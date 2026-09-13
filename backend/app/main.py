"""FastAPI entrypoint. Deployed as a single Vercel Function (see pyproject [tool.vercel])."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db, llm, orchestrator, queues
from .models import BatchState, DemoSnapshot, RunConfig, RunSummary, summary
from .paradigms import PARADIGMS
from .scenario import load_scenario
from .store import MemoryStore, Store
from .telemetry import emit, request_logger

app = FastAPI(title="agent-simulator api")
app.middleware("http")(request_logger)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

_store: Store | None = None
_background_tasks: set[asyncio.Task[Any]] = set()


def get_store() -> Store:
    global _store
    if _store is None:
        _store = db.PgStore() if os.getenv("DATABASE_URL") else MemoryStore()
        emit("info", "store.selected", kind=_store.__class__.__name__)
    return _store


def reset_state() -> None:
    """Test hook."""
    global _store
    _store = None
    llm.reset_client()


class GreetingIn(BaseModel):
    message: str = Field(min_length=1, max_length=280)


class BatchIn(BaseModel):
    config: RunConfig = RunConfig()
    n: int = Field(default=1, ge=1, le=25)


@app.get("/api/health")
def health(request: Request) -> dict[str, Any]:
    checks: dict[str, Any] = {"api": "ok"}
    try:
        checks["database"] = "ok" if db.ping() else "unhealthy"
    except Exception as exc:  # noqa: BLE001 - health endpoint reports, never raises
        checks["database"] = f"error: {exc.__class__.__name__}"
    checks["queues"] = "ok" if queues.oidc_token(request) else "unconfigured"
    return {"status": "ok", "checks": checks, "env": os.getenv("VERCEL_ENV", "development")}


@app.get("/api/greetings")
def get_greetings() -> list[dict[str, Any]]:
    return [
        {"id": row["id"], "message": row["message"], "created_at": row["created_at"].isoformat()}
        for row in db.list_greetings()
    ]


@app.post("/api/greetings", status_code=201)
async def create_greeting(payload: GreetingIn, request: Request) -> dict[str, Any]:
    row = db.insert_greeting(payload.message)
    queued = False
    try:
        await queues.send(
            queues.GREETINGS_TOPIC,
            {"greetingId": row["id"], "message": row["message"]},
            idempotency_key=f"greeting-{row['id']}",
            token=queues.oidc_token(request),
        )
        queued = True
    except Exception as exc:  # noqa: BLE001 - a queue outage must not fail the write
        emit("warning", "queue.publish_failed", greetingId=row["id"], reason=str(exc))
    return {
        "id": row["id"],
        "message": row["message"],
        "created_at": row["created_at"].isoformat(),
        "queued": queued,
    }


# --- simulation API ---------------------------------------------------------


@app.get("/api/scenario")
def get_scenario() -> dict[str, Any]:
    return load_scenario().model_dump(by_alias=True)


@app.get("/api/paradigms")
def get_paradigms() -> list[dict[str, str]]:
    return [{"id": p.id, "label": p.label, "description": p.description} for p in PARADIGMS.values()]


async def start_run(run_id: str, request: Request) -> None:
    """Kick off round 0 via Vercel Queues, or drive the run in-process."""
    mode = os.getenv("RUN_MODE", "")
    token = queues.oidc_token(request)
    if mode not in ("inline", "sync"):
        try:
            await queues.send(
                queues.SIMULATION_TOPIC,
                {"kind": "round", "runId": run_id, "round": 0},
                idempotency_key=f"run-{run_id}-round-0",
                token=token,
            )
            return
        except queues.QueueNotConfigured:
            pass  # no OIDC token → local dev, run inline
        except Exception as exc:  # noqa: BLE001 - queue outage falls back to inline
            emit("warning", "run.enqueue_failed", runId=run_id, reason=str(exc))
    client = llm.get_client()
    if mode == "sync":
        emit("info", "run.sync", runId=run_id)
        await orchestrator.run_to_completion(get_store(), client, run_id)
        return
    emit("info", "run.inline", runId=run_id)
    task = asyncio.create_task(orchestrator.run_to_completion(get_store(), client, run_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@app.post("/api/runs", status_code=201)
async def create_run(cfg: RunConfig, request: Request) -> dict[str, Any]:
    store = get_store()
    try:
        run = orchestrator.new_run(cfg, provider=llm.get_client().provider)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.create_run(run)
    await start_run(run.id, request)
    fresh = store.get_run(run.id) or run
    return fresh.model_dump(by_alias=True, mode="json")


@app.post("/api/runs/batch", status_code=201)
async def create_batch(payload: BatchIn, request: Request) -> dict[str, Any]:
    store = get_store()
    batch_id = str(uuid.uuid4())
    summaries: list[RunSummary] = []
    for i in range(payload.n):
        cfg = payload.config.model_copy(update={"seed": payload.config.seed + i})
        run = orchestrator.new_run(cfg, provider=llm.get_client().provider, batch_id=batch_id)
        store.create_run(run)
        summaries.append(summary(run))
    for s in summaries:
        await start_run(s.id, request)
    batch = BatchState(id=batch_id, runs=summaries)
    return batch.model_dump(by_alias=True, mode="json")


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, since_seq: int = -1) -> dict[str, Any]:
    run = get_store().get_run_since(run_id, since_seq)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run.model_dump(by_alias=True, mode="json")


@app.get("/api/runs")
def list_runs(is_demo: bool | None = None) -> list[dict[str, Any]]:
    return [
        s.model_dump(by_alias=True, mode="json") for s in get_store().list_runs(is_demo=is_demo)
    ]


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str) -> dict[str, Any]:
    runs = get_store().list_runs(batch_id=batch_id)
    if not runs:
        raise HTTPException(status_code=404, detail="batch not found")
    return BatchState(id=batch_id, runs=runs).model_dump(by_alias=True, mode="json")


@app.get("/api/demo")
def get_demo() -> dict[str, Any]:
    store = get_store()
    summaries = store.list_runs(is_demo=True)[:100]
    runs = [r for rid in summaries if (r := store.get_run(rid.id)) is not None]
    snapshot = DemoSnapshot(scenario=load_scenario(), runs=runs)
    return snapshot.model_dump(by_alias=True, mode="json")


# --- queue callbacks --------------------------------------------------------


async def _consume_greetings(request: Request, message_id: str) -> dict[str, str]:
    token = queues.oidc_token(request)
    message = await queues.receive_by_id(
        queues.GREETINGS_TOPIC, queues.GREETINGS_CONSUMER, message_id, token=token
    )
    if message is None:
        emit("info", "queue.already_processed", messageId=message_id)
        return {"status": "skipped"}
    emit(
        "info",
        "queue.consumed",
        topic=queues.GREETINGS_TOPIC,
        messageId=message_id,
        deliveryCount=message.get("deliveryCount"),
        payload=message["payload"],
    )
    await queues.acknowledge(
        queues.GREETINGS_TOPIC, queues.GREETINGS_CONSUMER, message["receiptHandle"], token=token
    )
    return {"status": "processed"}


async def _consume_simulation(request: Request, message_id: str) -> dict[str, str]:
    token = queues.oidc_token(request)
    message = await queues.receive_by_id(
        queues.SIMULATION_TOPIC, queues.SIMULATION_CONSUMER, message_id, token=token
    )
    if message is None:
        emit("info", "queue.already_processed", messageId=message_id)
        return {"status": "skipped"}

    store = get_store()
    client = llm.get_client()
    payload = message["payload"]
    run_id = payload["runId"]
    try:
        if payload.get("kind") != "round":
            raise ValueError(f"unknown simulation payload kind {payload.get('kind')!r}")
        run = await orchestrator.run_round(store, client, run_id, int(payload["round"]))
        emit(
            "info",
            "simulation.round_done",
            runId=run_id,
            round=payload["round"],
            status=run.status,
        )
    except Exception as exc:
        if (message.get("deliveryCount") or 0) > 3:
            emit("warning", "simulation.giving_up", runId=run_id, reason=str(exc))
            store.set_status(run_id, "error", error=str(exc))
        else:
            raise
    else:
        next_round = run.current_round
        if run.status == "running" and next_round < run.config.rounds:
            await queues.send(
                queues.SIMULATION_TOPIC,
                {"kind": "round", "runId": run_id, "round": next_round},
                idempotency_key=f"run-{run_id}-round-{next_round}",
                token=token,
            )
    await queues.acknowledge(
        queues.SIMULATION_TOPIC, queues.SIMULATION_CONSUMER, message["receiptHandle"], token=token
    )
    return {"status": "processed"}


@app.post("/api/queues/greetings")
@app.post("/api/queues/simulation")
@app.post(queues.TRIGGER_PATH)
async def consume_queue(request: Request) -> dict[str, str]:
    """Push callback for Vercel Queues topics (see vercel.json experimentalTriggers).

    Vercel Queues delivers at-least-once, so handlers must be idempotent.
    """
    try:
        event = json.loads(await request.body())
        topic, consumer = queues.callback_topic(event)
        message_id = queues.callback_message_id(event, topic, consumer)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="unrecognized queue callback") from exc

    if (topic, consumer) == (queues.GREETINGS_TOPIC, queues.GREETINGS_CONSUMER):
        return await _consume_greetings(request, message_id)
    if (topic, consumer) == (queues.SIMULATION_TOPIC, queues.SIMULATION_CONSUMER):
        return await _consume_simulation(request, message_id)
    raise HTTPException(status_code=400, detail=f"no handler for {topic}/{consumer}")

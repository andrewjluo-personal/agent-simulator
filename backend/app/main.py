"""FastAPI entrypoint. Deployed as a single Vercel Function (see pyproject [tool.vercel])."""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db, llm, orchestrator, queues, truth, validation_jobs
from .anthropic_auth import vercel_oidc_context
from .engine_version import ENGINE_VERSION, scenario_engine_version
from .models import (
    BatchState,
    DemoSnapshot,
    Model,
    RunConfig,
    RunSummary,
    Scenario,
    ValidationJob,
    summary,
)
from .paradigms import PARADIGMS
from .samples import HIDDEN_SAMPLE_IDS, SAMPLES_BY_ID, ensure_samples
from .scenario import DEFAULT_SCENARIO_ID, load_scenario
from .store import MemoryStore, Store
from .telemetry import emit, request_logger, server_timing

app = FastAPI(title="agent-simulator api")
app.middleware("http")(request_logger)
app.middleware("http")(server_timing)
app.middleware("http")(vercel_oidc_context)

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
    expose_headers=["Server-Timing", "x-request-id"],
)

_store: Store | None = None
_background_tasks: set[asyncio.Task[Any]] = set()

RUN_RATE_LIMIT_PER_MIN = int(os.getenv("RUN_RATE_LIMIT_PER_MIN", "6"))
VALIDATE_RATE_LIMIT_PER_HOUR = int(os.getenv("VALIDATE_RATE_LIMIT_PER_HOUR", "2"))
FORK_RATE_LIMIT_PER_HOUR = int(os.getenv("FORK_RATE_LIMIT_PER_HOUR", "10"))
VALIDATION_JOB_STALE_MIN = int(os.getenv("VALIDATION_JOB_STALE_MIN", "30"))
CUSTOM_SCENARIOS_LISTED = int(os.getenv("CUSTOM_SCENARIOS_LISTED", "20"))
AUTO_RUN_ON_LOAD = os.getenv("AUTO_RUN_ON_LOAD", "1") not in ("0", "false", "off")


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded.strip():
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(store: Store, request: Request, n: int) -> None:
    if RUN_RATE_LIMIT_PER_MIN <= 0:
        return
    total = store.record_run_requests(_client_key(request), n, 60)
    if total > RUN_RATE_LIMIT_PER_MIN:
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many runs started from this address in the last minute — "
                "please wait a moment and try again."
            ),
        )


def _check_hourly_limit(store: Store, request: Request, kind: str, limit: int, what: str) -> None:
    if limit <= 0:
        return
    total = store.record_run_requests(f"{kind}:{_client_key(request)}", 1, 3600)
    if total > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Too many {what} from this address in the last hour — limit is {limit}/hour.",
        )


def _validation_job_is_fresh(job: ValidationJob) -> bool:
    updated = datetime.fromisoformat(job.updated_at)
    return updated > datetime.now(UTC) - timedelta(minutes=VALIDATION_JOB_STALE_MIN)


def get_store() -> Store:
    global _store
    if _store is None:
        _store = db.PgStore() if os.getenv("DATABASE_URL") else MemoryStore()
        ensure_samples(_store)
        emit("info", "store.selected", kind=_store.__class__.__name__)
    return _store


def reset_state() -> None:
    """Test hook."""
    global _store
    _store = None
    llm.reset_client()
    db.reset_pool()


class GreetingIn(BaseModel):
    message: str = Field(min_length=1, max_length=280)


class BatchIn(BaseModel):
    config: RunConfig = RunConfig()
    n: int = Field(default=1, ge=1, le=25)


class ClientEvent(BaseModel):
    """Browser-side event forwarded into Vercel Logs; the frontend is static, so it cannot log."""

    name: str = Field(min_length=1, max_length=120)
    sessionId: str = Field(min_length=1, max_length=64)
    level: Literal["info", "warning", "error"] = "info"
    context: dict[str, Any] = Field(default_factory=dict)


class ForkIn(Model):
    base_id: str
    scenario: Scenario
    slug: str | None = None


@app.get("/api/health")
def health(request: Request) -> dict[str, Any]:
    checks: dict[str, Any] = {"api": "ok"}
    try:
        checks["database"] = "ok" if db.ping() else "unhealthy"
    except Exception as exc:  # noqa: BLE001 - health endpoint reports, never raises
        checks["database"] = f"error: {exc.__class__.__name__}"
    checks["queues"] = "ok" if queues.oidc_token(request) else "unconfigured"
    return {
        "status": "ok",
        "checks": checks,
        "env": os.getenv("VERCEL_ENV", "development"),
        "engineVersion": ENGINE_VERSION,
        "autoRunOnLoad": AUTO_RUN_ON_LOAD,
    }


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


@app.post("/api/client-logs", status_code=202)
def ingest_client_log(event: ClientEvent, request: Request) -> dict[str, str]:
    emit(
        event.level,
        f"client.{event.name}",
        clientSessionId=event.sessionId,
        userAgent=request.headers.get("user-agent"),
        context=json.dumps(event.context)[:2000],
    )
    return {"status": "accepted"}


# --- simulation API ---------------------------------------------------------


@app.get("/api/scenario")
def get_scenario() -> dict[str, Any]:
    return load_scenario(get_store(), DEFAULT_SCENARIO_ID).model_dump(by_alias=True)


@app.get("/api/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    scenarios = get_store().list_scenarios()
    listed = [s for s in scenarios if s.source.kind != "custom" and s.id not in HIDDEN_SAMPLE_IDS]
    customs = [s for s in scenarios if s.source.kind == "custom"]
    customs.sort(
        key=lambda s: (s.created_at is not None, s.created_at or ""),
        reverse=True,
    )
    return [s.model_dump(by_alias=True) for s in [*listed, *customs[:CUSTOM_SCENARIOS_LISTED]]]


@app.get("/api/scenarios/{scenario_id}")
def get_scenario_by_id(scenario_id: str) -> dict[str, Any]:
    scenario = get_store().get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return scenario.model_dump(by_alias=True)


@app.get("/api/scenarios/{scenario_id}/analysis")
def get_scenario_analysis(scenario_id: str) -> dict[str, Any]:
    scenario = get_store().get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return truth.analysis(scenario).model_dump(by_alias=True)


@app.post("/api/scenarios/analyze")
def analyze_scenario(scenario: Scenario) -> dict[str, Any]:
    return truth.analysis(scenario).model_dump(by_alias=True)


@app.post("/api/scenarios", status_code=201)
def fork_scenario(payload: ForkIn, request: Request) -> dict[str, Any]:
    store = get_store()
    base = store.get_scenario(payload.base_id)
    if base is None:
        raise HTTPException(status_code=404, detail="base scenario not found")
    _check_hourly_limit(store, request, "fork", FORK_RATE_LIMIT_PER_HOUR, "scenarios saved")
    if payload.slug is not None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", payload.slug):
            raise HTTPException(status_code=422, detail="invalid scenario slug")
        if store.get_scenario(payload.slug) is not None:
            raise HTTPException(status_code=409, detail="scenario already exists")
        scenario_id = payload.slug
    else:
        stem = re.sub(r"-v\d+$", "", payload.base_id)
        n = 2
        while True:
            candidate = f"{stem}-v{n}"
            if store.get_scenario(candidate) is None and candidate not in SAMPLES_BY_ID:
                break
            n += 1
        scenario_id = candidate
    source = base.source.model_copy(update={"kind": "custom", "fidelity": "modified"})
    scenario = payload.scenario.model_copy(
        update={
            "id": scenario_id,
            "is_sample": False,
            "parent_id": payload.base_id,
            "created_at": datetime.now(UTC).isoformat(),
            "validation": None,
            "source": source,
        }
    )
    store.upsert_scenario(scenario)
    return scenario.model_dump(by_alias=True)


@app.post("/api/scenarios/{scenario_id}/validate", status_code=202)
async def validate_scenario(
    scenario_id: str,
    request: Request,
    discussion: bool = False,
    model: str = "claude-haiku-4-5",
) -> dict[str, Any]:
    store = get_store()
    if store.get_scenario(scenario_id) is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    latest = store.latest_validation_job(scenario_id)
    if (
        latest is not None
        and latest.status in ("queued", "running")
        and _validation_job_is_fresh(latest)
    ):
        raise HTTPException(status_code=409, detail="validation already running")
    active = store.active_validation_job(VALIDATION_JOB_STALE_MIN * 60)
    if active is not None:
        raise HTTPException(
            status_code=429,
            detail=(
                f"A validation is already running (scenario {active.scenario_id}); "
                "try again in a few minutes."
            ),
        )
    _check_hourly_limit(
        store, request, "validate", VALIDATE_RATE_LIMIT_PER_HOUR, "validations started"
    )
    now = datetime.now(UTC).isoformat()
    job = ValidationJob(
        id=str(uuid.uuid4()),
        scenario_id=scenario_id,
        model=model,
        status="queued",
        trials=10,
        discussion_runs=10 if discussion else 0,
        created_at=now,
        updated_at=now,
    )
    store.upsert_validation_job(job)

    async def run() -> None:
        client = llm.get_client()
        await validation_jobs.run_job(
            store,
            client,
            job.id,
            lambda run_id: start_run(run_id, request),
        )
        current = store.get_validation_job(job.id)
        if current is not None:
            validation_jobs.finalize_if_ready(store, current)

    mode = os.getenv("RUN_MODE", "")
    if mode == "sync":
        await run()
    else:
        try:
            await queues.send(
                queues.SIMULATION_TOPIC,
                {"kind": "validate", "jobId": job.id},
                idempotency_key=f"validate-{job.id}",
                token=queues.oidc_token(request),
            )
        except queues.QueueNotConfigured:
            task = asyncio.create_task(run())
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
        except Exception as exc:  # noqa: BLE001 - queue outage falls back to inline
            emit("warning", "validation.enqueue_failed", jobId=job.id, reason=str(exc))
            task = asyncio.create_task(run())
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
    current = store.get_validation_job(job.id) or job
    return current.model_dump(by_alias=True)


@app.get("/api/validation-jobs/{job_id}")
def get_validation_job(job_id: str) -> dict[str, Any]:
    store = get_store()
    job = store.get_validation_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="validation job not found")
    return validation_jobs.finalize_if_ready(store, job).model_dump(by_alias=True)


@app.get("/api/scenarios/{scenario_id}/validation-job")
def get_scenario_validation_job(scenario_id: str) -> dict[str, Any]:
    store = get_store()
    if store.get_scenario(scenario_id) is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    job = store.latest_validation_job(scenario_id)
    if job is None:
        raise HTTPException(status_code=404, detail="validation job not found")
    return validation_jobs.finalize_if_ready(store, job).model_dump(by_alias=True)


@app.post("/api/scenarios/{scenario_id}/reset")
def reset_scenario(scenario_id: str) -> dict[str, Any]:
    sample = SAMPLES_BY_ID.get(scenario_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="not a sample scenario")
    get_store().upsert_scenario(sample)
    return sample.model_dump(by_alias=True)


@app.get("/api/paradigms")
def get_paradigms() -> list[dict[str, str]]:
    return [
        {"id": p.id, "label": p.label, "description": p.description} for p in PARADIGMS.values()
    ]


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
    _check_rate_limit(store, request, 1)
    try:
        run = orchestrator.new_run(store, cfg, provider=llm.get_client().provider)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    store.create_run(run)
    await start_run(run.id, request)
    fresh = store.get_run(run.id) or run
    return fresh.model_dump(by_alias=True, mode="json")


@app.post("/api/runs/batch", status_code=201)
async def create_batch(payload: BatchIn, request: Request) -> dict[str, Any]:
    store = get_store()
    _check_rate_limit(store, request, payload.n)
    batch_id = str(uuid.uuid4())
    summaries: list[RunSummary] = []
    for i in range(payload.n):
        cfg = payload.config.model_copy(update={"seed": payload.config.seed + i})
        try:
            run = orchestrator.new_run(
                store, cfg, provider=llm.get_client().provider, batch_id=batch_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
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
def get_demo(scenario_id: str | None = Query(default=None, alias="scenarioId")) -> dict[str, Any]:
    """Scenario plus recent finished run *summaries* (demo or live, current engine
    version); the client fetches full transcripts via GET /api/runs/{id} on demand."""

    snap = get_store().demo_snapshot(scenario_id or DEFAULT_SCENARIO_ID)
    if snap is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    scenario, runs = snap
    snapshot = DemoSnapshot(
        scenario=scenario,
        runs=runs,
        engine_version=scenario_engine_version(scenario),
        auto_run_on_load=AUTO_RUN_ON_LOAD,
    )
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
    run_id = payload.get("runId")
    job_id = payload.get("jobId")
    try:
        if payload.get("kind") == "validate":
            if not isinstance(job_id, str):
                raise ValueError("validation payload missing jobId")
            await validation_jobs.run_job(
                store,
                client,
                job_id,
                lambda validation_run_id: start_run(validation_run_id, request),
            )
            job = store.get_validation_job(job_id)
            if job is not None:
                validation_jobs.finalize_if_ready(store, job)
            emit("info", "simulation.validation_done", jobId=job_id)
            run = None
        elif payload.get("kind") != "round":
            raise ValueError(f"unknown simulation payload kind {payload.get('kind')!r}")
        else:
            if not isinstance(run_id, str):
                raise ValueError("round payload missing runId")
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
            emit("warning", "simulation.giving_up", runId=run_id, jobId=job_id, reason=str(exc))
            if isinstance(job_id, str):
                job = store.get_validation_job(job_id)
                if job is not None:
                    job.status = "error"
                    job.error = str(exc)
                    job.updated_at = datetime.now(UTC).isoformat()
                    store.upsert_validation_job(job)
            elif isinstance(run_id, str):
                store.set_status(run_id, "error", error=str(exc))
        else:
            raise
    else:
        next_round = run.current_round if run is not None else 0
        if (
            run is not None
            and run.status == "running"
            and next_round < orchestrator.total_rounds(run)
        ):
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

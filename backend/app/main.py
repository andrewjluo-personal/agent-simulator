"""FastAPI entrypoint. Deployed as a single Vercel Function (see pyproject [tool.vercel])."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db, queues
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


class GreetingIn(BaseModel):
    message: str = Field(min_length=1, max_length=280)


class Greeting(BaseModel):
    id: int
    message: str
    created_at: str


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
    message_id: str | None = None
    try:
        message_id = await queues.send(
            queues.GREETINGS_TOPIC,
            {"greetingId": row["id"], "message": row["message"]},
            idempotency_key=f"greeting-{row['id']}",
            token=queues.oidc_token(request),
        )
    except Exception as exc:  # noqa: BLE001 - a queue outage must not fail the write
        emit("warning", "queue.publish_failed", greetingId=row["id"], reason=str(exc))
    return {
        "id": row["id"],
        "message": row["message"],
        "created_at": row["created_at"].isoformat(),
        "queueMessageId": message_id,
    }


@app.post("/api/queues/greetings")
@app.post(queues.TRIGGER_PATH)
async def consume_greeting(request: Request) -> dict[str, str]:
    """Push callback for the `greetings` topic (see vercel.json experimentalTriggers).

    Vercel Queues delivers at-least-once, so handlers must be idempotent.
    """
    try:
        event = json.loads(await request.body())
        message_id = event["data"]["messageId"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="unrecognized queue callback") from exc

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

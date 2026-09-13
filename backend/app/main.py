"""FastAPI entrypoint. Deployed as a single Vercel Function (see pyproject [tool.vercel])."""

from __future__ import annotations

import base64
import json
import os
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException
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
def health() -> dict[str, Any]:
    checks: dict[str, Any] = {"api": "ok"}
    try:
        checks["database"] = "ok" if db.ping() else "unhealthy"
    except Exception as exc:  # noqa: BLE001 - health endpoint reports, never raises
        checks["database"] = f"error: {exc.__class__.__name__}"
    checks["queues"] = "ok" if os.getenv("VERCEL_OIDC_TOKEN") else "unconfigured"
    return {"status": "ok", "checks": checks, "env": os.getenv("VERCEL_ENV", "development")}


@app.get("/api/greetings")
def get_greetings() -> list[dict[str, Any]]:
    return [
        {"id": row["id"], "message": row["message"], "created_at": row["created_at"].isoformat()}
        for row in db.list_greetings()
    ]


@app.post("/api/greetings", status_code=201)
async def create_greeting(payload: GreetingIn) -> dict[str, Any]:
    row = db.insert_greeting(payload.message)
    message_id: str | None = None
    try:
        message_id = await queues.send(
            queues.GREETINGS_TOPIC,
            {"greetingId": row["id"], "message": row["message"]},
            idempotency_key=f"greeting-{row['id']}",
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
def consume_greeting(body: Annotated[dict[str, Any], Body()]) -> dict[str, str]:
    """Push callback for the `greetings` topic (see vercel.json experimentalTriggers).

    Vercel Queues delivers at-least-once, so handlers must be idempotent.
    """
    payload = body
    if "body" in body and isinstance(body["body"], str):
        try:
            payload = json.loads(base64.b64decode(body["body"]))
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="unreadable message body") from exc
    emit("info", "queue.consumed", topic=queues.GREETINGS_TOPIC, payload=payload)
    return {"status": "processed"}

"""Vercel Queues client (HTTP API v3).

Vercel's first-party SDK is JS-only, so the Python backend talks to the REST API
described at https://vercel.com/docs/queues/api. Requests are authenticated with
the Vercel OIDC token that Vercel Functions expose as VERCEL_OIDC_TOKEN.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .telemetry import emit

DEFAULT_REGION = "iad1"
GREETINGS_TOPIC = "greetings"


class QueueNotConfigured(RuntimeError):
    pass


def _base_url() -> str:
    region = os.getenv("VERCEL_QUEUE_REGION", DEFAULT_REGION)
    return f"https://{region}.vercel-queue.com/api/v3"


def _token() -> str:
    token = os.getenv("VERCEL_OIDC_TOKEN")
    if not token:
        raise QueueNotConfigured("VERCEL_OIDC_TOKEN is not set")
    return token


def _headers() -> dict[str, str]:
    headers = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}
    deployment_id = os.getenv("VERCEL_DEPLOYMENT_ID")
    if deployment_id:
        headers["Vqs-Deployment-Id"] = deployment_id
    return headers


async def send(topic: str, payload: dict[str, Any], idempotency_key: str | None = None) -> str:
    """Publish a message to a topic and return its message id."""
    headers = _headers()
    if idempotency_key:
        headers["Vqs-Idempotency-Key"] = idempotency_key
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{_base_url()}/topic/{topic}",
            content=json.dumps(payload),
            headers=headers,
        )
    response.raise_for_status()
    message_id = str(response.json()["messageId"])
    emit("info", "queue.published", topic=topic, messageId=message_id)
    return message_id


async def receive(topic: str, consumer: str, max_messages: int = 10) -> list[dict[str, Any]]:
    """Poll a consumer group. Used by the local worker; production uses push callbacks."""
    headers = _headers() | {
        "Accept": "application/x-ndjson",
        "Vqs-Max-Messages": str(max_messages),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{_base_url()}/topic/{topic}/consumer/{consumer}", headers=headers
        )
    if response.status_code == 204:
        return []
    response.raise_for_status()
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


async def acknowledge(topic: str, consumer: str, receipt_handle: str) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.delete(
            f"{_base_url()}/topic/{topic}/consumer/{consumer}/receipt/{receipt_handle}",
            headers=_headers(),
        )
    response.raise_for_status()

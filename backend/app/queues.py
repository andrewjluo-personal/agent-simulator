"""Vercel Queues client (HTTP API v3).

Vercel's first-party SDK is JS-only, so the Python backend talks to the REST API
described at https://vercel.com/docs/queues/api. Requests are authenticated with a
Vercel OIDC token: functions receive it on the `x-vercel-oidc-token` request header,
while local runs read VERCEL_OIDC_TOKEN from `vercel env pull`.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import Request

from .telemetry import emit

OIDC_HEADER = "x-vercel-oidc-token"

DEFAULT_REGION = "iad1"
GREETINGS_TOPIC = "greetings"
GREETINGS_CONSUMER = "greetings-worker"  # must match vercel.json
SIMULATION_TOPIC = "simulation"
SIMULATION_CONSUMER = "simulation-worker"  # must match vercel.json

# Queue triggers invoke the Vercel Function at the path of its resolved entrypoint,
# which for a FastAPI deployment is /fastapi rather than any route the app declares.
TRIGGER_PATH = "/fastapi"
CALLBACK_EVENT_TYPE = "com.vercel.queue.v1beta"


class QueueNotConfigured(RuntimeError):
    pass


def _segment(value: str) -> str:
    """Topic names, ids and receipt handles are opaque; keep them one path segment."""
    return quote(value, safe="")


def callback_topic(event: Any) -> tuple[str, str]:
    """Extract (topic, consumer) from a queue trigger CloudEvent, rejecting foreign envelopes."""
    if not isinstance(event, dict):
        raise TypeError("callback body is not an object")
    if event.get("type") != CALLBACK_EVENT_TYPE:
        raise ValueError(f"unexpected CloudEvent type {event.get('type')!r}")
    data = event["data"]
    topic, consumer = data["queueName"], data["consumerGroup"]
    if not isinstance(topic, str) or not isinstance(consumer, str):
        raise TypeError("missing queueName/consumerGroup")
    if event.get("source") != f"/topic/{topic}/consumer/{consumer}":
        raise ValueError(f"unexpected CloudEvent source {event.get('source')!r}")
    return topic, consumer


def callback_message_id(event: Any, topic: str, consumer: str) -> str:
    """Extract the message id from a queue trigger CloudEvent, rejecting foreign envelopes.

    Vercel exposes the trigger path publicly and signs nothing, so the envelope is the
    only thing a handler can check; the claim itself still fails for unknown ids.
    """
    if not isinstance(event, dict):
        raise TypeError("callback body is not an object")
    if event.get("type") != CALLBACK_EVENT_TYPE:
        raise ValueError(f"unexpected CloudEvent type {event.get('type')!r}")
    if event.get("source") != f"/topic/{topic}/consumer/{consumer}":
        raise ValueError(f"unexpected CloudEvent source {event.get('source')!r}")
    data = event["data"]
    if data["queueName"] != topic or data["consumerGroup"] != consumer:
        raise ValueError("CloudEvent data does not match this consumer")
    message_id = data["messageId"]
    if not isinstance(message_id, str) or not message_id:
        raise TypeError("missing messageId")
    return message_id


def _base_url() -> str:
    region = os.getenv("VERCEL_QUEUE_REGION", DEFAULT_REGION)
    return f"https://{region}.vercel-queue.com/api/v3"


def oidc_token(request: Request | None = None) -> str | None:
    """Vercel injects the token per request in production and per `env pull` locally."""
    if request is not None:
        header = request.headers.get(OIDC_HEADER)
        if header:
            return header
    return os.getenv("VERCEL_OIDC_TOKEN")


def _headers(token: str | None) -> dict[str, str]:
    token = token or oidc_token()
    if not token:
        raise QueueNotConfigured("no Vercel OIDC token available")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    deployment_id = os.getenv("VERCEL_DEPLOYMENT_ID")
    if deployment_id:
        headers["Vqs-Deployment-Id"] = deployment_id
    return headers


async def send(
    topic: str,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
    token: str | None = None,
) -> str:
    """Publish a message to a topic and return its message id."""
    headers = _headers(token)
    if idempotency_key:
        headers["Vqs-Idempotency-Key"] = idempotency_key
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{_base_url()}/topic/{_segment(topic)}",
            content=json.dumps(payload),
            headers=headers,
        )
    response.raise_for_status()
    message_id = str(response.json()["messageId"])
    emit("info", "queue.published", topic=topic, messageId=message_id)
    return message_id


def _decode(line: str) -> dict[str, Any]:
    message: dict[str, Any] = json.loads(line)
    message["payload"] = json.loads(base64.b64decode(message["body"]))
    return message


async def receive(
    topic: str, consumer: str, max_messages: int = 10, token: str | None = None
) -> list[dict[str, Any]]:
    """Poll a consumer group. Used by the local worker; production uses push callbacks."""
    headers = _headers(token) | {
        "Accept": "application/x-ndjson",
        "Vqs-Max-Messages": str(max_messages),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{_base_url()}/topic/{_segment(topic)}/consumer/{_segment(consumer)}",
            headers=headers,
        )
    if response.status_code == 204:
        return []
    response.raise_for_status()
    return [_decode(line) for line in response.text.splitlines() if line.strip()]


async def receive_by_id(
    topic: str, consumer: str, message_id: str, token: str | None = None
) -> dict[str, Any] | None:
    """Claim a single message, as referenced by a push callback."""
    headers = _headers(token) | {"Accept": "application/x-ndjson"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{_base_url()}/topic/{_segment(topic)}/consumer/{_segment(consumer)}"
            f"/id/{_segment(message_id)}",
            headers=headers,
        )
    if response.status_code in (204, 404):
        return None
    response.raise_for_status()
    lines = [line for line in response.text.splitlines() if line.strip()]
    return _decode(lines[0]) if lines else None


async def acknowledge(
    topic: str, consumer: str, receipt_handle: str, token: str | None = None
) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.request(
            "DELETE",
            f"{_base_url()}/topic/{_segment(topic)}/consumer/{_segment(consumer)}"
            f"/lease/{_segment(receipt_handle)}",
            headers=_headers(token),
        )
    response.raise_for_status()

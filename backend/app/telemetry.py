"""Structured JSON logging, collected by Vercel Observability / Logs."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response

SERVICE = "agent-simulator-api"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
            "service": SERVICE,
            "env": os.getenv("VERCEL_ENV", "development"),
            "deploymentId": os.getenv("VERCEL_DEPLOYMENT_ID"),
        }
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps({k: v for k, v in payload.items() if v is not None})


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    return logging.getLogger(SERVICE)


log = configure_logging()


def emit(level: str, message: str, **context: Any) -> None:
    getattr(log, level)(message, extra={"context": context})


async def request_logger(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("x-vercel-id") or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        emit(
            "exception",
            "request.failed",
            requestId=request_id,
            method=request.method,
            path=request.url.path,
            durationMs=round((time.perf_counter() - started) * 1000, 2),
        )
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    emit(
        "info",
        "request.completed",
        requestId=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        durationMs=duration_ms,
    )
    response.headers["x-request-id"] = request_id
    return response

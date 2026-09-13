"""Neon Postgres access via psycopg3."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

SCHEMA = """
create table if not exists greetings (
    id bigserial primary key,
    message text not null,
    created_at timestamptz not null default now()
)
"""


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


@contextmanager
def connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=10) as conn:
        yield conn


def init_schema() -> None:
    with connection() as conn:
        conn.execute(SCHEMA)


def insert_greeting(message: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            "insert into greetings (message) values (%s) returning id, message, created_at",
            (message,),
        ).fetchone()
    assert row is not None
    return row


def list_greetings(limit: int = 20) -> list[dict[str, Any]]:
    with connection() as conn:
        return conn.execute(
            "select id, message, created_at from greetings order by id desc limit %s",
            (limit,),
        ).fetchall()


def ping() -> bool:
    with connection() as conn:
        return conn.execute("select 1 as ok").fetchone() == {"ok": 1}

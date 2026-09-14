"""Neon Postgres access via psycopg3."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .engine_version import ENGINE_VERSION
from .models import Metrics, RunState, RunStatus, RunSummary, Scenario, Turn, ValidationJob, Vote

SCHEMA = """
create table if not exists greetings (
    id bigserial primary key,
    message text not null,
    created_at timestamptz not null default now()
);

create table if not exists runs (
    id uuid primary key,
    scenario_id text not null,
    scenario jsonb not null,
    config jsonb not null,
    status text not null,
    current_round int not null default 0,
    is_demo boolean not null default false,
    batch_id uuid,
    llm_provider text not null,
    engine_version text not null default '',
    error text,
    metrics jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
alter table runs add column if not exists engine_version text not null default '';
create index if not exists runs_demo_idx on runs (is_demo, created_at desc);
create index if not exists runs_batch_idx on runs (batch_id);

create table if not exists validation_jobs (
    id text primary key,
    scenario_id text not null,
    status text not null,
    body jsonb not null,
    updated_at timestamptz not null default now()
);
create index if not exists validation_jobs_scenario_idx
    on validation_jobs (scenario_id, updated_at desc);

create table if not exists run_requests (
    id bigserial primary key,
    client_key text not null,
    created_at timestamptz not null default now()
);
create index if not exists run_requests_key_idx on run_requests (client_key, created_at);

create table if not exists scenarios (
    id text primary key,
    title text not null,
    is_sample boolean not null default false,
    body jsonb not null,
    updated_at timestamptz not null default now()
);

create table if not exists turns (
    run_id uuid not null references runs(id) on delete cascade,
    seq int not null,
    round int not null,
    agent_id text not null,
    sentences jsonb not null,
    cited jsonb not null,
    hallucinated jsonb not null,
    lean text not null,
    confidence real not null,
    latency_ms int,
    input_tokens int,
    output_tokens int,
    primary key (run_id, seq)
);
alter table turns add column if not exists heard_before jsonb;

create table if not exists votes (
    run_id uuid not null references runs(id) on delete cascade,
    round int not null,
    agent_id text not null,
    choice text not null,
    confidence real not null,
    reason text,
    said_lean text not null default 'undecided',
    latency_ms int,
    input_tokens int,
    output_tokens int,
    primary key (run_id, round, agent_id)
);

alter table votes add column if not exists said_lean text not null default 'undecided'
"""


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


@dataclass
class DbTiming:
    """Per-request accounting surfaced as a `Server-Timing` header."""

    acquire_ms: float = 0.0
    total_ms: float = 0.0
    connections: int = 0


timing: ContextVar[DbTiming | None] = ContextVar("db_timing", default=None)

_pool: ConnectionPool[psycopg.Connection[dict[str, Any]]] | None = None


def pool() -> ConnectionPool[psycopg.Connection[dict[str, Any]]]:
    """Module-level pool so warm function instances reuse Neon connections instead of
    paying the TCP+TLS+auth handshake on every request."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            database_url(),
            connection_class=psycopg.Connection[dict[str, Any]],
            kwargs={"row_factory": dict_row, "connect_timeout": 10, "autocommit": True},
            min_size=1,
            max_size=int(os.getenv("DB_POOL_MAX", "5")),
            max_idle=300,
            check=ConnectionPool.check_connection,
            open=True,
        )
    return _pool


def reset_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
    _pool = None


@contextmanager
def connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    started = time.perf_counter()
    with pool().connection() as conn:
        acquired = time.perf_counter()
        try:
            yield conn
        finally:
            stats = timing.get()
            if stats is not None:
                now = time.perf_counter()
                stats.connections += 1
                stats.acquire_ms += (acquired - started) * 1000
                stats.total_ms += (now - started) * 1000


def init_schema() -> None:
    with connection() as conn:
        for statement in SCHEMA.split(";"):
            if statement.strip():
                conn.execute(statement)


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


def _turn_from_row(row: dict[str, Any]) -> Turn:
    return Turn(
        seq=row["seq"],
        round=row["round"],
        agent_id=row["agent_id"],
        sentences=row["sentences"],
        cited=row["cited"],
        hallucinated=row["hallucinated"],
        lean=row["lean"],
        confidence=row["confidence"],
        latency_ms=row["latency_ms"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        heard_before=row.get("heard_before") or [],
    )


def _vote_from_row(row: dict[str, Any]) -> Vote:
    return Vote(
        round=row["round"],
        agent_id=row["agent_id"],
        choice=row["choice"],
        confidence=row["confidence"],
        reason=row["reason"],
        said_lean=row.get("said_lean") or "undecided",
    )


def _run_from_row(row: dict[str, Any], turns: list[Turn], votes: list[Vote]) -> RunState:
    return RunState(
        id=str(row["id"]),
        scenario_id=row["scenario_id"],
        scenario=Scenario.model_validate(row["scenario"]),
        config=row["config"],
        status=row["status"],
        current_round=row["current_round"],
        is_demo=row["is_demo"],
        batch_id=str(row["batch_id"]) if row["batch_id"] else None,
        llm_provider=row["llm_provider"],
        error=row["error"],
        metrics=row["metrics"],
        engine_version=row.get("engine_version") or "",
        turns=turns,
        votes=votes,
        created_at=row["created_at"].isoformat(),
    )


def _summary_from_row(row: dict[str, Any]) -> RunSummary:
    return RunSummary(
        id=str(row["id"]),
        scenario_id=row["scenario_id"],
        config=row["config"],
        status=row["status"],
        current_round=row["current_round"],
        is_demo=row["is_demo"],
        batch_id=str(row["batch_id"]) if row["batch_id"] else None,
        llm_provider=row["llm_provider"],
        error=row["error"],
        metrics=row["metrics"],
        engine_version=row.get("engine_version") or "",
        created_at=row["created_at"].isoformat(),
    )


class PgStore:
    def list_scenarios(self) -> list[Scenario]:
        with connection() as conn:
            rows = conn.execute("select body from scenarios order by title").fetchall()
        return [Scenario.model_validate(r["body"]) for r in rows]

    def get_scenario(self, scenario_id: str) -> Scenario | None:
        with connection() as conn:
            row = conn.execute(
                "select body from scenarios where id = %s", (scenario_id,)
            ).fetchone()
        return Scenario.model_validate(row["body"]) if row else None

    def upsert_scenario(self, scenario: Scenario) -> None:
        with connection() as conn:
            conn.execute(
                "insert into scenarios (id, title, is_sample, body) values (%s, %s, %s, %s) "
                "on conflict (id) do update set title = excluded.title, "
                "is_sample = excluded.is_sample, body = excluded.body, updated_at = now()",
                (
                    scenario.id,
                    scenario.title,
                    scenario.is_sample,
                    Jsonb(scenario.model_dump(by_alias=True)),
                ),
            )

    def delete_scenario(self, scenario_id: str) -> bool:
        with connection() as conn:
            cur = conn.execute(
                "delete from scenarios where id = %s and is_sample", (scenario_id,)
            )
        return (cur.rowcount or 0) > 0

    def upsert_validation_job(self, job: ValidationJob) -> None:
        with connection() as conn:
            conn.execute(
                "insert into validation_jobs (id, scenario_id, status, body, updated_at) "
                "values (%s, %s, %s, %s, now()) "
                "on conflict (id) do update set scenario_id = excluded.scenario_id, "
                "status = excluded.status, body = excluded.body, updated_at = now()",
                (
                    job.id,
                    job.scenario_id,
                    job.status,
                    Jsonb(job.model_dump(by_alias=True)),
                ),
            )

    def get_validation_job(self, job_id: str) -> ValidationJob | None:
        with connection() as conn:
            row = conn.execute(
                "select body from validation_jobs where id = %s", (job_id,)
            ).fetchone()
        return ValidationJob.model_validate(row["body"]) if row else None

    def latest_validation_job(self, scenario_id: str) -> ValidationJob | None:
        with connection() as conn:
            row = conn.execute(
                "select body from validation_jobs where scenario_id = %s "
                "order by updated_at desc limit 1",
                (scenario_id,),
            ).fetchone()
        return ValidationJob.model_validate(row["body"]) if row else None

    def active_validation_job(self, stale_after_s: int) -> ValidationJob | None:
        with connection() as conn:
            row = conn.execute(
                "select body from validation_jobs "
                "where status in ('queued', 'running') "
                "and updated_at > now() - make_interval(secs => %s) "
                "order by updated_at desc limit 1",
                (stale_after_s,),
            ).fetchone()
        return ValidationJob.model_validate(row["body"]) if row else None

    def create_run(self, run: RunState) -> None:
        with connection() as conn:
            conn.execute(
                "insert into runs (id, scenario_id, scenario, config, status, "
                "current_round, is_demo, batch_id, llm_provider, engine_version) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    run.id,
                    run.scenario_id,
                    Jsonb(run.scenario.model_dump(by_alias=True)),
                    Jsonb(run.config.model_dump(by_alias=True)),
                    run.status,
                    run.current_round,
                    run.is_demo,
                    run.batch_id,
                    run.llm_provider,
                    run.engine_version,
                ),
            )

    def _turns(self, conn: psycopg.Connection[dict[str, Any]], run_id: str) -> list[Turn]:
        rows = conn.execute(
            "select * from turns where run_id = %s order by seq", (run_id,)
        ).fetchall()
        return [_turn_from_row(r) for r in rows]

    def _votes(self, conn: psycopg.Connection[dict[str, Any]], run_id: str) -> list[Vote]:
        rows = conn.execute(
            "select * from votes where run_id = %s order by round, agent_id", (run_id,)
        ).fetchall()
        return [_vote_from_row(r) for r in rows]

    def get_run(self, run_id: str) -> RunState | None:
        with connection() as conn:
            row = conn.execute("select * from runs where id = %s", (run_id,)).fetchone()
            if row is None:
                return None
            return _run_from_row(row, self._turns(conn, run_id), self._votes(conn, run_id))

    def demo_snapshot(self, scenario_id: str) -> tuple[Scenario, list[RunSummary]] | None:
        with connection() as conn:
            row = conn.execute(
                "select body from scenarios where id = %s", (scenario_id,)
            ).fetchone()
            if row is None:
                return None
            rows = conn.execute(
                "select * from runs where scenario_id = %s "
                "and engine_version = %s and status = 'done' "
                "order by created_at desc limit 40",
                (scenario_id, ENGINE_VERSION),
            ).fetchall()
        return Scenario.model_validate(row["body"]), [_summary_from_row(r) for r in rows]

    def get_run_since(self, run_id: str, since_seq: int) -> RunState | None:
        with connection() as conn:
            row = conn.execute("select * from runs where id = %s", (run_id,)).fetchone()
            if row is None:
                return None
            turns = conn.execute(
                "select * from turns where run_id = %s and seq > %s order by seq",
                (run_id, since_seq),
            ).fetchall()
            return _run_from_row(row, [_turn_from_row(r) for r in turns], self._votes(conn, run_id))

    def list_runs(
        self,
        batch_id: str | None = None,
        is_demo: bool | None = None,
        scenario_id: str | None = None,
    ) -> list[RunSummary]:
        clauses: list[str] = []
        params: list[Any] = []
        if batch_id is not None:
            clauses.append("batch_id = %s")
            params.append(batch_id)
        if scenario_id is not None:
            clauses.append("scenario_id = %s")
            params.append(scenario_id)
        if is_demo is not None:
            clauses.append("is_demo = %s")
            params.append(is_demo)
        where = f" where {' and '.join(clauses)}" if clauses else ""
        with connection() as conn:
            rows = conn.execute(
                f"select * from runs{where} order by created_at desc", params
            ).fetchall()
        return [_summary_from_row(r) for r in rows]

    def turn_exists(self, run_id: str, seq: int) -> bool:
        with connection() as conn:
            return (
                conn.execute(
                    "select 1 from turns where run_id = %s and seq = %s",
                    (run_id, seq),
                ).fetchone()
                is not None
            )

    def insert_turn(self, run_id: str, turn: Turn) -> bool:
        with connection() as conn:
            cur = conn.execute(
                "insert into turns (run_id, seq, round, agent_id, sentences, cited, "
                "hallucinated, lean, confidence, latency_ms, input_tokens, output_tokens, "
                "heard_before) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "on conflict (run_id, seq) do nothing",
                (
                    run_id,
                    turn.seq,
                    turn.round,
                    turn.agent_id,
                    Jsonb(turn.sentences),
                    Jsonb(turn.cited),
                    Jsonb(turn.hallucinated),
                    turn.lean,
                    turn.confidence,
                    turn.latency_ms,
                    turn.input_tokens,
                    turn.output_tokens,
                    Jsonb(turn.heard_before),
                ),
            )
            return cur.rowcount == 1

    def insert_vote(self, run_id: str, vote: Vote) -> None:
        with connection() as conn:
            conn.execute(
                "insert into votes (run_id, round, agent_id, choice, confidence, reason, said_lean) "
                "values (%s, %s, %s, %s, %s, %s, %s) "
                "on conflict (run_id, round, agent_id) do nothing",
                (
                    run_id,
                    vote.round,
                    vote.agent_id,
                    vote.choice,
                    vote.confidence,
                    vote.reason,
                    vote.said_lean,
                ),
            )

    def set_status(
        self,
        run_id: str,
        status: RunStatus,
        current_round: int | None = None,
        error: str | None = None,
    ) -> None:
        with connection() as conn:
            conn.execute(
                "update runs set status = %s, current_round = coalesce(%s, current_round), "
                "error = coalesce(%s, error), updated_at = now() where id = %s",
                (status, current_round, error, run_id),
            )

    def finish_run(self, run_id: str, metrics: Metrics) -> None:
        with connection() as conn:
            conn.execute(
                "update runs set status = 'done', metrics = %s, updated_at = now() where id = %s",
                (Jsonb(metrics.model_dump(by_alias=True)), run_id),
            )

    def delete_demo_runs(self) -> int:
        with connection() as conn:
            cur = conn.execute("delete from runs where is_demo")
            return cur.rowcount

    def delete_stale_demo_runs(self, engine_version: str) -> int:
        with connection() as conn:
            cur = conn.execute(
                "delete from runs where is_demo and engine_version <> %s",
                (engine_version,),
            )
            return cur.rowcount

    def record_run_requests(self, client_key: str, n: int, window_s: int) -> int:
        with connection() as conn:
            conn.execute(
                "insert into run_requests (client_key) select %s from generate_series(1, %s)",
                (client_key, n),
            )
            conn.execute("delete from run_requests where created_at < now() - interval '1 hour'")
            row = conn.execute(
                "select count(*) from run_requests where client_key = %s "
                "and created_at > now() - make_interval(secs => %s)",
                (client_key, window_s),
            ).fetchone()
            assert row is not None
            return int(row["count"])

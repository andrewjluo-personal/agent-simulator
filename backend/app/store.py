"""Run persistence. `Store` is a Protocol so the orchestrator is testable without
Neon; `MemoryStore` backs local development and tests, `PgStore` (app.db) Neon."""

from __future__ import annotations

from typing import Protocol

from .models import Metrics, RunState, RunStatus, RunSummary, Turn, Vote, summary


class Store(Protocol):
    def create_run(self, run: RunState) -> None: ...
    def get_run(self, run_id: str) -> RunState | None: ...
    def get_run_since(self, run_id: str, since_seq: int) -> RunState | None: ...
    def list_runs(
        self, batch_id: str | None = None, is_demo: bool | None = None
    ) -> list[RunSummary]: ...
    def turn_exists(self, run_id: str, seq: int) -> bool: ...
    def insert_turn(self, run_id: str, turn: Turn) -> bool: ...
    def insert_vote(self, run_id: str, vote: Vote) -> None: ...
    def set_status(
        self,
        run_id: str,
        status: RunStatus,
        current_round: int | None = None,
        error: str | None = None,
    ) -> None: ...
    def finish_run(self, run_id: str, metrics: Metrics) -> None: ...
    def delete_demo_runs(self) -> int: ...


class MemoryStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}

    def create_run(self, run: RunState) -> None:
        self._runs[run.id] = run

    def get_run(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def get_run_since(self, run_id: str, since_seq: int) -> RunState | None:
        run = self._runs.get(run_id)
        if run is None:
            return None
        clone = run.model_copy()
        clone.turns = [t for t in run.turns if t.seq > since_seq]
        return clone

    def list_runs(
        self, batch_id: str | None = None, is_demo: bool | None = None
    ) -> list[RunSummary]:
        runs = sorted(
            self._runs.values(), key=lambda r: r.created_at, reverse=True
        )
        return [
            summary(r)
            for r in runs
            if (batch_id is None or r.batch_id == batch_id)
            and (is_demo is None or r.is_demo == is_demo)
        ]

    def turn_exists(self, run_id: str, seq: int) -> bool:
        run = self._runs[run_id]
        return any(t.seq == seq for t in run.turns)

    def insert_turn(self, run_id: str, turn: Turn) -> bool:
        run = self._runs[run_id]
        if self.turn_exists(run_id, turn.seq):
            return False
        run.turns.append(turn)
        run.turns.sort(key=lambda t: t.seq)
        return True

    def insert_vote(self, run_id: str, vote: Vote) -> None:
        run = self._runs[run_id]
        if any(
            v.round == vote.round and v.agent_id == vote.agent_id for v in run.votes
        ):
            return
        run.votes.append(vote)
        run.votes.sort(key=lambda v: (v.round, v.agent_id))

    def set_status(
        self,
        run_id: str,
        status: RunStatus,
        current_round: int | None = None,
        error: str | None = None,
    ) -> None:
        run = self._runs[run_id]
        run.status = status
        if current_round is not None:
            run.current_round = current_round
        if error is not None:
            run.error = error

    def finish_run(self, run_id: str, metrics: Metrics) -> None:
        run = self._runs[run_id]
        run.metrics = metrics
        run.status = "done"

    def delete_demo_runs(self) -> int:
        doomed = [rid for rid, r in self._runs.items() if r.is_demo]
        for rid in doomed:
            del self._runs[rid]
        return len(doomed)

"""Run persistence. `Store` is a Protocol so the orchestrator is testable without
Neon; `MemoryStore` backs local development and tests, `PgStore` (app.db) Neon."""

from __future__ import annotations

from typing import Protocol

from .engine_version import ENGINE_VERSION
from .models import (
    Metrics,
    RunState,
    RunStatus,
    RunSummary,
    Scenario,
    Turn,
    ValidationJob,
    Vote,
    summary,
)


class Store(Protocol):
    def list_scenarios(self) -> list[Scenario]: ...
    def get_scenario(self, scenario_id: str) -> Scenario | None: ...
    def upsert_scenario(self, scenario: Scenario) -> None: ...
    def upsert_validation_job(self, job: ValidationJob) -> None: ...
    def get_validation_job(self, job_id: str) -> ValidationJob | None: ...
    def latest_validation_job(self, scenario_id: str) -> ValidationJob | None: ...
    def create_run(self, run: RunState) -> None: ...
    def get_run(self, run_id: str) -> RunState | None: ...
    def get_run_since(self, run_id: str, since_seq: int) -> RunState | None: ...
    def demo_snapshot(self, scenario_id: str) -> tuple[Scenario, list[RunSummary]] | None: ...
    def list_runs(
        self,
        batch_id: str | None = None,
        is_demo: bool | None = None,
        scenario_id: str | None = None,
    ) -> list[RunSummary]: ...
    def turn_exists(self, run_id: str, seq: int) -> bool: ...
    def delete_stale_demo_runs(self, engine_version: str) -> int: ...
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
        self._scenarios: dict[str, Scenario] = {}
        self._validation_jobs: dict[str, ValidationJob] = {}
        from .samples import SAMPLE_SCENARIOS

        for sample in SAMPLE_SCENARIOS:
            self._scenarios[sample.id] = sample

    def list_scenarios(self) -> list[Scenario]:
        return list(self._scenarios.values())

    def get_scenario(self, scenario_id: str) -> Scenario | None:
        return self._scenarios.get(scenario_id)

    def upsert_scenario(self, scenario: Scenario) -> None:
        self._scenarios[scenario.id] = scenario

    def upsert_validation_job(self, job: ValidationJob) -> None:
        self._validation_jobs[job.id] = job

    def get_validation_job(self, job_id: str) -> ValidationJob | None:
        return self._validation_jobs.get(job_id)

    def latest_validation_job(self, scenario_id: str) -> ValidationJob | None:
        jobs = [j for j in self._validation_jobs.values() if j.scenario_id == scenario_id]
        return max(jobs, key=lambda j: j.updated_at) if jobs else None

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

    def demo_snapshot(self, scenario_id: str) -> tuple[Scenario, list[RunSummary]] | None:
        scenario = self._scenarios.get(scenario_id)
        if scenario is None:
            return None
        return scenario, [
            s
            for s in self.list_runs(is_demo=True, scenario_id=scenario_id)
            if s.engine_version == ENGINE_VERSION
        ][:100]

    def list_runs(
        self,
        batch_id: str | None = None,
        is_demo: bool | None = None,
        scenario_id: str | None = None,
    ) -> list[RunSummary]:
        runs = sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)
        return [
            summary(r)
            for r in runs
            if (batch_id is None or r.batch_id == batch_id)
            and (is_demo is None or r.is_demo == is_demo)
            and (scenario_id is None or r.scenario_id == scenario_id)
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
        if any(v.round == vote.round and v.agent_id == vote.agent_id for v in run.votes):
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

    def delete_stale_demo_runs(self, engine_version: str) -> int:
        doomed = [
            rid for rid, r in self._runs.items() if r.is_demo and r.engine_version != engine_version
        ]
        for rid in doomed:
            del self._runs[rid]
        return len(doomed)

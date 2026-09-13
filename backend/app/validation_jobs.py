"""Background validation jobs and discussion batch finalization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from statistics import mean

from . import orchestrator, validator
from .llm import LLMClient
from .models import RunConfig, ValidationJob
from .store import Store


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def run_job(
    store: Store,
    client: LLMClient,
    job_id: str,
    start_run: Callable[[str], Awaitable[None]],
) -> ValidationJob:
    job = store.get_validation_job(job_id)
    if job is None:
        raise KeyError(f"unknown validation job {job_id!r}")
    scenario = store.get_scenario(job.scenario_id)
    if scenario is None:
        job.status = "error"
        job.error = f"unknown scenario {job.scenario_id!r}"
        job.updated_at = _now()
        store.upsert_validation_job(job)
        return job
    job.status = "running"
    job.updated_at = _now()
    store.upsert_validation_job(job)
    try:
        job.result = await validator.validate_scenario(
            scenario, client, model=job.model, trials=job.trials
        )
        if job.discussion_runs > 0:
            job.batch_id = job.id
            for i in range(job.discussion_runs):
                run = orchestrator.new_run(
                    store,
                    RunConfig(
                        scenario_id=job.scenario_id,
                        paradigm="free_discussion",
                        model=job.model,
                        seed=i,
                    ),
                    provider=client.provider,
                    batch_id=job.id,
                )
                store.create_run(run)
                await start_run(run.id)
            job.updated_at = _now()
            store.upsert_validation_job(job)
            return job
        scenario.validation = dict(scenario.validation or {})
        scenario.validation[job.model] = job.result
        store.upsert_scenario(scenario)
        job.status = "done"
    except Exception as exc:  # noqa: BLE001 - persist worker failures
        job.status = "error"
        job.error = str(exc)
    job.updated_at = _now()
    store.upsert_validation_job(job)
    return job


def finalize_if_ready(store: Store, job: ValidationJob) -> ValidationJob:
    if job.status != "running" or job.result is None or job.batch_id is None:
        return job
    runs = store.list_runs(batch_id=job.batch_id)
    if len(runs) != job.discussion_runs or not all(r.status in ("done", "error") for r in runs):
        return job
    done = [r for r in runs if r.status == "done"]
    rate = mean(1.0 if r.metrics and r.metrics.correct else 0.0 for r in done) if done else 0.0
    job.result.free_discussion_rate = rate
    job.result.free_discussion_runs = len(done)
    job.status = "done"
    scenario = store.get_scenario(job.scenario_id)
    if scenario is not None:
        scenario.validation = dict(scenario.validation or {})
        scenario.validation[job.model] = job.result
        store.upsert_scenario(scenario)
    job.updated_at = _now()
    store.upsert_validation_job(job)
    return job

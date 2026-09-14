from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

os.environ["LLM_PROVIDER"] = "fake"
os.environ["RUN_MODE"] = "sync"
os.environ.pop("DATABASE_URL", None)

import pytest
from fastapi.testclient import TestClient

from app import main, validation_jobs
from app.main import app, reset_state
from app.models import ValidationJob

client = TestClient(app)
SID = "hiring-panel-flat-v2"


def test_analysis_and_stateless_analyze() -> None:
    reset_state()
    response = client.get(f"/api/scenarios/{SID}/analysis")
    assert response.status_code == 200
    assert response.json()["flipK"] > 0
    assert client.get("/api/scenarios/unknown/analysis").status_code == 404

    body = client.get(f"/api/scenarios/{SID}").json()
    body["title"] = "Modified only for analysis"
    analyzed = client.post("/api/scenarios/analyze", json=body)
    assert analyzed.status_code == 200
    assert client.get(f"/api/scenarios/{SID}").json()["title"] != body["title"]


def test_fork_and_validate_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_state()
    monkeypatch.setattr(main, "VALIDATE_RATE_LIMIT_PER_HOUR", 0)
    monkeypatch.setattr(main, "FORK_RATE_LIMIT_PER_HOUR", 0)
    base = client.get(f"/api/scenarios/{SID}").json()
    fork = client.post("/api/scenarios", json={"baseId": SID, "scenario": base})
    assert fork.status_code == 201
    forked = fork.json()
    assert forked["id"] == "hiring-panel-flat-v4"  # v3 is a seeded sample
    assert forked["parentId"] == SID
    assert forked["isSample"] is False
    assert forked["source"]["kind"] == "custom"
    assert forked["source"]["fidelity"] == "modified"
    assert forked["validation"] is None
    assert client.get(f"/api/scenarios/{SID}").json() == base

    fork_again = client.post("/api/scenarios", json={"baseId": SID, "scenario": base})
    assert fork_again.status_code == 201
    assert fork_again.json()["id"] == "hiring-panel-flat-v5"
    slug = client.post(
        "/api/scenarios",
        json={"baseId": SID, "slug": "custom-panel", "scenario": base},
    )
    assert slug.status_code == 201
    assert (
        client.post(
            "/api/scenarios",
            json={"baseId": SID, "slug": "INVALID", "scenario": base},
        ).status_code
        == 422
    )

    async def leave_running(store: Any, client: Any, job_id: str, start_run: Any) -> Any:
        job = store.get_validation_job(job_id)
        assert job is not None
        job.status = "running"
        store.upsert_validation_job(job)
        return job

    monkeypatch.setattr("app.main.validation_jobs.run_job", leave_running)
    monkeypatch.setenv("RUN_MODE", "inline")
    pending = client.post(f"/api/scenarios/{SID}/validate")
    assert pending.status_code == 202
    assert client.post(f"/api/scenarios/{SID}/validate").status_code == 409
    monkeypatch.undo()
    monkeypatch.setenv("RUN_MODE", "sync")
    reset_state()
    done = client.post(f"/api/scenarios/{SID}/validate")
    assert done.status_code == 202
    job = done.json()
    assert job["status"] == "done"
    assert job["result"]["pooledRightRate"] is not None
    assert client.get(f"/api/scenarios/{SID}").json()["validation"] is not None

    discussion = client.post(f"/api/scenarios/{SID}/validate?discussion=true")
    assert discussion.status_code == 202
    job = discussion.json()
    for _ in range(3):
        job = client.get(f"/api/validation-jobs/{job['id']}").json()
        if job["status"] == "done":
            break
    assert job["status"] == "done"
    assert job["result"]["freeDiscussionRuns"] == 10


async def _finish_validation(store: Any, client: Any, job_id: str, start_run: Any) -> Any:
    job = store.get_validation_job(job_id)
    assert job is not None
    job.status = "done"
    store.upsert_validation_job(job)
    return job


def test_validation_hourly_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_state()
    monkeypatch.setattr(main, "VALIDATE_RATE_LIMIT_PER_HOUR", 2)
    monkeypatch.setattr(main, "FORK_RATE_LIMIT_PER_HOUR", 0)
    monkeypatch.setattr(validation_jobs, "run_job", _finish_validation)
    headers = {"x-forwarded-for": "203.0.113.50"}
    for scenario_id in ("hiring-panel-flat-v2", "stasser-1985-hidden"):
        response = client.post(f"/api/scenarios/{scenario_id}/validate", headers=headers)
        assert response.status_code == 202
    response = client.post(
        "/api/scenarios/hiddenbench-company-acquisition-decision/validate",
        headers=headers,
    )
    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Too many validations started from this address in the last hour — limit is 2/hour."
    )


def test_validation_global_single_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_state()
    monkeypatch.setattr(main, "VALIDATE_RATE_LIMIT_PER_HOUR", 0)
    store = main.get_store()
    now = datetime.now(UTC).isoformat()
    other_id = "stasser-1985-hidden"
    store.upsert_validation_job(
        ValidationJob(
            id="global-active",
            scenario_id=other_id,
            model="fake",
            status="queued",
            trials=10,
            discussion_runs=0,
            created_at=now,
            updated_at=now,
        )
    )
    response = client.post(f"/api/scenarios/{SID}/validate")
    assert response.status_code == 429
    assert other_id in response.json()["detail"]


def test_stale_validation_job_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_state()
    monkeypatch.setattr(main, "VALIDATE_RATE_LIMIT_PER_HOUR", 0)
    monkeypatch.setattr(validation_jobs, "run_job", _finish_validation)
    old = (datetime.now(UTC) - timedelta(minutes=main.VALIDATION_JOB_STALE_MIN + 1)).isoformat()
    store = main.get_store()
    store.upsert_validation_job(
        ValidationJob(
            id="stale-job",
            scenario_id=SID,
            model="fake",
            status="queued",
            trials=10,
            discussion_runs=0,
            created_at=old,
            updated_at=old,
        )
    )
    response = client.post(f"/api/scenarios/{SID}/validate")
    assert response.status_code == 202


def test_fork_hourly_limit_and_forwarded_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_state()
    monkeypatch.setattr(main, "FORK_RATE_LIMIT_PER_HOUR", 10)
    base = client.get(f"/api/scenarios/{SID}").json()
    headers = {"x-forwarded-for": "203.0.113.60"}
    for n in range(10):
        response = client.post(
            "/api/scenarios",
            json={"baseId": SID, "slug": f"limited-{n}", "scenario": base},
            headers=headers,
        )
        assert response.status_code == 201
    blocked = client.post(
        "/api/scenarios",
        json={"baseId": SID, "slug": "limited-blocked", "scenario": base},
        headers=headers,
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == (
        "Too many scenarios saved from this address in the last hour — limit is 10/hour."
    )
    allowed = client.post(
        "/api/scenarios",
        json={"baseId": SID, "slug": "limited-other-ip", "scenario": base},
        headers={"x-forwarded-for": "203.0.113.61"},
    )
    assert allowed.status_code == 201


def test_custom_scenario_picker_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_state()
    monkeypatch.setattr(main, "FORK_RATE_LIMIT_PER_HOUR", 0)
    monkeypatch.setattr(main, "CUSTOM_SCENARIOS_LISTED", 2)
    base = client.get(f"/api/scenarios/{SID}").json()
    created: list[dict[str, Any]] = []
    for slug in ("picker-one", "picker-two", "picker-three"):
        response = client.post(
            "/api/scenarios",
            json={"baseId": SID, "slug": slug, "scenario": base},
        )
        assert response.status_code == 201
        created.append(response.json())
    listed = client.get("/api/scenarios")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert all(
        s["source"]["kind"] != "custom" for s in listed_body if s["id"] == "hiring-panel-flat-v2"
    )
    custom_ids = {s["id"] for s in listed_body if s["source"]["kind"] == "custom"}
    newest = {s["id"] for s in sorted(created, key=lambda s: s["createdAt"], reverse=True)[:2]}
    assert custom_ids == newest

from __future__ import annotations

import os
from typing import Any

os.environ["LLM_PROVIDER"] = "fake"
os.environ["RUN_MODE"] = "sync"
os.environ.pop("DATABASE_URL", None)

import pytest
from fastapi.testclient import TestClient

from app.main import app, reset_state

client = TestClient(app)
SID = "hiring-panel-v1"


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
    base = client.get(f"/api/scenarios/{SID}").json()
    fork = client.post("/api/scenarios", json={"baseId": SID, "scenario": base})
    assert fork.status_code == 201
    forked = fork.json()
    assert forked["id"] == "hiring-panel-v2"
    assert forked["parentId"] == SID
    assert forked["isSample"] is False
    assert forked["source"]["kind"] == "custom"
    assert forked["source"]["fidelity"] == "modified"
    assert forked["validation"] is None
    assert client.get(f"/api/scenarios/{SID}").json() == base

    fork_again = client.post("/api/scenarios", json={"baseId": SID, "scenario": base})
    assert fork_again.status_code == 201
    assert fork_again.json()["id"] == "hiring-panel-v3"
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

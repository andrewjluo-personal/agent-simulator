from __future__ import annotations

import os

os.environ["LLM_PROVIDER"] = "fake"
os.environ["RUN_MODE"] = "sync"
os.environ.pop("DATABASE_URL", None)
os.environ["RUN_RATE_LIMIT_PER_MIN"] = "0"

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_run_rate_limit_blocks_seventh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "RUN_RATE_LIMIT_PER_MIN", 6)
    headers = {"x-forwarded-for": "203.0.113.10"}
    codes = [
        client.post("/api/runs", json={"rounds": 1}, headers=headers).status_code for _ in range(7)
    ]
    assert codes == [201] * 6 + [429]
    resp = client.post("/api/runs", json={"rounds": 1}, headers=headers)
    assert resp.status_code == 429
    assert "Too many runs" in resp.json()["detail"]
    other = client.post(
        "/api/runs", json={"rounds": 1}, headers={"x-forwarded-for": "203.0.113.11"}
    )
    assert other.status_code == 201


def test_run_rate_limit_disabled_when_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "RUN_RATE_LIMIT_PER_MIN", 0)
    headers = {"x-forwarded-for": "203.0.113.20"}
    for _ in range(8):
        resp = client.post("/api/runs", json={"rounds": 1}, headers=headers)
        assert resp.status_code == 201


def test_demo_lists_recent_finished_runs() -> None:
    store = main.get_store()
    from app import orchestrator
    from app.engine_version import ENGINE_VERSION
    from app.models import RunConfig

    done = orchestrator.new_run(store, RunConfig(rounds=1, seed=91), provider="fake")
    done.status = "done"
    running = orchestrator.new_run(store, RunConfig(rounds=1, seed=92), provider="fake")
    stale = orchestrator.new_run(store, RunConfig(rounds=1, seed=93), provider="fake")
    stale.engine_version = "old"
    stale.status = "done"
    for r in (done, running, stale):
        store.create_run(r)

    resp = client.get("/api/demo?scenarioId=stasser-1985-hidden")
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["runs"]}
    assert done.id in ids
    assert running.id not in ids
    assert stale.id not in ids
    assert ENGINE_VERSION == resp.json()["engineVersion"]


def test_auto_run_on_load_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/api/health").json()["autoRunOnLoad"] is True
    assert client.get("/api/demo?scenarioId=stasser-1985-hidden").json()["autoRunOnLoad"] is True
    monkeypatch.setattr(main, "AUTO_RUN_ON_LOAD", False)
    assert client.get("/api/health").json()["autoRunOnLoad"] is False

from __future__ import annotations

import os
import time

os.environ["LLM_PROVIDER"] = "fake"
os.environ["RUN_MODE"] = "sync"
os.environ.pop("VERCEL_OIDC_TOKEN", None)
os.environ.pop("DATABASE_URL", None)
os.environ["RUN_RATE_LIMIT_PER_MIN"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app, reset_state
from app.models import RunConfig
from app.orchestrator import new_run
from app.store import MemoryStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_run_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_state()
    monkeypatch.delenv("RUN_MODE", raising=False)
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)


def test_created_run_stays_queued_then_steps_to_done() -> None:
    resp = client.post("/api/runs", json={"rounds": 1, "seed": 3})
    assert resp.status_code == 201
    run = resp.json()
    assert run["status"] == "queued"
    assert run["currentRound"] == 0

    stepped = client.post(f"/api/runs/{run['id']}/step")
    assert stepped.status_code == 200
    body = stepped.json()
    assert body["currentRound"] == 1
    assert body["status"] == "done"  # rounds=1 -> one step finishes the run

    again = client.post(f"/api/runs/{run['id']}/step")
    assert again.status_code == 200
    assert again.json()["status"] == "done"
    assert again.json()["currentRound"] == 1


def test_step_advances_one_round_per_call() -> None:
    run = client.post("/api/runs", json={"rounds": 3, "seed": 3}).json()
    for expected in (1, 2, 3):
        body = client.post(f"/api/runs/{run['id']}/step").json()
        assert body["currentRound"] == expected
        assert body["status"] == ("running" if expected < 3 else "done")
    assert len(body["turns"]) == 3 * len(run["scenario"]["agents"])


def test_step_since_seq_filters_turns() -> None:
    run = client.post("/api/runs", json={"rounds": 2, "seed": 3}).json()
    first = client.post(f"/api/runs/{run['id']}/step").json()
    seen = {t["seq"] for t in first["turns"]}
    delta = client.post(
        f"/api/runs/{run['id']}/step", params={"since_seq": max(seen)}
    ).json()
    assert all(t["seq"] > max(seen) for t in delta["turns"])
    assert len(delta["turns"]) == len(run["scenario"]["agents"])


def test_step_unknown_run_is_404() -> None:
    assert client.post("/api/runs/nope/step").status_code == 404


def test_memory_claim_round_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryStore()
    run = new_run(store, RunConfig(rounds=2), provider="fake")
    store.create_run(run)

    assert store.claim_round(run.id, 0, 90)
    assert not store.claim_round(run.id, 0, 90)  # same round still leased

    store.set_status(run.id, "running", current_round=1)
    assert store.claim_round(run.id, 1, 90)  # next round is claimable

    clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    other = new_run(store, RunConfig(rounds=2), provider="fake")
    store.create_run(other)
    assert store.claim_round(other.id, 0, 90)
    clock[0] += 200.0  # lease expired
    assert store.claim_round(other.id, 0, 90)


def test_batch_step_advances_one_run_per_call() -> None:
    resp = client.post("/api/runs/batch", json={"config": {"rounds": 2}, "n": 2})
    assert resp.status_code == 201
    batch = resp.json()
    assert all(r["status"] == "queued" for r in batch["runs"])

    stepped = client.post(f"/api/batches/{batch['id']}/step").json()
    assert sum(r["currentRound"] for r in stepped["runs"]) == 1

    stepped = client.post(f"/api/batches/{batch['id']}/step").json()
    advanced = [r for r in stepped["runs"] if r["currentRound"] > 0]
    assert sum(r["currentRound"] for r in stepped["runs"]) == 2
    assert len(advanced) >= 1

    assert client.post("/api/batches/nope/step").status_code == 404

from __future__ import annotations

import os

os.environ["LLM_PROVIDER"] = "fake"
os.environ["RUN_MODE"] = "sync"
os.environ.pop("DATABASE_URL", None)

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_scenario_endpoint() -> None:
    resp = client.get("/api/scenario")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["id"] == "john"


def test_paradigms_endpoint() -> None:
    resp = client.get("/api/paradigms")
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert ids == {"free_discussion", "share_first"}


def test_run_lifecycle_sync() -> None:
    resp = client.post("/api/runs", json={"rounds": 1, "seed": 3})
    assert resp.status_code == 201
    run = resp.json()
    assert run["status"] == "done"  # RUN_MODE=sync awaited completion
    assert len(run["turns"]) == 4
    assert run["metrics"]["correctCandidateId"] == "sally"

    got = client.get(f"/api/runs/{run['id']}")
    assert got.status_code == 200
    since = client.get(f"/api/runs/{run['id']}", params={"since_seq": 2})
    assert since.status_code == 200
    assert all(t["seq"] > 2 for t in since.json()["turns"])
    assert client.get("/api/runs/nope").status_code == 404


def test_batch() -> None:
    resp = client.post("/api/runs/batch", json={"config": {"rounds": 1}, "n": 3})
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["runs"]) == 3
    batch = client.get(f"/api/batches/{body['id']}")
    assert batch.status_code == 200
    assert len(batch.json()["runs"]) == 3

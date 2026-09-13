from __future__ import annotations

import os

os.environ["LLM_PROVIDER"] = "fake"
os.environ["RUN_MODE"] = "sync"
os.environ.pop("DATABASE_URL", None)

from fastapi.testclient import TestClient

from app.main import app, get_store

client = TestClient(app)
SID = "hiring-panel-v1"


def test_list_and_get_scenarios() -> None:
    resp = client.get("/api/scenarios")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert SID in ids
    one = client.get(f"/api/scenarios/{SID}")
    assert one.status_code == 200
    assert one.json()["isSample"] is True
    assert client.get("/api/scenarios/nope").status_code == 404


def test_reset_restores_sample() -> None:
    store = get_store()
    original = store.get_scenario(SID)
    assert original is not None
    mutated = original.model_copy(update={"title": "MUTATED"})
    store.upsert_scenario(mutated)
    assert client.get(f"/api/scenarios/{SID}").json()["title"] == "MUTATED"
    resp = client.post(f"/api/scenarios/{SID}/reset")
    assert resp.status_code == 200
    assert resp.json()["title"] == original.title
    assert client.get(f"/api/scenarios/{SID}").json()["title"] == original.title
    assert client.post("/api/scenarios/nope/reset").status_code == 404


def test_demo_scenario_filter() -> None:
    resp = client.get("/api/demo")
    assert resp.status_code == 200
    assert resp.json()["scenario"]["id"] == SID
    filtered = client.get("/api/demo", params={"scenarioId": SID})
    assert filtered.status_code == 200
    assert all(r["scenarioId"] == SID for r in filtered.json()["runs"])
    assert client.get("/api/demo", params={"scenarioId": "nope"}).status_code == 404


def test_run_unknown_scenario_404() -> None:
    resp = client.post("/api/runs", json={"scenarioId": "nope"})
    assert resp.status_code == 404
    resp = client.post("/api/runs/batch", json={"config": {"scenarioId": "nope"}, "n": 2})
    assert resp.status_code == 404

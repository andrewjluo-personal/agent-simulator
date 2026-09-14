from __future__ import annotations

import importlib

from app import orchestrator
from app.engine_version import ENGINE_VERSION
from app.models import RunConfig
from app.store import MemoryStore


def test_engine_version_is_12_hex_and_stable() -> None:
    assert len(ENGINE_VERSION) == 12
    int(ENGINE_VERSION, 16)
    import app.engine_version as ev

    assert importlib.reload(ev).ENGINE_VERSION == ENGINE_VERSION


def test_new_run_stamps_engine_version() -> None:
    store = MemoryStore()
    run = orchestrator.new_run(store, RunConfig(), provider="fake")
    assert run.engine_version == ENGINE_VERSION


def test_demo_snapshot_filters_stale_versions() -> None:
    store = MemoryStore()
    fresh = orchestrator.new_run(store, RunConfig(), provider="fake", is_demo=True)
    fresh.status = "done"
    stale = fresh.model_copy(deep=True, update={"id": "stale-id", "engine_version": "old"})
    store.create_run(fresh)
    store.create_run(stale)
    snap = store.demo_snapshot("hiring-panel-flat-v2")
    assert snap is not None
    ids = [s.id for s in snap[1]]
    assert fresh.id in ids and "stale-id" not in ids

    assert store.delete_stale_demo_runs(ENGINE_VERSION) == 1
    snap = store.demo_snapshot("hiring-panel-flat-v2")
    assert snap is not None
    ids = [s.id for s in snap[1]]
    assert ids == [fresh.id]
    # non-demo runs are never touched
    live = fresh.model_copy(deep=True, update={"id": "live-id", "is_demo": False})
    live.engine_version = "old"
    store.create_run(live)
    assert store.delete_stale_demo_runs(ENGINE_VERSION) == 0
    assert store.get_run("live-id") is not None

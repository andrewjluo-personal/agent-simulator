from __future__ import annotations

import importlib

from app import orchestrator
from app.engine_version import ENGINE_VERSION, scenario_engine_version
from app.models import RunConfig
from app.samples import SAMPLE_SCENARIOS, SAMPLES_BY_ID
from app.store import MemoryStore

SID = "stasser-1985-hidden"


def test_engine_version_is_12_hex_and_stable() -> None:
    assert len(ENGINE_VERSION) == 12
    int(ENGINE_VERSION, 16)
    import app.engine_version as ev

    assert importlib.reload(ev).ENGINE_VERSION == ENGINE_VERSION


def test_scenario_engine_version_is_12_hex_and_stable() -> None:
    scenario = SAMPLES_BY_ID[SID]
    stamp = scenario_engine_version(scenario)
    assert len(stamp) == 12
    int(stamp, 16)
    assert scenario_engine_version(scenario) == stamp


def test_scenario_engine_version_tracks_scenario_content() -> None:
    scenario = SAMPLES_BY_ID[SID]
    changed_fact = scenario.model_copy(deep=True)
    changed_fact.facts[0].text = f"{changed_fact.facts[0].text} (edited)"
    assert scenario_engine_version(changed_fact) != scenario_engine_version(scenario)

    changed_validation = scenario.model_copy(deep=True)
    changed_validation.validation = {
        "fake": {
            "aloneWrongRate": {},
            "pooledRightRate": 0.0,
            "trials": 1,
            "date": "2026-01-01",
            "passed": True,
        }
    }
    assert scenario_engine_version(changed_validation) == scenario_engine_version(scenario)

    other = next(s for s in SAMPLE_SCENARIOS if s.id != SID)
    assert scenario_engine_version(other) != scenario_engine_version(scenario)


def test_new_run_stamps_scenario_engine_version() -> None:
    store = MemoryStore()
    run = orchestrator.new_run(store, RunConfig(), provider="fake")
    assert run.engine_version == scenario_engine_version(run.scenario)


def test_demo_snapshot_filters_stale_versions() -> None:
    store = MemoryStore()
    fresh = orchestrator.new_run(store, RunConfig(), provider="fake", is_demo=True)
    fresh.status = "done"
    stale = fresh.model_copy(deep=True, update={"id": "stale-id", "engine_version": "old"})
    store.create_run(fresh)
    store.create_run(stale)
    snap = store.demo_snapshot(SID)
    assert snap is not None
    ids = [s.id for s in snap[1]]
    assert fresh.id in ids and "stale-id" not in ids

    current = {s.id: scenario_engine_version(s) for s in SAMPLE_SCENARIOS}
    assert store.delete_stale_demo_runs(current) == 1
    snap = store.demo_snapshot(SID)
    assert snap is not None
    ids = [s.id for s in snap[1]]
    assert ids == [fresh.id]
    # non-demo runs are never touched
    live = fresh.model_copy(deep=True, update={"id": "live-id", "is_demo": False})
    live.engine_version = "old"
    store.create_run(live)
    assert store.delete_stale_demo_runs(current) == 0
    assert store.get_run("live-id") is not None


def test_delete_stale_demo_runs_mapping_semantics() -> None:
    store = MemoryStore()
    run_a = orchestrator.new_run(store, RunConfig(), provider="fake", is_demo=True)
    other_id = next(s.id for s in SAMPLE_SCENARIOS if s.id != SID)
    run_b = orchestrator.new_run(
        store, RunConfig(scenario_id=other_id), provider="fake", is_demo=True
    )
    store.create_run(run_a)
    store.create_run(run_b)

    # scenario missing from the mapping is treated as stale
    only_a = {run_a.scenario_id: scenario_engine_version(run_a.scenario)}
    assert store.delete_stale_demo_runs(only_a) == 1
    assert store.get_run(run_b.id) is None
    assert store.get_run(run_a.id) is not None

    # mismatched stamp for a known scenario is deleted
    wrong = {run_a.scenario_id: "deadbeefdead"}
    assert store.delete_stale_demo_runs(wrong) == 1
    assert store.get_run(run_a.id) is None

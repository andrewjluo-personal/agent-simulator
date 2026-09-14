"""Scenario loading. Scenarios are store rows seeded from app.samples."""

from __future__ import annotations

from .models import Scenario
from .store import Store

DEFAULT_SCENARIO_ID = "hiring-panel-flat-v2"


def load_scenario(store: Store, scenario_id: str = DEFAULT_SCENARIO_ID) -> Scenario:
    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise KeyError(f"unknown scenario {scenario_id!r}")
    return scenario

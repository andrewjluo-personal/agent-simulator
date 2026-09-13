"""Scenario loading. Scenarios are bundled JSON files under app/scenarios/."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import Scenario

DEFAULT_SCENARIO_ID = "hiring-panel-v1"
SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def scenario_path(scenario_id: str) -> Path:
    return SCENARIOS_DIR / f"{scenario_id.replace('-', '_')}.json"


@lru_cache(maxsize=8)
def load_scenario(scenario_id: str = DEFAULT_SCENARIO_ID) -> Scenario:
    path = scenario_path(scenario_id)
    if path.exists():
        return Scenario.model_validate(json.loads(path.read_text()))
    # file name need not equal the scenario id — scan for a matching "id"
    for candidate in SCENARIOS_DIR.glob("*.json"):
        scenario = Scenario.model_validate(json.loads(candidate.read_text()))
        if scenario.id == scenario_id:
            return scenario
    raise KeyError(f"unknown scenario {scenario_id!r}")

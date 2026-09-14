from __future__ import annotations

import json
from pathlib import Path

from app import truth
from app.scenarios.papers.hiddenbench import convert_task


def test_convert_hiddenbench_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "hiddenbench_task.json"
    scenario = convert_task(json.loads(fixture.read_text()))

    assert scenario.id == "hiddenbench-evacuation-west-city"
    assert len(scenario.candidates) == 3
    assert len(scenario.agents) == 4
    assert len(scenario.facts) == 8
    assert all(len(held) == 5 for held in scenario.distribution.values())
    assert all(fact.weight == 1 for fact in scenario.facts)
    assert all(fact.memo_text for fact in scenario.facts)
    assert scenario.source.fidelity == "verbatim"
    assert truth.pooled_verdict(scenario) == "west-city"

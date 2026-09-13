from __future__ import annotations

import asyncio

from app import validator
from app.llm import FakeClient
from app.models import Scenario
from app.store import MemoryStore


def _sample() -> Scenario:
    scenario = MemoryStore().get_scenario("hiring-panel-v1")
    assert scenario is not None
    return scenario


def test_validate_sample_passes() -> None:
    scenario = _sample()
    result = asyncio.run(
        validator.validate_scenario(scenario, FakeClient(), model="fake", trials=5)
    )
    assert result.passed
    assert result.trials == 5
    assert all(rate >= 0.8 for rate in result.alone_wrong_rate.values())
    assert result.pooled_right_rate >= 0.8


def test_validate_fails_when_a_hand_favors_pooled_winner() -> None:
    scenario = _sample()
    sally_ids = [f.id for f in scenario.facts if f.candidate_id == "sally" and f.valence == "pro"]
    # give dana only the strongest sally evidence -> her alone ballot flips to sally
    bad = scenario.model_copy(
        update={"distribution": {**scenario.distribution, "dana": sally_ids[:5]}}
    )
    result = asyncio.run(validator.validate_scenario(bad, FakeClient(), model="fake", trials=5))
    assert not result.passed
    assert result.alone_wrong_rate["dana"] < 0.8

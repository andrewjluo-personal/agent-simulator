from __future__ import annotations

import asyncio

import pytest

from app import truth, validator
from app.llm import FakeClient
from app.models import Scenario
from app.samples import SAMPLE_SCENARIOS
from app.scenarios.papers import PAPER_SCENARIOS

NON_PAPER_SAMPLE_SCENARIOS = [
    scenario for scenario in SAMPLE_SCENARIOS if scenario.id not in {s.id for s in PAPER_SCENARIOS}
]


@pytest.mark.parametrize("scenario", NON_PAPER_SAMPLE_SCENARIOS, ids=lambda scenario: scenario.id)
def test_sample_is_hidden_profile_and_each_hand_favors_shared_verdict(scenario: Scenario) -> None:
    assert truth.is_hidden_profile(scenario)
    wrong = truth.shared_only_verdict(scenario)
    assert all(truth.verdict(scenario, hand) == wrong for hand in scenario.distribution.values())


def test_sample_ids_are_unique() -> None:
    assert len({scenario.id for scenario in SAMPLE_SCENARIOS}) == len(SAMPLE_SCENARIOS)
    assert SAMPLE_SCENARIOS[0].id == "hiring-panel-v1"


@pytest.mark.parametrize("scenario", SAMPLE_SCENARIOS, ids=lambda scenario: scenario.id)
def test_sample_distribution_round_trips(scenario: Scenario) -> None:
    fact_ids = {fact.id for fact in scenario.facts}
    assert set(scenario.distribution) == {agent.id for agent in scenario.agents}
    assert all(set(held) <= fact_ids for held in scenario.distribution.values())
    round_trip = Scenario.model_validate(scenario.model_dump(by_alias=True))
    assert round_trip == scenario


@pytest.mark.parametrize("scenario", SAMPLE_SCENARIOS, ids=lambda scenario: scenario.id)
def test_sample_facts_have_memo_metadata(scenario: Scenario) -> None:
    assert all(fact.memo_text and 2 <= len(fact.keywords) <= 3 for fact in scenario.facts)


@pytest.mark.parametrize("scenario", NON_PAPER_SAMPLE_SCENARIOS, ids=lambda scenario: scenario.id)
def test_sample_passes_fake_validation(scenario: Scenario) -> None:
    result = asyncio.run(
        validator.validate_scenario(scenario, FakeClient(), model="fake", trials=3)
    )
    assert result.passed

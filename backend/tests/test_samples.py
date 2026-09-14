from __future__ import annotations

import asyncio

import pytest

from app import truth, validator
from app.llm import FakeClient
from app.models import Scenario
from app.samples import HIRING_PANEL_NULL, SAMPLE_SCENARIOS, ensure_samples
from app.scenarios.papers import PAPER_SCENARIOS

# hiring-panel-null is a zero-margin bias control, deliberately not a hidden profile.
NON_PAPER_SAMPLE_SCENARIOS = [
    scenario
    for scenario in SAMPLE_SCENARIOS
    if scenario.id not in {s.id for s in PAPER_SCENARIOS} and scenario is not HIRING_PANEL_NULL
]


def test_null_pool_is_symmetric() -> None:
    s = HIRING_PANEL_NULL
    assert truth.scores(s, truth.pooled_fact_ids(s)) == {"john": 0, "sally": 0}
    by_cand = {
        c.id: sorted(f.memo_text or f.text for f in s.facts if f.candidate_id == c.id)
        for c in s.candidates
    }
    assert len(by_cand["john"]) == len(by_cand["sally"]) == len(s.facts) // 2
    for hand in s.distribution.values():
        assert truth.scores(s, hand) == {"john": 0, "sally": 0}
        assert sum(s.fact(i).candidate_id == "john" for i in hand) == len(hand) // 2


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


class _StubStore:
    def __init__(self, scenarios: list[Scenario] | None = None) -> None:
        self._scenarios = {s.id: s for s in scenarios or []}
        self.upserted: list[str] = []

    def list_scenarios(self) -> list[Scenario]:
        return list(self._scenarios.values())

    def get_scenario(self, scenario_id: str) -> Scenario | None:
        return self._scenarios.get(scenario_id)

    def upsert_scenario(self, scenario: Scenario) -> None:
        self._scenarios[scenario.id] = scenario
        self.upserted.append(scenario.id)


def test_ensure_samples_inserts_missing() -> None:
    store = _StubStore()
    assert ensure_samples(store) == len(SAMPLE_SCENARIOS)  # type: ignore[arg-type]
    assert {s.id for s in store.list_scenarios()} == {s.id for s in SAMPLE_SCENARIOS}


def test_ensure_samples_leaves_identical_rows_untouched() -> None:
    store = _StubStore(list(SAMPLE_SCENARIOS))
    assert ensure_samples(store) == 0  # type: ignore[arg-type]
    assert store.upserted == []


def test_ensure_samples_overwrites_stale_rows() -> None:
    stale = SAMPLE_SCENARIOS[0].model_copy(update={"title": "stale"})
    custom = Scenario.model_validate(
        {**SAMPLE_SCENARIOS[0].model_dump(by_alias=True), "id": "custom-1", "isSample": False}
    )
    store = _StubStore([stale, *SAMPLE_SCENARIOS[1:], custom])
    assert ensure_samples(store) == 1  # type: ignore[arg-type]
    assert store.upserted == [stale.id]
    assert store.get_scenario(stale.id) == SAMPLE_SCENARIOS[0]
    assert store.get_scenario("custom-1") == custom

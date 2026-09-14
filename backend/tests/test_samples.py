from __future__ import annotations

import asyncio
from collections import Counter

import pytest

from app import prompts, truth, validator
from app.llm import FakeClient
from app.models import RunConfig, Scenario
from app.samples import (
    FLAT_V3_TYPE,
    HIRING_PANEL_FLAT_V2,
    HIRING_PANEL_FLAT_V3,
    HIRING_PANEL_FLAT_V3_NULL,
    HIRING_PANEL_NULL,
    SAMPLE_SCENARIOS,
    ensure_samples,
)
from app.scenarios.papers import PAPER_SCENARIOS

NULL_POOLS = [HIRING_PANEL_NULL, HIRING_PANEL_FLAT_V3_NULL]

# null pools are zero-margin bias controls, deliberately not hidden profiles.
NON_PAPER_SAMPLE_SCENARIOS = [
    scenario
    for scenario in SAMPLE_SCENARIOS
    if scenario.id not in {s.id for s in PAPER_SCENARIOS}
    and all(scenario is not n for n in NULL_POOLS)
]


@pytest.mark.parametrize("s", NULL_POOLS, ids=lambda s: s.id)
def test_null_pool_is_symmetric(s: Scenario) -> None:
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
    assert SAMPLE_SCENARIOS[0].id == "hiring-panel-flat-v2"


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

    def delete_scenario(self, scenario_id: str) -> bool:
        scenario = self._scenarios.pop(scenario_id, None)
        return scenario is not None


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


def test_hiring_panel_samples_have_four_panelists() -> None:
    for s in (
        HIRING_PANEL_FLAT_V2,
        HIRING_PANEL_NULL,
        HIRING_PANEL_FLAT_V3,
        HIRING_PANEL_FLAT_V3_NULL,
    ):
        assert [a.id for a in s.agents] == ["dana", "marcus", "priya", "tom"]
        cfg = RunConfig()  # balanced candidate order, seed 0
        split = Counter(prompts.resolve_candidate_order(s, cfg, a) for a in s.agents)
        assert split == Counter({"fixed": 2, "reversed": 2})
        assert prompts.resolve_candidate_order(s, cfg, None) == "fixed"
    assert truth.shared_only_verdict(HIRING_PANEL_FLAT_V2) == "john"
    assert truth.pooled_verdict(HIRING_PANEL_FLAT_V2) == "sally"
    assert all(
        truth.verdict(HIRING_PANEL_FLAT_V2, hand) == "john"
        for hand in HIRING_PANEL_FLAT_V2.distribution.values()
    )


@pytest.mark.parametrize("s", NULL_POOLS + [HIRING_PANEL_FLAT_V3], ids=lambda s: s.id)
def test_symmetric_candidates_and_brief(s: Scenario) -> None:
    cands = s.candidates
    assert len(cands) == 2
    assert cands[0].blurb == cands[1].blurb
    assert "payments" not in s.brief


def _type_sign_histogram(s: Scenario, ids: set[str], candidate: str) -> dict[tuple[str, str], int]:
    hist: dict[tuple[str, str], int] = {}
    for f in s.facts:
        if f.id in ids and f.candidate_id == candidate:
            key = (FLAT_V3_TYPE[f.id], f.valence)
            hist[key] = hist.get(key, 0) + 1
    return hist


def test_flat_v3_shared_type_sign_balance() -> None:
    s = HIRING_PANEL_FLAT_V3
    shared = truth.shared_fact_ids(s)
    assert all(f.id in FLAT_V3_TYPE for f in s.facts)
    john = _type_sign_histogram(s, shared, "john")
    sally = _type_sign_histogram(s, shared, "sally")
    assert john == sally
    assert {t for t, _ in john} == set(FLAT_V3_TYPE.values())
    # shared leans John by strength only
    assert truth.shared_only_verdict(s) == "john"


def test_flat_v3_uniques_type_matched_by_john_shared_pros() -> None:
    s = HIRING_PANEL_FLAT_V3
    shared = truth.shared_fact_ids(s)
    john_pro_types = {
        FLAT_V3_TYPE[f.id]
        for f in s.facts
        if f.id in shared and f.candidate_id == "john" and f.valence == "pro"
    }
    uniques = [f for f in s.facts if f.id not in shared]
    assert 5 <= len(uniques) <= 8
    for f in uniques:
        assert f.candidate_id == "sally" and f.valence == "pro"
        assert FLAT_V3_TYPE[f.id] in john_pro_types
    for hand in s.distribution.values():
        assert 1 <= len([i for i in hand if i not in shared]) <= 2
    assert truth.pooled_verdict(s) == "sally"


def test_flat_v3_null_mirrors_every_v3_item() -> None:
    v3, null = HIRING_PANEL_FLAT_V3, HIRING_PANEL_FLAT_V3_NULL
    assert len(null.facts) == 2 * len(v3.facts)
    assert null.brief == v3.brief and null.candidates == v3.candidates
    ids = {f.id for f in null.facts}
    assert all(f.id in ids and f.id + "x" in ids for f in v3.facts)

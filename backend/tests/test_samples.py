from __future__ import annotations

import asyncio
from collections import Counter

import pytest

from app import prompts, truth, validator
from app.llm import FakeClient
from app.models import RunConfig, Scenario
from app.samples import (
    _V3_SALLY_UNIQUE,
    ALL_SAMPLE_SCENARIOS,
    FLAT_V3_FILLER,
    FLAT_V3_JOHN_PRO,
    FLAT_V3_SALLY_CON,
    HIDDEN_SAMPLE_IDS,
    HIRING_PANEL_FLAT_V2,
    HIRING_PANEL_FLAT_V3,
    HIRING_PANEL_FLAT_V3_NULL,
    HIRING_PANEL_NULL,
    HIRING_PANEL_NULL_V2,
    NULL_V2_SHARED_IDS,
    RETIRED_SAMPLE_IDS,
    SAMPLE_SCENARIOS,
    SAMPLES_BY_ID,
    SERVED_SCENARIO_IDS,
    _null_swap,
    _v3_john,
    _v3_sally,
    ensure_samples,
)
from app.scenarios.papers import PAPER_SCENARIOS
from app.store import MemoryStore

NULL_POOLS = [HIRING_PANEL_NULL, HIRING_PANEL_NULL_V2, HIRING_PANEL_FLAT_V3_NULL]

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
    assert SAMPLE_SCENARIOS[0].id == "hiring-panel-flat-v3"
    assert len(ALL_SAMPLE_SCENARIOS) > len(SAMPLE_SCENARIOS)
    assert "incident-review-v1" in HIDDEN_SAMPLE_IDS


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


def test_ensure_samples_leaves_hidden_rows_without_upserting() -> None:
    hidden = SAMPLES_BY_ID["incident-review-v1"]
    store = _StubStore([*SAMPLE_SCENARIOS, hidden])
    assert ensure_samples(store) == 0  # type: ignore[arg-type]
    assert store.get_scenario(hidden.id) == hidden
    assert hidden.id not in store.upserted


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


RETIRED_HIRING_IDS = ["hiring-panel-flat-v2", "hiring-panel-null", "hiring-panel-flat-v3-null"]


def test_retired_hiring_samples_not_served() -> None:
    for scenario_id in RETIRED_HIRING_IDS:
        assert scenario_id in RETIRED_SAMPLE_IDS
        assert scenario_id not in SERVED_SCENARIO_IDS
        assert scenario_id in SAMPLES_BY_ID

    store = MemoryStore()
    store.upsert_scenario(HIRING_PANEL_FLAT_V2.model_copy(update={"is_sample": True}))
    ensure_samples(store)
    assert store.get_scenario("hiring-panel-flat-v2") is None


def test_null_v2_pairs_are_paraphrased_not_mirrored() -> None:
    s = HIRING_PANEL_NULL_V2
    texts = [f.text for f in s.facts]
    assert len(texts) == len(set(texts))
    by_candidate = Counter(f.candidate_id for f in s.facts)
    assert by_candidate["john"] == by_candidate["sally"]
    for fact in s.facts:
        if not fact.id.endswith("x"):
            continue
        base = s.fact(fact.id[:-1])
        assert base is not None
        assert fact.candidate_id != base.candidate_id
        assert fact.valence == "neutral" == base.valence
        assert fact.text != _null_swap(base.text)
        assert fact.text != base.text


def test_null_v2_hands() -> None:
    s = HIRING_PANEL_NULL_V2
    assert [a.id for a in s.agents] == ["dana", "marcus", "priya", "tom"]
    shared = set(NULL_V2_SHARED_IDS)
    for hand in s.distribution.values():
        for fact_id in hand:
            if fact_id not in shared and not fact_id.endswith("x"):
                assert fact_id + "x" in hand
        assert truth.verdict(s, hand) == "undecided"
    assert truth.pooled_verdict(s) == "undecided"
    assert all(fact.memo_text and fact.keywords for fact in s.facts)
    cfg = RunConfig()  # balanced candidate order, seed 0
    split = Counter(prompts.resolve_candidate_order(s, cfg, a) for a in s.agents)
    assert split == Counter({"fixed": 2, "reversed": 2})


@pytest.mark.parametrize("s", NULL_POOLS + [HIRING_PANEL_FLAT_V3], ids=lambda s: s.id)
def test_symmetric_candidates_and_brief(s: Scenario) -> None:
    cands = s.candidates
    assert len(cands) == 2
    assert "payments" not in s.brief
    if s is HIRING_PANEL_NULL:
        assert cands[0].blurb == cands[1].blurb
    else:
        # null-v2 blurbs are equivalent paraphrases, not identical strings
        assert cands[0].blurb != ""


def test_flat_v3_is_cut_from_null_v2_bank() -> None:
    s = HIRING_PANEL_FLAT_V3
    bank = {f.id: f for f in HIRING_PANEL_NULL_V2.facts}
    assert len(s.facts) == 25
    assert all(f.id in bank for f in s.facts)
    for f in s.facts:
        twin = bank[f.id]
        assert (f.text, f.memo_text, f.keywords) == (twin.text, twin.memo_text, twin.keywords)
    shared = truth.shared_fact_ids(s)
    assert len(shared) == 17
    fact_ids = {f.id for f in s.facts}
    for base in FLAT_V3_JOHN_PRO:
        assert _v3_john(base) in shared
        assert _v3_sally(base) not in fact_ids
    for base in FLAT_V3_SALLY_CON:
        assert _v3_sally(base) in shared
        assert _v3_john(base) not in fact_ids
    for base in FLAT_V3_FILLER:
        assert base in shared and base + "x" in shared
    uniques = [f for f in s.facts if f.id not in shared]
    assert len(uniques) == 8
    assert all(f.candidate_id == "sally" and f.valence == "pro" for f in uniques)
    for agent, hand in s.distribution.items():
        assert len([i for i in hand if i not in shared]) == 2
    for agent, bases in _V3_SALLY_UNIQUE.items():
        hand = s.distribution[agent]
        assert all(_v3_sally(b) in hand for b in bases)
    assert truth.shared_only_verdict(s) == "john"
    assert truth.pooled_verdict(s) == "sally"
    assert all(truth.verdict(s, hand) == "john" for hand in s.distribution.values())


def test_flat_v3_null_mirrors_every_v3_item() -> None:
    v3, null = HIRING_PANEL_FLAT_V3, HIRING_PANEL_FLAT_V3_NULL
    pairs = (
        set(FLAT_V3_JOHN_PRO)
        | set(FLAT_V3_SALLY_CON)
        | set(FLAT_V3_FILLER)
        | {b for bases in _V3_SALLY_UNIQUE.values() for b in bases}
    )
    assert len(null.facts) == 2 * len(pairs) == 40
    assert null.brief == v3.brief and null.candidates == v3.candidates
    ids = {f.id for f in null.facts}
    assert all(b in ids and b + "x" in ids for b in pairs)
    assert all(f.id in ids for f in v3.facts)
    assert all(f.valence == "neutral" for f in null.facts)
    assert all(truth.verdict(null, hand) == "undecided" for hand in null.distribution.values())
    assert truth.pooled_verdict(null) == "undecided"

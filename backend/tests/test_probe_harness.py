from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app import orchestrator, prompts, truth
from app.llm import FakeClient
from app.models import AgentPersona, Candidate, Fact, RunConfig, Scenario
from app.paradigms import get_paradigm
from app.samples import HIRING_PANEL_FLAT, HIRING_PANEL_V1
from app.store import MemoryStore

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import perceived_profile
import probe_lib


def test_prompt_style_default_unchanged() -> None:
    spec = get_paradigm("free_discussion")
    agent = HIRING_PANEL_V1.agents[0]
    hand = list(HIRING_PANEL_V1.distribution[agent.id])
    default = prompts.system_prompt(HIRING_PANEL_V1, RunConfig(), agent, hand, spec)
    naive = prompts.system_prompt(
        HIRING_PANEL_V1, RunConfig(prompt_style="naive"), agent, hand, spec
    )
    assert "asymmetr" in default.lower() or "evidence" in default.lower()
    assert naive != default
    assert "one or two sentences" in naive


def test_plant_used_verbatim_and_first() -> None:
    store = MemoryStore()
    client = FakeClient()
    run = orchestrator.new_run(store, RunConfig(turn_order="random", seed=3), provider="fake")
    store.create_run(run)
    speaker = run.scenario.agents[-1].id
    plant = orchestrator.Plant(round_idx=0, speaker=speaker, text="Eight years of professional Go.")
    assert orchestrator.turn_order(run, 0, (plant,))[0] == speaker
    assert orchestrator.turn_order(run, 0) != orchestrator.turn_order(run, 0, (plant,))

    async def go() -> None:
        final = await orchestrator.run_to_completion(store, client, run.id, plants=(plant,))
        first = final.turns[0]
        assert first.agent_id == speaker
        assert first.sentences == ["Eight years of professional Go."]
        assert first.input_tokens == 0

    asyncio.run(go())


def test_wilson_and_odds_ratio() -> None:
    p, lo, hi = probe_lib.wilson(6, 7)
    assert lo < p < hi and 0 <= lo and hi <= 1
    orv, lo, hi = probe_lib.odds_ratio(8, 2, 3, 7)
    assert orv > 1 and lo < orv < hi


def test_echo_metric() -> None:
    turns = [
        {"round": 0, "text": "a b c d e f"},
        {"round": 1, "text": "a b c d x y"},
        {"round": 1, "text": "p q r s t u"},
    ]
    echo = probe_lib.echo_by_round(turns)
    assert echo[1] > 0
    assert 0 not in echo or echo[0] == 0


def test_mirror_scenario_flips_pooled_verdict() -> None:
    mirror = probe_lib.mirror_scenario(HIRING_PANEL_FLAT)
    assert truth.verdict(HIRING_PANEL_FLAT, truth.pooled_fact_ids(HIRING_PANEL_FLAT)) == "sally"
    assert truth.verdict(mirror, truth.pooled_fact_ids(mirror)) == "john"
    assert mirror.id != HIRING_PANEL_FLAT.id


def test_perceived_tallies_match_designed_when_weights_designed() -> None:
    scenario = HIRING_PANEL_FLAT
    w = {f.id: float(truth.signed_weight(f)) for f in scenario.facts}
    t = perceived_profile.tallies(scenario, w)
    designed = truth.scores(scenario, truth.pooled_fact_ids(scenario))
    assert t["pooled"] == {k: float(v) for k, v in designed.items()}
    assert set(t) == {"shared", "pooled", *(f"hand:{a}" for a in scenario.distribution)}


def test_perceived_render_flags_disagreement() -> None:
    result = {
        "scenario": "x",
        "items": [
            {
                "id": "S10",
                "candidate": "sally",
                "kind": "shared",
                "designed": -1,
                "calibrate_mean": 0.0,
                "neutral_mean": 1.0,
                "disagree_calibrate": False,
                "disagree_neutral": True,
                "weak_calibrate": True,
                "weak_neutral": False,
                "text": "t",
            }
        ],
        "tallies": {
            "designed": {"pooled": {"john": 1.0, "sally": 0.0}},
            "calibrate": {"pooled": {"john": 1.0, "sally": 0.0}},
            "neutral": {"pooled": {"john": 0.0, "sally": 1.0}},
        },
    }
    out = perceived_profile.render(result)
    assert "DIS-neu" in out and "weak-cal" in out
    assert "→ sally" in out and "→ john" in out


def test_gate_null_within() -> None:
    import gate_null

    assert gate_null.within(0.5, 0.35, 0.65)
    assert gate_null.within(0.35, 0.35, 0.65)
    assert not gate_null.within(0.7, 0.35, 0.65)
    assert not gate_null.within(0.2, 0.35, 0.65)


def test_balanced_order_assignment() -> None:
    assigned = [probe_lib.order_for_sample("balanced", j) for j in range(10)]
    assert assigned.count("fixed") == assigned.count("reversed") == 5
    assert probe_lib.order_for_sample("random", 0) == "random"
    assert probe_lib.order_for_sample("fixed", 7) == "fixed"


def _helper_scenario(*, pooled_tie: bool = False, hidden_tie: bool = False) -> Scenario:
    if pooled_tie and hidden_tie:
        shared_a, shared_b, unique_a, unique_b = 2, 2, 1, 1
    elif pooled_tie:
        shared_a, shared_b, unique_a, unique_b = 3, 1, 1, 3
    else:
        shared_a, shared_b, unique_a, unique_b = 1, 1, 1, 3
    agents = [
        AgentPersona(id="one", name="One", role="reviewer", style="careful"),
        AgentPersona(id="two", name="Two", role="reviewer", style="careful"),
    ]
    facts = [
        Fact(id="shared-a", candidate_id="a", valence="pro", weight=shared_a, text="A"),
        Fact(id="shared-b", candidate_id="b", valence="pro", weight=shared_b, text="B"),
        Fact(id="unique-a", candidate_id="a", valence="pro", weight=unique_a, text="A"),
        Fact(id="unique-b", candidate_id="b", valence="pro", weight=unique_b, text="B"),
    ]
    return Scenario(
        id="helper",
        title="Helper",
        brief="Choose.",
        candidates=[
            Candidate(id="a", name="A", blurb=""),
            Candidate(id="b", name="B", blurb=""),
        ],
        facts=facts,
        agents=agents,
        distribution={
            "one": ["shared-a", "shared-b", "unique-a"],
            "two": ["shared-a", "shared-b", "unique-b"],
        },
    )


def test_rotate_candidates_preserves_id_and_rotates() -> None:
    scenario = _helper_scenario()
    rotated = probe_lib.rotate_candidates(scenario, 3)
    assert scenario.id == rotated.id
    assert [c.id for c in rotated.candidates] == ["b", "a"]


def test_designed_correct_decided_and_hidden_tie_break() -> None:
    assert probe_lib.designed_correct(HIRING_PANEL_FLAT) == "sally"
    assert probe_lib.designed_correct(_helper_scenario(pooled_tie=True)) == "b"
    assert probe_lib.designed_correct(_helper_scenario(pooled_tie=True, hidden_tie=True)) is None


def test_samples_for_balances_rotations() -> None:
    assert probe_lib.samples_for(2, 8) == 8
    assert probe_lib.samples_for(3, 8) == 6
    assert probe_lib.samples_for(4, 8) == 8
    assert probe_lib.samples_for(3, 2) == 3


def test_twin_null_is_symmetric_and_rotates_names() -> None:
    candidates = [
        Candidate(id="a", name="Candidate A", blurb="A blurb"),
        Candidate(id="b", name="Candidate B", blurb="B blurb"),
        Candidate(id="c", name="Candidate C", blurb="C blurb"),
    ]
    agents = [
        AgentPersona(id="one", name="One", role="reviewer", style="careful"),
        AgentPersona(id="two", name="Two", role="reviewer", style="careful"),
    ]
    scenario = Scenario(
        id="three-way",
        title="Three-way",
        brief="Choose.",
        candidates=candidates,
        facts=[
            Fact(
                id="fact-a",
                candidate_id="a",
                valence="pro",
                weight=2,
                text="Candidate A (a) has a strong result.",
                memo_text="Candidate A (a) result.",
            ),
            Fact(
                id="fact-b",
                candidate_id="b",
                valence="pro",
                weight=1,
                text="Candidate B (b) has a strong result.",
                memo_text="Candidate B (b) result.",
            ),
        ],
        agents=agents,
        distribution={"one": ["fact-a"], "two": ["fact-b"]},
    )
    twin = probe_lib.twin_null(scenario)
    assert twin.id == "three-way-twin"
    assert twin.title == "Three-way (twin null)"
    assert twin.validation is None
    assert len(twin.facts) == 3 * len(scenario.facts)
    assert all(candidate.blurb == "" for candidate in twin.candidates)
    assert twin.facts[0].text == "Candidate A (a) has a strong result."
    assert twin.facts[1].text == "Candidate B (b) has a strong result."
    assert twin.facts[2].text == "Candidate C (c) has a strong result."
    assert twin.facts[0].memo_text == "Candidate A (a) result."
    assert len(twin.distribution["one"]) == 3
    pooled_scores = truth.scores(twin, truth.pooled_fact_ids(twin))
    assert len(set(pooled_scores.values())) == 1
    for held in twin.distribution.values():
        scores = truth.scores(twin, held)
        assert len(set(scores.values())) == 1

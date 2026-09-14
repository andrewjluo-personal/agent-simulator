from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app import orchestrator, prompts, truth
from app.llm import FakeClient
from app.models import RunConfig
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

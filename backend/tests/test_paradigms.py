from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app import orchestrator
from app.llm import FakeClient
from app.models import RunConfig, RunState, Turn
from app.paradigms import MODERATOR_ID, get_paradigm
from app.prompts import system_prompt, turn_message, vote_message
from app.samples import SAMPLE_SCENARIOS
from app.store import MemoryStore
from app.truth import UNDECIDED, _majority
from app.validate import validate_board, validate_turn


def _run(cfg: RunConfig) -> tuple[MemoryStore, FakeClient, RunState]:
    store = MemoryStore()
    client = FakeClient()
    run = orchestrator.new_run(store, cfg, provider="fake")
    store.create_run(run)
    return store, client, run


def test_existing_prompt_snapshots_are_unchanged() -> None:
    scenario = SAMPLE_SCENARIOS[0]
    agent = scenario.agents[0]
    hand = scenario.distribution[agent.id]
    heard = [
        Turn(
            seq=i,
            round=0,
            agent_id=scenario.agents[(i + 1) % len(scenario.agents)].id,
            sentences=[f"synthetic {i}"],
            cited=[scenario.distribution[scenario.agents[(i + 1) % len(scenario.agents)].id][0]],
            hallucinated=[],
            lean=UNDECIDED,
            confidence=0.5,
        )
        for i in range(2)
    ]
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "prompts_baseline.json").read_text()
    )
    for paradigm_id in ("free_discussion", "share_first"):
        cfg = RunConfig(paradigm=paradigm_id)
        spec = get_paradigm(paradigm_id)
        assert system_prompt(scenario, cfg, agent, hand, spec) == fixture[paradigm_id]["system"]
        assert turn_message(scenario, cfg, 0, [], spec) == fixture[paradigm_id]["turn_0"]
        assert turn_message(scenario, cfg, 0, heard, spec) == fixture[paradigm_id]["turn_2"]
        assert vote_message(0, cfg, final=False) == fixture[paradigm_id]["vote"]


def test_new_paradigms_run_to_completion() -> None:
    async def go() -> None:
        for paradigm in ("exchange_then_decide", "elicitation_moderator", "message_board"):
            store, client, run = _run(RunConfig(paradigm=paradigm))
            final = await orchestrator.run_to_completion(store, client, run.id)
            extras = len(get_paradigm(paradigm).extra_participants())
            n_agents = len(run.scenario.agents)
            assert final.status == "done"
            assert len(final.turns) == final.config.rounds * (n_agents + extras)
            assert len(final.votes) == final.config.rounds * n_agents
            assert all(v.agent_id in {a.id for a in run.scenario.agents} for v in final.votes)
            assert final.metrics is not None

    asyncio.run(go())


def test_exchange_phases_and_opinion_gate() -> None:
    async def go() -> None:
        cfg = RunConfig(paradigm="exchange_then_decide", rounds=3)
        store, client, run = _run(cfg)
        await orchestrator.run_to_completion(store, client, run.id)
        exchange_rounds = (cfg.rounds + 1) // 2
        for turn in run.turns:
            expected = "exchange" if turn.round < exchange_rounds else "decide"
            assert turn.phase == expected
            if expected == "exchange":
                assert turn.lean == UNDECIDED
        scenario = run.scenario
        candidate_ids = {candidate.id for candidate in scenario.candidates}
        raw = {
            "sentences": [],
            "items_referenced": [],
            "current_lean": next(iter(candidate_ids)),
            "confidence": 0.5,
        }
        assert validate_turn(raw, set(), set(), candidate_ids, 2, False).lean == UNDECIDED
        assert validate_turn(raw, set(), set(), candidate_ids, 2, True).lean != UNDECIDED

    asyncio.run(go())


def test_moderator_turns_and_metrics_exclude_moderator() -> None:
    async def go() -> None:
        store, client, run = _run(RunConfig(paradigm="elicitation_moderator"))
        final = await orchestrator.run_to_completion(store, client, run.id)
        n_agents = len(run.scenario.agents)
        moderators = [turn for turn in final.turns if turn.agent_id == MODERATOR_ID]
        assert len(moderators) == final.config.rounds
        assert [turn.seq for turn in moderators] == [
            round_idx * (n_agents + 1) for round_idx in range(final.config.rounds)
        ]
        assert all(v.agent_id != MODERATOR_ID for v in final.votes)
        assert final.metrics is not None
        agent_votes = final.votes
        last_round = max(v.round for v in agent_votes)
        final_choices = [v.choice for v in agent_votes if v.round == last_round]
        majority = _majority(final_choices)
        majority_voters = sum(choice == majority for choice in final_choices)
        assert final.metrics.agreement == majority_voters / n_agents
        injected = final.model_copy(deep=True)
        injected.turns.append(
            Turn(
                seq=max(turn.seq for turn in injected.turns) + 1,
                round=0,
                agent_id=MODERATOR_ID,
                sentences=[],
                cited=[],
                hallucinated=[f"{run.scenario.facts[0].id}-hallucinated"],
                lean=UNDECIDED,
                confidence=0.0,
            )
        )
        assert orchestrator.compute_metrics(injected).hallucination_count == final.metrics.hallucination_count

    asyncio.run(go())


def test_board_context_and_validation() -> None:
    scenario = SAMPLE_SCENARIOS[0]
    agent = scenario.agents[0]
    fact_id = scenario.distribution[agent.id][0]
    run = RunState(
        id="test",
        scenario_id=scenario.id,
        scenario=scenario,
        config=RunConfig(paradigm="message_board"),
        status="running",
        llm_provider="fake",
        turns=[
            Turn(
                seq=0,
                round=0,
                agent_id=agent.id,
                sentences=["one. two."],
                cited=[fact_id],
                hallucinated=[],
                lean=UNDECIDED,
                confidence=0.5,
            )
        ],
    )
    context = get_paradigm("message_board").visible_context(run, agent.id, 0)
    assert scenario.fact(fact_id).text in context
    assert "one." in context
    assert "two." not in context
    validated = validate_board(
        {"fact_ids": [fact_id, f"{fact_id}-hallucinated"], "note": "one. two.", "current_lean": UNDECIDED, "confidence": 0.5},
        {fact_id},
        {candidate.id for candidate in scenario.candidates},
        True,
    )
    assert validated.cited == [fact_id]
    assert validated.hallucinated == [f"{fact_id}-hallucinated"]
    assert validated.sentences == ["one."]

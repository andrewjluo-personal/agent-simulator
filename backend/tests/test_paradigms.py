from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app import orchestrator
from app.llm import FakeClient
from app.models import RunConfig, RunState, Turn
from app.paradigms import MODERATOR_ID, ExchangeThenDecide, get_paradigm
from app.prompts import moderator_message, system_prompt, turn_message, vote_message
from app.samples import SAMPLE_SCENARIOS
from app.store import MemoryStore
from app.truth import UNDECIDED, _majority, match_facts
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
        assert turn_message(scenario, cfg, 0, [], spec, cfg.rounds) == fixture[paradigm_id]["turn_0"]
        assert turn_message(scenario, cfg, 0, heard, spec, cfg.rounds) == fixture[paradigm_id]["turn_2"]
        assert (
            vote_message(
                scenario,
                cfg,
                0,
                heard,
                agent.id,
                total=cfg.rounds,
                final=False,
            )
            == fixture[paradigm_id]["vote"]
        )


def test_exchange_and_moderator_prompt_addenda() -> None:
    scenario = SAMPLE_SCENARIOS[0]
    cfg = RunConfig(paradigm="exchange_then_decide", rounds=3, fact_style="labelled")
    run = RunState(
        id="test",
        scenario_id=scenario.id,
        scenario=scenario,
        config=cfg,
        status="running",
        llm_provider="fake",
    )
    agent = scenario.agents[0]
    spec = get_paradigm(cfg.paradigm)
    assert isinstance(spec, ExchangeThenDecide)
    first_addendum = spec.turn_addendum(run, agent.id, 0)
    first_prompt = turn_message(scenario, cfg, 0, [], spec, cfg.rounds, addendum=first_addendum)
    assert all(fact_id in first_prompt for fact_id in scenario.distribution[agent.id])
    decide_round = spec.exchange_rounds(cfg)
    decide_addendum = spec.turn_addendum(run, agent.id, decide_round)
    decide_prompt = turn_message(
        scenario, cfg, decide_round, [], spec, cfg.rounds, addendum=decide_addendum
    )
    assert "Discussion phase begins" in decide_prompt
    moderator_turn = Turn(
        seq=0,
        round=0,
        agent_id=MODERATOR_ID,
        sentences=["Please share your remaining evidence."],
        cited=[],
        hallucinated=[],
        lean=UNDECIDED,
        confidence=0.0,
        addressed_agent_id=agent.id,
    )
    run.turns = [moderator_turn]
    ask = orchestrator._moderator_ask(run.turns, agent.id, 0)
    addressed_prompt = turn_message(
        scenario, cfg, 0, run.turns, spec, cfg.rounds, addendum=ask
    )
    assert "The moderator asked you" in addressed_prompt


def test_new_paradigms_run_to_completion() -> None:
    async def go() -> None:
        for paradigm in ("exchange_then_decide", "elicitation_moderator", "message_board"):
            store, client, run = _run(RunConfig(paradigm=paradigm))
            final = await orchestrator.run_to_completion(store, client, run.id)
            extras = len(get_paradigm(paradigm).extra_participants())
            n_agents = len(run.scenario.agents)
            total_rounds = orchestrator.total_rounds(final)
            assert final.status == "done"
            assert len(final.turns) == total_rounds * (n_agents + extras)
            assert len(final.votes) == (total_rounds + 1) * n_agents
            assert all(v.agent_id in {a.id for a in run.scenario.agents} for v in final.votes)
            assert final.metrics is not None

    asyncio.run(go())


def test_exchange_phases_and_opinion_gate() -> None:
    async def go() -> None:
        cfg = RunConfig(paradigm="exchange_then_decide", rounds=3, fact_style="labelled")
        store, client, run = _run(cfg)
        await orchestrator.run_to_completion(store, client, run.id)
        for turn in run.turns:
            expected = get_paradigm(cfg.paradigm).phase_for(turn.round, cfg)
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
        total_rounds = orchestrator.total_rounds(final)
        moderators = [turn for turn in final.turns if turn.agent_id == MODERATOR_ID]
        assert len(moderators) == total_rounds
        assert [turn.seq for turn in moderators] == [
            round_idx * (n_agents + 1) for round_idx in range(total_rounds)
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
    assert context is not None
    assert scenario.fact(fact_id).text in context
    assert "one." in context
    assert "two." not in context
    validated = validate_board(
        {"fact_ids": [fact_id, f"{fact_id}-hallucinated"], "note": "one. two.", "current_lean": UNDECIDED, "confidence": 0.5},
        {fact_id},
        {candidate.id for candidate in scenario.candidates},
        True,
        scenario=scenario,
        fact_style="labelled",
    )
    assert validated.cited == [fact_id]
    assert validated.hallucinated == [f"{fact_id}-hallucinated"]
    assert validated.sentences == ["one."]


def test_memo_paradigm_prompts_hide_fact_ids() -> None:
    scenario = SAMPLE_SCENARIOS[0]
    agent = scenario.agents[0]
    cfg = RunConfig(paradigm="exchange_then_decide", fact_style="memo")
    run = RunState(
        id="test",
        scenario_id=scenario.id,
        scenario=scenario,
        config=cfg,
        status="running",
        llm_provider="fake",
    )
    spec = get_paradigm(cfg.paradigm)
    addendum = spec.turn_addendum(run, agent.id, 0)
    assert addendum is not None
    assert "Points from your notes not yet raised by anyone:" in addendum
    assert any(
        (scenario.fact(fact_id).memo_text or scenario.fact(fact_id).text) in addendum
        for fact_id in scenario.distribution[agent.id]
    )
    assert all(fact_id not in addendum for fact_id in scenario.distribution[agent.id])

    heard = [
        Turn(
            seq=0,
            round=0,
            agent_id=scenario.agents[1].id,
            sentences=["A note from the panel."],
            cited=[scenario.distribution[scenario.agents[1].id][0]],
            hallucinated=[],
            lean=UNDECIDED,
            confidence=0.5,
        )
    ]
    moderator = moderator_message(
        scenario,
        cfg,
        0,
        heard,
        {agent.id: len(scenario.distribution[agent.id]) for agent in scenario.agents},
    )
    assert "FACT IDS MENTIONED" not in moderator
    assert all(fact.id not in moderator for fact in scenario.facts)


def test_memo_board_context_and_validation_use_verbatim_facts() -> None:
    scenario = SAMPLE_SCENARIOS[0]
    agent = scenario.agents[0]
    fact_id = scenario.distribution[agent.id][0]
    run = RunState(
        id="test",
        scenario_id=scenario.id,
        scenario=scenario,
        config=RunConfig(paradigm="message_board", fact_style="memo"),
        status="running",
        llm_provider="fake",
        turns=[
            Turn(
                seq=0,
                round=0,
                agent_id=agent.id,
                sentences=["A note."],
                cited=[fact_id],
                hallucinated=[],
                lean=UNDECIDED,
                confidence=0.5,
            )
        ],
    )
    board = get_paradigm("message_board")
    context = board.visible_context(run, agent.id, 0)
    assert context is not None
    assert scenario.fact(fact_id).text in context
    assert f"[{fact_id}]" not in context

    hand = set(scenario.distribution[agent.id])
    off_hand = next(
        fact
        for fact in scenario.facts
        if fact.id not in hand and not match_facts([fact.text], [scenario.fact(fid) for fid in hand])
    )
    validated = validate_board(
        {
            "facts": [scenario.fact(fact_id).text, off_hand.text],
            "note": "",
            "current_lean": UNDECIDED,
            "confidence": 0.5,
        },
        hand,
        {candidate.id for candidate in scenario.candidates},
        True,
        scenario=scenario,
        fact_style="memo",
    )
    assert fact_id in validated.cited
    assert off_hand.id not in validated.cited
    assert f"unmatched:{off_hand.text[:60]}" in validated.hallucinated

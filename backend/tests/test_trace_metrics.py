from __future__ import annotations

import asyncio

from app import orchestrator, truth
from app.llm import FakeClient
from app.models import RunConfig, RunState, Turn, Vote
from app.store import MemoryStore


def _run(cfg: RunConfig | None = None) -> tuple[MemoryStore, RunState]:
    store = MemoryStore()
    run = orchestrator.new_run(store, cfg or RunConfig(), provider="fake")
    store.create_run(run)
    return store, run


def _turn(seq: int, round_idx: int, agent_id: str, cited: list[str], heard: list[str]) -> Turn:
    return Turn(
        seq=seq,
        round=round_idx,
        agent_id=agent_id,
        sentences=["x"],
        cited=cited,
        hallucinated=[],
        lean="undecided",
        confidence=0.5,
        latency_ms=10,
        input_tokens=100,
        output_tokens=20,
        heard_before=heard,
    )


def test_unspoken_decisive_with_holders_and_first_surfaced() -> None:
    store, run = _run(RunConfig(rounds=2))
    s = run.scenario
    decisive = sorted(truth.decisive_fact_ids(s))
    spoken, silent = decisive[0], decisive[1]
    shared = min(truth.shared_fact_ids(s))
    agents = [a.id for a in s.agents]
    speaker = truth.holders(s, spoken)[0]
    other = next(a for a in agents if a != speaker)
    n = len(agents)
    store.insert_turn(run.id, _turn(0, 0, other, [shared], []))
    store.insert_turn(run.id, _turn(1, 0, speaker, [spoken, shared], [shared]))
    store.insert_turn(run.id, _turn(n, 1, speaker, [spoken], [shared, spoken]))
    m = orchestrator.compute_metrics(store.get_run(run.id) or run)

    assert silent in m.unspoken_decisive
    assert spoken not in m.unspoken_decisive
    assert m.holders[silent] == truth.holders(s, silent)
    assert m.first_surfaced[spoken].seq == 1
    assert m.first_surfaced[spoken].round == 0
    assert m.first_surfaced[spoken].agent_id == speaker
    assert m.first_surfaced[shared].seq == 0
    assert m.mentions.shared == 2
    assert m.mentions.unique == 2
    assert m.tokens_total.input == 300
    assert m.tokens_total.output == 60
    assert m.latency_total_ms == 30
    assert m.llm_calls == 3


def test_agreement_and_accuracy_by_round() -> None:
    store, run = _run(RunConfig(rounds=2))
    s = run.scenario
    correct = truth.pooled_verdict(s)
    wrong = next(c.id for c in s.candidates if c.id != correct)
    agents = [a.id for a in s.agents]
    n = len(agents)
    # round 0: everyone but one votes wrong, the last is undecided
    for i, a in enumerate(agents):
        choice = "undecided" if i == n - 1 else wrong
        store.insert_vote(run.id, Vote(round=0, agent_id=a, choice=choice, confidence=0.5))
    # round 1: unanimous correct
    for a in agents:
        store.insert_vote(run.id, Vote(round=1, agent_id=a, choice=correct, confidence=0.9))
    m = orchestrator.compute_metrics(store.get_run(run.id) or run)

    assert len(m.agreement_by_round) == run.config.rounds == len(m.vote_trajectory)
    assert len(m.accuracy_by_round) == run.config.rounds
    assert abs(m.agreement_by_round[0] - (n - 1) / n) < 1e-9
    assert m.accuracy_by_round[0] == 0.0
    assert m.agreement_by_round[1] == 1.0
    assert m.accuracy_by_round[1] == 1.0


def test_heard_before_recorded_in_run() -> None:
    async def go() -> None:
        store, run = _run(RunConfig(rounds=1))
        final = await orchestrator.run_to_completion(store, FakeClient(), run.id)
        turns = sorted(final.turns, key=lambda t: t.seq)
        assert turns[0].heard_before == []
        for i in range(1, len(turns)):
            expected = sorted({f for t in turns[:i] for f in t.cited})
            assert turns[i].heard_before == expected
        assert final.metrics is not None
        assert set(final.metrics.first_surfaced) == {f for t in turns for f in t.cited}
        assert set(final.metrics.unspoken_decisive) == truth.decisive_fact_ids(
            final.scenario
        ) - set(final.metrics.first_surfaced)

    asyncio.run(go())

from __future__ import annotations

import asyncio

from app import orchestrator
from app.llm import FakeClient
from app.models import RunConfig, RunState, Turn
from app.store import MemoryStore


def _run(
    cfg: RunConfig | None = None, store: MemoryStore | None = None
) -> tuple[MemoryStore, FakeClient, RunState]:
    store = store or MemoryStore()
    client = FakeClient()
    run = orchestrator.new_run(cfg or RunConfig(), provider="fake")
    store.create_run(run)
    return store, client, run


def test_run_to_completion() -> None:
    async def go() -> None:
        store, client, run = _run()
        final = await orchestrator.run_to_completion(store, client, run.id)
        n = len(run.scenario.agents)
        assert final.status == "done"
        assert len(final.turns) == run.config.rounds * n
        assert len(final.votes) == run.config.rounds * n
        assert final.metrics is not None
        assert final.metrics.correct_candidate_id == "sally"
        assert final.metrics.decisive_total == 14
        assert len(final.metrics.vote_trajectory) == run.config.rounds

    asyncio.run(go())


def test_idempotent_redelivery() -> None:
    async def go() -> None:
        store, client, run = _run()
        n = len(run.scenario.agents)
        await orchestrator.run_round(store, client, run.id, 0)
        await orchestrator.run_round(store, client, run.id, 0)  # redelivery
        state = store.get_run(run.id)
        assert state is not None
        assert len([t for t in state.turns if t.round == 0]) == n
        assert len([v for v in state.votes if v.round == 0]) == n
        # stale round after current_round advanced is a no-op
        state = await orchestrator.run_round(store, client, run.id, 0)
        assert len(state.turns) == n

    asyncio.run(go())


def test_preinserted_turn_kept() -> None:
    async def go() -> None:
        store, client, run = _run()
        pre = Turn(
            seq=0,
            round=0,
            agent_id="dana",
            sentences=["preexisting"],
            cited=[],
            hallucinated=[],
            lean="undecided",
            confidence=0.1,
        )
        store.insert_turn(run.id, pre)
        await orchestrator.run_round(store, client, run.id, 0)
        state = store.get_run(run.id)
        assert state is not None
        n = len(run.scenario.agents)
        assert len([t for t in state.turns if t.round == 0]) == n
        kept = next(t for t in state.turns if t.seq == 0)
        assert kept.sentences == ["preexisting"]

    asyncio.run(go())


def test_share_first_forces_undecided_round_zero() -> None:
    async def go() -> None:
        store, client, run = _run(RunConfig(paradigm="share_first", rounds=2))
        await orchestrator.run_round(store, client, run.id, 0)
        state = store.get_run(run.id)
        assert state is not None
        assert all(t.lean == "undecided" for t in state.turns if t.round == 0)
        await orchestrator.run_round(store, client, run.id, 1)
        state = store.get_run(run.id)
        assert state is not None
        assert any(t.lean != "undecided" for t in state.turns if t.round == 1)

    asyncio.run(go())


def test_random_turn_order_deterministic() -> None:
    cfg = RunConfig(turn_order="random", seed=7)
    _, _, run = _run(cfg)
    r0 = orchestrator.turn_order(run, 0)
    assert r0 == orchestrator.turn_order(run, 0)
    assert r0 != orchestrator.turn_order(run, 1)
    assert sorted(r0) == sorted(a.id for a in run.scenario.agents)


def test_compute_metrics_arithmetic() -> None:
    store, _, run = _run(RunConfig(rounds=1))
    s = run.scenario
    decisive = sorted(__import__("app.truth", fromlist=["x"]).decisive_fact_ids(s))
    for i, t in enumerate(run.scenario.agents):
        store.insert_turn(
            run.id,
            Turn(
                seq=i,
                round=0,
                agent_id=t.id,
                sentences=["x"],
                cited=decisive[:2] if i == 0 else [],
                hallucinated=["X1"],
                lean="john",
                confidence=0.5,
            ),
        )
        from app.models import Vote

        store.insert_vote(
            run.id,
            Vote(round=0, agent_id=t.id, choice="sally" if i else "john", confidence=0.5),
        )
    m = orchestrator.compute_metrics(store.get_run(run.id) or run)
    assert m.correct_candidate_id == "sally"
    assert m.majority_candidate_id == "sally"
    assert m.correct
    assert m.decisive_surfaced_count == 2
    assert abs(m.decisive_surfaced - 2 / len(decisive)) < 1e-9
    assert m.agreement == 0.75
    assert m.hallucination_count == 4
    assert m.vote_trajectory == [{"sally": 3, "john": 1}]

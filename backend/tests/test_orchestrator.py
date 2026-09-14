from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app import orchestrator
from app.llm import FakeClient, LLMClient, LLMRequest, LLMResponse
from app.models import RunConfig, RunState, Turn
from app.store import MemoryStore


class RecordingClient(LLMClient):
    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.provider = inner.provider
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return await self.inner.complete(request)


def _run(
    cfg: RunConfig | None = None, store: MemoryStore | None = None
) -> tuple[MemoryStore, FakeClient, RunState]:
    store = store or MemoryStore()
    client = FakeClient()
    run = orchestrator.new_run(store, cfg or RunConfig(), provider="fake")
    store.create_run(run)
    return store, client, run


def test_run_to_completion() -> None:
    async def go() -> None:
        store, client, run = _run()
        final = await orchestrator.run_to_completion(store, client, run.id)
        n = len(run.scenario.agents)
        assert final.status == "done"
        assert len(final.turns) == run.config.rounds * n
        # one private ballot per agent per round plus the pre-discussion ballot
        assert len(final.votes) == (run.config.rounds + 1) * n
        assert final.metrics is not None
        assert final.metrics.correct_candidate_id == "sally"
        assert final.metrics.decisive_total == 19
        assert len(final.metrics.vote_trajectory) == run.config.rounds + 1
        assert final.metrics.vote_rounds[0] == -1

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
        assert len([v for v in state.votes if v.round == -1]) == n
        # stale round after current_round advanced is a no-op
        state = await orchestrator.run_round(store, client, run.id, 0)
        assert len(state.turns) == n
        assert len([v for v in state.votes if v.round == -1]) == n

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
    assert m.agreement == 0.8
    assert m.hallucination_count == 5
    assert m.vote_trajectory == [{"sally": 4, "john": 1}]


def test_pre_discussion_ballot_has_no_transcript() -> None:
    async def go() -> None:
        store, client, run = _run(RunConfig(rounds=1))
        rec = RecordingClient(client)
        final = await orchestrator.run_to_completion(store, rec, run.id)
        n = len(run.scenario.agents)
        pre_votes = [v for v in final.votes if v.round == -1]
        assert len(pre_votes) == n
        assert all(v.said_lean == "undecided" for v in pre_votes)
        pre_reqs = [
            r for r in rec.requests if r.meta.get("kind") == "vote" and r.meta.get("round") == -1
        ]
        assert len(pre_reqs) == n
        assert all("TRANSCRIPT SO FAR" not in r.user for r in pre_reqs)

    asyncio.run(go())


def test_ballot_sees_transcript_and_own_lean() -> None:
    async def go() -> None:
        store, client, run = _run(RunConfig(rounds=1, fact_style="labelled"))
        rec = RecordingClient(client)
        await orchestrator.run_to_completion(store, rec, run.id)
        round0_votes = [
            r for r in rec.requests if r.meta.get("kind") == "vote" and r.meta.get("round") == 0
        ]
        assert round0_votes
        # the ballot saw the discussion: a FakeClient turn sentence appears in it
        assert any("I noted the point about" in r.user for r in round0_votes)
        assert all("TRANSCRIPT SO FAR" in r.user for r in round0_votes)
        assert all("Your last stated lean:" in r.user for r in round0_votes)

    asyncio.run(go())


def test_hidden_transcript_naive_run_completes() -> None:
    async def go() -> None:
        store, client, run = _run(
            RunConfig(
                rounds=2,
                prompt_style="naive",
                transcript_visibility="none",
            )
        )
        final = await orchestrator.run_to_completion(store, client, run.id)
        assert final.status == "done"
        assert final.metrics is not None

    asyncio.run(go())


def test_memo_mode_run_yields_cited() -> None:
    async def go() -> None:
        store, client, run = _run(RunConfig(fact_style="memo", rounds=2))
        rec = RecordingClient(client)
        final = await orchestrator.run_to_completion(store, rec, run.id)
        assert final.status == "done"
        for t in final.turns:
            if t.sentences:
                assert t.cited, f"turn {t.seq} spoke but cited nothing"
        assert all(r.meta.get("fact_style") == "memo" for r in rec.requests)
        for r in rec.requests:
            assert "items_referenced" not in r.system
            assert "items_referenced" not in r.user

    asyncio.run(go())


def _tie_client(monkeypatch: pytest.MonkeyPatch, agent_ids: list[str]) -> FakeClient:
    """FakeClient whose ballots tie after the undecided vote is excluded."""

    def _alt_vote(self: FakeClient, meta: dict[str, Any], rng: Any) -> str:
        idx = agent_ids.index(meta["agent_id"])
        return json.dumps(
            {
                "vote": (
                    "undecided"
                    if idx == len(agent_ids) - 1
                    else ("john" if idx % 2 == 0 else "sally")
                ),
                "confidence": 0.6,
                "reason": "fixed",
            }
        )

    monkeypatch.setattr(FakeClient, "_vote", _alt_vote)
    return FakeClient()


def test_runoff_extends_on_tie(monkeypatch: pytest.MonkeyPatch) -> None:
    async def go() -> None:
        store, _, run = _run(RunConfig(rounds=2, tie_break="runoff"))
        client = _tie_client(monkeypatch, [agent.id for agent in run.scenario.agents])
        final = await orchestrator.run_to_completion(store, client, run.id)
        n = len(run.scenario.agents)
        assert final.status == "done"
        assert len(final.turns) == (run.config.rounds + 1) * n
        assert len(final.votes) == (run.config.rounds + 2) * n
        assert any(t.round == run.config.rounds for t in final.turns)

    asyncio.run(go())


def test_tie_break_none_stops_on_tie(monkeypatch: pytest.MonkeyPatch) -> None:
    async def go() -> None:
        store, _, run = _run(RunConfig(rounds=2, tie_break="none"))
        client = _tie_client(monkeypatch, [agent.id for agent in run.scenario.agents])
        final = await orchestrator.run_to_completion(store, client, run.id)
        n = len(run.scenario.agents)
        assert final.status == "done"
        assert len(final.turns) == run.config.rounds * n
        assert len(final.votes) == (run.config.rounds + 1) * n
        assert final.metrics is not None
        assert final.metrics.majority_candidate_id == "undecided"
        assert final.metrics.agreement == 0.4

    asyncio.run(go())


def test_tie_break_chair(monkeypatch: pytest.MonkeyPatch) -> None:
    async def go() -> None:
        store, _, run = _run(RunConfig(rounds=2, tie_break="chair"))
        client = _tie_client(monkeypatch, [agent.id for agent in run.scenario.agents])
        final = await orchestrator.run_to_completion(store, client, run.id)
        assert final.status == "done"
        assert len(final.turns) == run.config.rounds * len(run.scenario.agents)
        assert final.metrics is not None
        first_agent = run.scenario.agents[0].id
        chair_vote = next(
            v for v in final.votes if v.round == run.config.rounds - 1 and v.agent_id == first_agent
        )
        assert final.metrics.majority_candidate_id == chair_vote.choice == "john"

    asyncio.run(go())

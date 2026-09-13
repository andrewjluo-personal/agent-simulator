from __future__ import annotations

import asyncio

from app import orchestrator, truth, validator
from app.llm import FakeClient
from app.models import AgentPersona, Candidate, Fact, RunConfig, Scenario
from app.store import MemoryStore


def three_candidate_scenario() -> Scenario:
    agents = [
        AgentPersona(id=f"agent-{i}", name=f"Agent {i}", role="reviewer", style="careful")
        for i in range(3)
    ]
    return Scenario(
        id="three-candidates",
        title="Three candidates",
        brief="Choose the strongest candidate.",
        candidates=[
            Candidate(id="a", name="A", blurb=""),
            Candidate(id="b", name="B", blurb=""),
            Candidate(id="c", name="C", blurb=""),
        ],
        facts=[
            Fact(id="shared-b", candidate_id="b", valence="pro", weight=3, text="B shared"),
            Fact(id="a-1", candidate_id="a", valence="pro", weight=2, text="A one"),
            Fact(id="a-2", candidate_id="a", valence="pro", weight=2, text="A two"),
            Fact(id="a-3", candidate_id="a", valence="pro", weight=2, text="A three"),
            Fact(id="neutral-1", candidate_id="c", valence="neutral", weight=9, text="neutral"),
            Fact(id="neutral-2", candidate_id="a", valence="neutral", weight=7, text="neutral"),
        ],
        agents=agents,
        distribution={
            "agent-0": ["shared-b", "a-1", "neutral-1"],
            "agent-1": ["shared-b", "a-2"],
            "agent-2": ["shared-b", "a-3", "neutral-2"],
        },
    )


def test_three_candidate_truth_and_orchestration() -> None:
    scenario = three_candidate_scenario()
    result = truth.analysis(scenario)
    assert result.pooled_verdict == "a"
    assert result.shared_only_verdict == "b"

    async def go() -> None:
        store = MemoryStore()
        store.upsert_scenario(scenario)
        run = orchestrator.new_run(store, RunConfig(scenario_id=scenario.id), provider="fake")
        store.create_run(run)
        final = await orchestrator.run_to_completion(store, FakeClient(), run.id)
        assert final.status == "done"
        assert final.metrics is not None
        assert final.metrics.correct_candidate_id == "a"
        assert set(final.metrics.final_tally) <= {"a", "b", "c", "undecided"}
        await validator.validate_scenario(scenario, FakeClient(), model="fake", trials=3)

    asyncio.run(go())

"""Scenario validation engine: does every agent's private hand still point at the
wrong (shared-only) candidate, and does the pooled view point at the right one?
Pure logic — testable with FakeClient."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from . import orchestrator, prompts, truth, validate
from .llm import LLMClient, LLMRequest
from .models import AgentPersona, RunConfig, Scenario, ValidationResult
from .paradigms import get_paradigm
from .store import MemoryStore

REVIEWER = AgentPersona(
    id="__all__", name="Reviewer", role="independent reviewer", style="thorough"
)


async def _alone_votes(
    scenario: Scenario,
    client: LLMClient,
    agent: AgentPersona,
    hand: list[str],
    model: str,
    trials: int,
    sem: asyncio.Semaphore,
) -> list[str]:
    cfg = RunConfig(scenario_id=scenario.id)
    spec = get_paradigm("free_discussion")
    system = prompts.system_prompt(scenario, cfg, agent, hand, spec)
    user = prompts.alone_vote_message(scenario)
    candidate_ids = {c.id for c in scenario.candidates}

    async def one(trial: int) -> str:
        meta = {
            "kind": "vote",
            "seed": trial,
            "run_nonce": f"validate-{scenario.id}",
            "agent_id": agent.id,
            "round": 0,
            "hand": hand,
            "heard": [],
            "candidates": [c.id for c in scenario.candidates],
            "alone": True,
            "fact_candidate": {f.id: f.candidate_id for f in scenario.facts},
            "fact_signed_weight": {
                f.id: f.weight if f.valence == "pro" else -f.weight for f in scenario.facts
            },
        }
        async with sem:
            resp = await client.complete(
                LLMRequest(system=system, user=user, model=model, max_tokens=200, meta=meta)
            )
        choice, _conf, _reason = validate.validate_vote(
            validate.parse_json_object(resp.text), candidate_ids
        )
        return choice

    return list(await asyncio.gather(*(one(t) for t in range(trials))))


async def validate_scenario(
    scenario: Scenario,
    client: LLMClient,
    *,
    model: str,
    trials: int,
    threshold: float = 0.8,
) -> ValidationResult:
    wrong = truth.shared_only_verdict(scenario)
    right = truth.pooled_verdict(scenario)
    sem = asyncio.Semaphore(4)

    async def agent_rates(agent: AgentPersona, hand: list[str]) -> tuple[str, list[str]]:
        votes = await _alone_votes(scenario, client, agent, hand, model, trials, sem)
        return agent.id, votes

    results = await asyncio.gather(
        *(agent_rates(a, scenario.distribution[a.id]) for a in scenario.agents)
    )
    alone_wrong_rate = {
        agent_id: sum(1 for v in votes if v == wrong) / trials for agent_id, votes in results
    }
    pooled_votes = await _alone_votes(
        scenario, client, REVIEWER, [f.id for f in scenario.facts], model, trials, sem
    )
    pooled_right_rate = sum(1 for v in pooled_votes if v == right) / trials
    passed = all(r >= threshold for r in alone_wrong_rate.values()) and (
        pooled_right_rate >= threshold
    )
    return ValidationResult(
        alone_wrong_rate=alone_wrong_rate,
        pooled_right_rate=pooled_right_rate,
        trials=trials,
        date=datetime.now(UTC).isoformat(),
        passed=passed,
    )


async def free_discussion_rate(
    scenario: Scenario,
    client: LLMClient,
    *,
    runs: int,
    provider: str,
) -> tuple[float, int]:
    """Mean metrics.correct over `runs` free_discussion simulations (seeds 0..runs-1)
    through the real orchestrator path, at most 4 concurrently."""
    sem = asyncio.Semaphore(4)

    async def one(seed: int) -> float:
        store = MemoryStore()
        store.upsert_scenario(scenario)
        run = orchestrator.new_run(
            store,
            RunConfig(scenario_id=scenario.id, paradigm="free_discussion", seed=seed),
            provider=provider,
        )
        store.create_run(run)
        async with sem:
            final = await orchestrator.run_to_completion(store, client, run.id)
        return 1.0 if final.metrics and final.metrics.correct else 0.0

    results = await asyncio.gather(*(one(s) for s in range(runs)))
    return (sum(results) / runs if runs else 0.0), runs

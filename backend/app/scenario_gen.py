"""Generate N-agent variants of hidden-profile scenarios."""

from __future__ import annotations

import random

from . import truth
from .models import AgentPersona, Scenario

AGENT_POOL: list[AgentPersona] = [
    AgentPersona.model_validate(
        {
            "id": "nadia",
            "name": "Nadia",
            "role": "Security engineer",
            "style": "threat-models everything; terse",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "eli",
            "name": "Eli",
            "role": "SRE",
            "style": "incident-scarred, asks about failure modes",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "grace",
            "name": "Grace",
            "role": "Engineering director",
            "style": "big-picture, budget-aware",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "lena",
            "name": "Lena",
            "role": "HR partner",
            "style": "listens for how people treat others",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "kai",
            "name": "Kai",
            "role": "Release manager",
            "style": "process-minded, risk-averse",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "ravi",
            "name": "Ravi",
            "role": "Platform engineer",
            "style": "systems-minded, traces dependencies",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "mei",
            "name": "Mei",
            "role": "Product manager",
            "style": "customer-focused, clarifies tradeoffs",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "theo",
            "name": "Theo",
            "role": "Data engineer",
            "style": "methodical, follows the numbers",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "ines",
            "name": "Ines",
            "role": "Support lead",
            "style": "empathetic, tests the edge cases",
        }
    ),
    AgentPersona.model_validate(
        {
            "id": "felix",
            "name": "Felix",
            "role": "Finance partner",
            "style": "numbers-driven, questions the cost",
        }
    ),
]


def _agents_for(
    base: Scenario, n_agents: int, agent_pool: list[AgentPersona]
) -> list[AgentPersona]:
    if n_agents < 1:
        raise ValueError("n_agents must be at least 1")
    agents = list(base.agents[:n_agents])
    if len(agents) < n_agents:
        used = {agent.id for agent in agents}
        extras = [agent for agent in agent_pool if agent.id not in used]
        agents.extend(extras[: n_agents - len(agents)])
    if len(agents) != n_agents:
        raise ValueError(
            f"cannot build {n_agents} agents: base has {len(base.agents)} and "
            f"agent pool has only {len(agent_pool)} usable extras"
        )
    return agents


def redistribute(
    base: Scenario, n_agents: int, seed: int, agent_pool: list[AgentPersona] | None = None
) -> Scenario:
    """Redeal unique facts while preserving the hidden-profile invariant."""
    decisive = truth.decisive_fact_ids(base)
    if len(decisive) < n_agents:
        raise ValueError(
            f"cannot deal {n_agents} agents: only {len(decisive)} decisive unique facts"
        )

    agents = _agents_for(base, n_agents, AGENT_POOL if agent_pool is None else agent_pool)
    agent_ids = [agent.id for agent in agents]
    shared = sorted(truth.shared_fact_ids(base))
    unique = truth.unique_fact_ids(base)
    counter = unique - decisive
    wrong = truth.shared_only_verdict(base)
    right = truth.pooled_verdict(base)

    for attempt in range(200):
        rng = random.Random(seed * 100_003 + attempt)
        shuffled_decisive = list(decisive)
        shuffled_counter = list(counter)
        rng.shuffle(shuffled_decisive)
        rng.shuffle(shuffled_counter)
        hands: dict[str, list[str]] = {agent_id: list(shared) for agent_id in agent_ids}

        position = 0
        for fact_id in shuffled_decisive:
            hands[agent_ids[position % n_agents]].append(fact_id)
            position += 1
        for fact_id in shuffled_counter:
            hands[agent_ids[position % n_agents]].append(fact_id)
            position += 1

        candidate = base.model_copy(
            update={
                "id": (
                    f"{base.id.rsplit('-v', 1)[0]}-{n_agents}"
                    if "-v" in base.id
                    else f"{base.id}-{n_agents}"
                ),
                "title": f"{base.title} ({n_agents} panelists)",
                "agents": agents,
                "distribution": {agent_id: sorted(held) for agent_id, held in hands.items()},
                "validation": None,
            }
        )
        if not truth.is_hidden_profile(candidate):
            continue
        if all(truth.verdict(candidate, hand) == wrong for hand in hands.values()) and (
            truth.pooled_verdict(candidate) == right
        ):
            return candidate

    raise RuntimeError(
        f"redistribute({base.id}, {n_agents}) failed after 200 attempts; "
        "no deal preserved the hidden-profile invariant"
    )

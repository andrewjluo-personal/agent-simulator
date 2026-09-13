"""Generate N-agent variants of a hidden-profile scenario by redealing the
unique facts. Shared facts go to everyone; uniques are dealt round-robin under
a seeded shuffle; the result must keep the invariant: every hand alone still
verdicts the wrong candidate and pooled verdicts the right one."""

from __future__ import annotations

import random

from . import truth
from .models import AgentPersona, Scenario

# Named panelist personas to extend a base agent list when a variant needs more
# panelists than the base scenario has.
AGENT_POOL: list[AgentPersona] = [
    AgentPersona.model_validate(p)
    for p in [
        {"id": "nadia", "name": "Nadia", "role": "Security engineer", "style": "threat-models everything; terse"},
        {"id": "eli", "name": "Eli", "role": "SRE", "style": "incident-scarred, asks about failure modes"},
        {"id": "grace", "name": "Grace", "role": "Engineering director", "style": "big-picture, budget-aware"},
        {"id": "omar", "name": "Omar", "role": "Peer engineer", "style": "collegial, detail-oriented"},
        {"id": "lena", "name": "Lena", "role": "HR partner", "style": "listens for how people treat others"},
        {"id": "kai", "name": "Kai", "role": "Release manager", "style": "process-minded, risk-averse"},
    ]
]


def _agents_for(base: Scenario, n_agents: int, agent_pool: list[AgentPersona]) -> list[AgentPersona]:
    agents = list(base.agents[:n_agents])
    if len(agents) < n_agents:
        used = {a.id for a in agents}
        extras = [p for p in agent_pool if p.id not in used]
        agents.extend(extras[: n_agents - len(agents)])
    if len(agents) != n_agents:
        raise ValueError(
            f"cannot build {n_agents} agents: base has {len(base.agents)}, pool short"
        )
    return agents


def redistribute(
    base: Scenario, n_agents: int, seed: int, agent_pool: list[AgentPersona] | None = None
) -> Scenario:
    agents = _agents_for(base, n_agents, agent_pool or AGENT_POOL)
    agent_ids = [a.id for a in agents]

    shared = sorted(
        f.id for f in base.facts if len(truth.holders(base, f.id)) == len(base.agents)
    )
    uniques = [f.id for f in base.facts if len(truth.holders(base, f.id)) < len(base.agents)]

    wrong = truth.shared_only_verdict(base)
    right = truth.pooled_verdict(base)
    decisive = [fid for fid in uniques if fid in truth.decisive_fact_ids(base)]
    filler = [fid for fid in uniques if fid not in truth.decisive_fact_ids(base)]

    for attempt in range(200):
        rng = random.Random(seed * 100_003 + attempt)
        dec = list(decisive)
        fill = list(filler)
        rng.shuffle(dec)
        rng.shuffle(fill)
        hands: dict[str, list[str]] = {a: list(shared) for a in agent_ids}
        # guarantee each agent at least one decisive fact when possible
        pos = 0
        for fid in dec:
            hands[agent_ids[pos % n_agents]].append(fid)
            pos += 1
        for fid in fill:
            hands[agent_ids[pos % n_agents]].append(fid)
            pos += 1

        candidate = base.model_copy(
            update={
                "id": f"{base.id.rsplit('-v', 1)[0]}-{n_agents}"
                if "-v" in base.id
                else f"{base.id}-{n_agents}",
                "title": f"{base.title} ({n_agents} panelists)",
                "agents": agents,
                "distribution": {a: sorted(h) for a, h in hands.items()},
                "validation": None,
            }
        )
        if not truth.is_hidden_profile(candidate):
            continue
        if all(truth.verdict(candidate, h) == wrong for h in hands.values()) and (
            truth.pooled_verdict(candidate) == right
        ):
            return candidate

    raise RuntimeError(
        f"redistribute({base.id}, {n_agents}) failed: no seed in 200 tries kept "
        f"the hidden-profile invariant"
    )

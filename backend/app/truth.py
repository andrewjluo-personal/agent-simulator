"""Ground-truth scoring over a scenario's fact distribution. Pure functions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .models import Scenario

UNDECIDED = "undecided"


def _signed_weight(scenario: Scenario, fact_id: str) -> tuple[str, int]:
    fact = scenario.fact(fact_id)
    return fact.candidate_id, fact.weight if fact.valence == "pro" else -fact.weight


def scores(scenario: Scenario, fact_ids: Iterable[str]) -> dict[str, int]:
    totals = {c.id: 0 for c in scenario.candidates}
    for fact_id in set(fact_ids):
        candidate_id, signed = _signed_weight(scenario, fact_id)
        totals[candidate_id] += signed
    return totals


def verdict(scenario: Scenario, fact_ids: Iterable[str]) -> str:
    totals = scores(scenario, fact_ids)
    best = max(totals.values()) if totals else 0
    winners = [cid for cid, total in totals.items() if total == best]
    return winners[0] if len(winners) == 1 else UNDECIDED


def holders(scenario: Scenario, fact_id: str) -> list[str]:
    return [agent_id for agent_id, held in scenario.distribution.items() if fact_id in held]


def shared_fact_ids(scenario: Scenario) -> set[str]:
    return {
        f.id for f in scenario.facts if len(holders(scenario, f.id)) == len(scenario.agents)
    }


def unique_fact_ids(scenario: Scenario) -> set[str]:
    return {f.id for f in scenario.facts if len(holders(scenario, f.id)) == 1}


def pooled_fact_ids(scenario: Scenario) -> set[str]:
    pooled: set[str] = set()
    for held in scenario.distribution.values():
        pooled.update(held)
    return pooled


def pooled_verdict(scenario: Scenario) -> str:
    return verdict(scenario, pooled_fact_ids(scenario))


def shared_only_verdict(scenario: Scenario) -> str:
    return verdict(scenario, shared_fact_ids(scenario))


def alone_votes(scenario: Scenario) -> dict[str, str]:
    return {
        agent_id: verdict(scenario, held)
        for agent_id, held in scenario.distribution.items()
    }


def decisive_fact_ids(scenario: Scenario) -> set[str]:
    """Unique facts that favor the pooled-correct candidate."""
    correct = pooled_verdict(scenario)
    if correct == UNDECIDED:
        return set()
    out: set[str] = set()
    for fact_id in unique_fact_ids(scenario):
        fact = scenario.fact(fact_id)
        if (fact.valence == "pro") == (fact.candidate_id == correct):
            out.add(fact_id)
    return out


def is_hidden_profile(scenario: Scenario) -> bool:
    pooled = pooled_verdict(scenario)
    return pooled != UNDECIDED and shared_only_verdict(scenario) != pooled


def _majority(choices: Iterable[str]) -> str:
    tally = Counter(c for c in choices if c != UNDECIDED)
    if not tally:
        return UNDECIDED
    best = max(tally.values())
    winners = [cid for cid, n in tally.items() if n == best]
    return winners[0] if len(winners) == 1 else UNDECIDED

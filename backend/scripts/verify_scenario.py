"""Verify a sample scenario's hidden-profile arithmetic.

Usage: .venv/bin/python scripts/verify_scenario.py [--id hiring-panel-v1]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import truth
from app.models import Scenario
from app.samples import SAMPLES_BY_ID
from app.scenario import DEFAULT_SCENARIO_ID


def show(scenario: Scenario, label: str, fact_ids: set[str] | list[str]) -> None:
    totals = truth.scores(scenario, fact_ids)
    for c in scenario.candidates:
        pros = sum(
            f.weight
            for f in scenario.facts
            if f.id in set(fact_ids) and f.candidate_id == c.id and f.valence == "pro"
        )
        cons = sum(
            f.weight
            for f in scenario.facts
            if f.id in set(fact_ids) and f.candidate_id == c.id and f.valence == "con"
        )
        print(f"  {c.id} {label}: pros {pros} − cons {cons} = {totals[c.id]}")
    print(f"  {label} verdict: {truth.verdict(scenario, fact_ids)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=DEFAULT_SCENARIO_ID)
    args = parser.parse_args()
    scenario = SAMPLES_BY_ID.get(args.id)
    if scenario is None:
        print(f"unknown sample scenario {args.id!r}")
        return 1
    shared = truth.shared_fact_ids(scenario)
    pooled = truth.pooled_fact_ids(scenario)
    unique = truth.unique_fact_ids(scenario)
    decisive = truth.decisive_fact_ids(scenario)
    print(
        f"scenario: {scenario.id} ({len(scenario.facts)} facts, "
        f"{len(shared)} shared, {len(unique)} unique)"
    )
    show(scenario, "shared-only", shared)
    show(scenario, "pooled", pooled)
    for agent_id, held in scenario.distribution.items():
        print(f"  {agent_id} alone: {truth.verdict(scenario, held)}")
    print(f"  decisive unique facts ({len(decisive)}): {sorted(decisive)}")
    ok = truth.is_hidden_profile(scenario)
    print(f"HIDDEN PROFILE: {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

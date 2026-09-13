"""Verify the bundled scenario's hidden-profile arithmetic.

Usage: .venv/bin/python scripts/verify_scenario.py [path-to-scenario.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import truth
from app.models import Scenario
from app.scenario import DEFAULT_SCENARIO_ID, load_scenario


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
    if len(sys.argv) > 1:
        scenario = Scenario.model_validate(json.loads(Path(sys.argv[1]).read_text()))
    else:
        scenario = load_scenario(DEFAULT_SCENARIO_ID)
    shared = truth.shared_fact_ids(scenario)
    pooled = truth.pooled_fact_ids(scenario)
    unique = truth.unique_fact_ids(scenario)
    decisive = truth.decisive_fact_ids(scenario)
    print(f"scenario: {scenario.id} ({len(scenario.facts)} facts, "
          f"{len(shared)} shared, {len(unique)} unique)")
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

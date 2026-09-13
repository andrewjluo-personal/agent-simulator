"""Generate an N-agent variant of a base scenario and store it.

Usage:
  .venv/bin/python scripts/make_scenario.py --base hiring-panel-v1 --agents 7 \
      --seed 1 [--id hiring-panel-7] [--title "..."] [--dry-run] [--emit-python]
"""

from __future__ import annotations

import argparse
import pprint
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import scenario_gen, truth
from app.samples import SAMPLES_BY_ID
from app.scenario import load_scenario
from app.store import MemoryStore, Store


def get_store() -> Store:
    import os

    if os.getenv("DATABASE_URL"):
        from app import db

        return db.PgStore()
    return MemoryStore()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--agents", type=int, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--id")
    parser.add_argument("--title")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--emit-python", action="store_true")
    args = parser.parse_args()

    store = get_store()
    base = store.get_scenario(args.base) or SAMPLES_BY_ID.get(args.base)
    if base is None:
        print(f"unknown base scenario {args.base!r}")
        return 1
    # if the store holds a stale/other id, prefer it; load via store anyway
    try:
        base = load_scenario(store, args.base)
    except KeyError:
        pass

    scenario = scenario_gen.redistribute(base, args.agents, args.seed)
    if args.id:
        scenario = scenario.model_copy(update={"id": args.id})
    if args.title:
        scenario = scenario.model_copy(update={"title": args.title})
    scenario = scenario.model_copy(update={"is_sample": True})

    print(f"scenario: {scenario.id} ({len(scenario.facts)} facts, {len(scenario.agents)} agents)")
    for label, ids in (
        ("shared-only", truth.shared_fact_ids(scenario)),
        ("pooled", truth.pooled_fact_ids(scenario)),
    ):
        print(f"  {label}: {truth.scores(scenario, ids)} -> {truth.verdict(scenario, ids)}")
    for agent_id, held in scenario.distribution.items():
        print(
            f"  {agent_id} alone: {truth.scores(scenario, held)} -> {truth.verdict(scenario, held)}"
        )

    if args.emit_python:
        body = pprint.pformat(
            scenario.model_dump(by_alias=True, exclude={"validation"}), width=100, sort_dicts=False
        )
        print("\n    Scenario.model_validate(")
        print("    " + body.replace("\n", "\n    "))
        print("    ),")
    if not args.dry_run:
        store.upsert_scenario(scenario)
        print(f"upserted {scenario.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

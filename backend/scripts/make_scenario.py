"""Generate an N-agent variant of a base scenario and optionally store it."""

from __future__ import annotations

import argparse
import pprint
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import scenario_gen, truth
from app.samples import SAMPLES_BY_ID
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
    base = SAMPLES_BY_ID.get(args.base) or store.get_scenario(args.base)
    if base is None:
        print(f"unknown base scenario {args.base!r}")
        return 1

    scenario = scenario_gen.redistribute(base, args.agents, args.seed)
    if args.id:
        scenario = scenario.model_copy(update={"id": args.id})
    if args.title:
        scenario = scenario.model_copy(update={"title": args.title})

    print(f"scenario: {scenario.id} ({len(scenario.facts)} facts, {len(scenario.agents)} agents)")
    print(
        f"  shared-only: {truth.scores(scenario, truth.shared_fact_ids(scenario))} -> "
        f"{truth.shared_only_verdict(scenario)}"
    )
    print(
        f"  pooled: {truth.scores(scenario, truth.pooled_fact_ids(scenario))} -> "
        f"{truth.pooled_verdict(scenario)}"
    )
    for agent_id, held in scenario.distribution.items():
        print(
            f"  {agent_id} alone: {truth.scores(scenario, held)} -> {truth.verdict(scenario, held)}"
        )

    if args.emit_python:
        body = pprint.pformat(
            scenario.model_dump(by_alias=True, exclude={"validation"}, exclude_none=True),
            sort_dicts=False,
            width=100,
        )
        print("Scenario.model_validate(")
        print(body)
        print(")")
    if not args.dry_run:
        store.upsert_scenario(scenario)
        print(f"upserted {scenario.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

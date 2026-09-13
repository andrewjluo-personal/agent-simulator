"""Validate a scenario's hidden-profile shape with alone ballots.

Usage:
  .venv/bin/python scripts/validate_scenario.py hiring-panel-v1 \
      [--model claude-haiku-4-5] [--trials 10] [--provider anthropic|fake] [--no-save]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import llm, truth, validator
from app.models import Scenario
from app.scenario import DEFAULT_SCENARIO_ID
from app.store import MemoryStore, Store


def get_store() -> Store:
    if os.getenv("DATABASE_URL"):
        from app import db

        return db.PgStore()
    return MemoryStore()


def print_arithmetic(scenario: Scenario) -> None:
    shared = truth.shared_fact_ids(scenario)
    pooled = truth.pooled_fact_ids(scenario)
    for label, ids in (("shared-only", shared), ("pooled", pooled)):
        totals = truth.scores(scenario, ids)
        print(f"  {label}: {totals} -> {truth.verdict(scenario, ids)}")
    for agent_id, held in scenario.distribution.items():
        print(
            f"  {agent_id} alone: {truth.scores(scenario, held)} -> {truth.verdict(scenario, held)}"
        )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario_id", nargs="?", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--provider", choices=["fake", "anthropic"], default="fake")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    store = get_store()
    scenario = store.get_scenario(args.scenario_id)
    if scenario is None:
        print(f"unknown scenario {args.scenario_id!r}")
        return 1
    print(f"scenario: {scenario.id}")
    print_arithmetic(scenario)

    client: llm.LLMClient = llm.FakeClient() if args.provider == "fake" else llm.AnthropicClient()
    result = await validator.validate_scenario(
        scenario, client, model=args.model, trials=args.trials
    )
    for agent_id, rate in result.alone_wrong_rate.items():
        print(f"  {agent_id}: alone-wrong rate {rate:.2f}")
    print(f"  pooled-right rate: {result.pooled_right_rate:.2f}")
    print(f"VALIDATION: {'PASS' if result.passed else 'FAIL'}")

    if not args.no_save:
        validation = dict(scenario.validation or {})
        validation[args.model] = result
        store.upsert_scenario(scenario.model_copy(update={"validation": validation}))
        print(f"saved validation[{args.model}] to store")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

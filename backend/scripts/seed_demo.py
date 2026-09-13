"""Seed demo runs against the configured store.

Usage:
  .venv/bin/python scripts/seed_demo.py --n 10 --provider fake \
      --paradigms free_discussion,share_first --rounds 3 --sentences 2 \
      [--scenario hiring-panel-v1] [--reset-demo]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import llm, orchestrator
from app.models import Paradigm, RunConfig
from app.paradigms import PARADIGMS
from app.samples import ensure_samples
from app.scenario import DEFAULT_SCENARIO_ID
from app.store import MemoryStore, Store


def get_store() -> Store:
    import os

    from app import db

    if os.getenv("DATABASE_URL"):
        return db.PgStore()
    return MemoryStore()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--provider", choices=["fake", "anthropic"], default="fake")
    parser.add_argument("--paradigms", default="free_discussion,share_first")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--sentences", type=int, default=2)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--reset-demo", action="store_true")
    args = parser.parse_args()

    client: llm.LLMClient
    if args.provider == "fake":
        client = llm.FakeClient()
    else:
        client = llm.AnthropicClient()
    store = get_store()
    ensure_samples(store)
    if store.get_scenario(args.scenario) is None:
        sys.exit(f"unknown scenario {args.scenario!r}")
    if args.reset_demo:
        print(f"deleted {store.delete_demo_runs()} demo runs")

    sem = asyncio.Semaphore(4)
    paradigms = [p.strip() for p in args.paradigms.split(",") if p.strip()]
    for p in paradigms:
        if p not in PARADIGMS:
            sys.exit(f"unknown paradigm {p!r}")

    async def one_run(paradigm: str, seed: int) -> None:
        cfg = RunConfig(
            scenario_id=args.scenario,
            paradigm=cast("Paradigm", paradigm),
            rounds=args.rounds,
            sentences_per_turn=args.sentences,
            seed=seed,
        )
        run = orchestrator.new_run(store, cfg, provider=client.provider, is_demo=True)
        store.create_run(run)
        async with sem:
            await orchestrator.run_to_completion(store, client, run.id)

    for paradigm in paradigms:
        await asyncio.gather(*(one_run(paradigm, i) for i in range(args.n)))
        runs = [
            store.get_run(s.id) for s in store.list_runs(is_demo=True, scenario_id=args.scenario)
        ]
        these = [r for r in runs if r and r.config.paradigm == paradigm and r.metrics]
        correct = sum(1 for r in these if r.metrics and r.metrics.correct)
        surfaced = [r.metrics.decisive_surfaced for r in these if r.metrics]
        mean = sum(surfaced) / len(surfaced) if surfaced else 0.0
        print(f"{paradigm}: {correct}/{len(these)} correct, mean decisive surfaced {mean:.2f}")


if __name__ == "__main__":
    asyncio.run(main())

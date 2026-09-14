"""Seed demo runs against the configured store. Idempotent per engine version:
tops up each paradigm to --per-paradigm done runs stamped with the current
ENGINE_VERSION, and unless --keep-stale removes demo runs from older versions.

Usage:
  .venv/bin/python scripts/seed_demo.py --per-paradigm 5 --provider fake \
      --paradigms free_discussion,share_first --rounds 3 --sentences 2 \
      [--scenario hiring-panel-flat-v2] [--reset-demo] [--keep-stale]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import llm, orchestrator
from app.engine_version import ENGINE_VERSION
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
    parser.add_argument("--per-paradigm", "--n", dest="per_paradigm", type=int, default=5)
    parser.add_argument("--provider", choices=["fake", "anthropic"], default="fake")
    parser.add_argument("--paradigms", default="free_discussion,share_first")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--sentences", type=int, default=2)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--reset-demo", action="store_true")
    parser.add_argument("--keep-stale", action="store_true")
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
    elif not args.keep_stale:
        print(
            f"deleted {store.delete_stale_demo_runs(ENGINE_VERSION)} stale demo runs "
            f"(engine != {ENGINE_VERSION})"
        )

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
        existing = len(
            [
                s
                for s in store.list_runs(is_demo=True, scenario_id=args.scenario)
                if s.config.paradigm == paradigm
                and s.status == "done"
                and s.engine_version == ENGINE_VERSION
            ]
        )
        create = max(0, args.per_paradigm - existing)
        print(f"{paradigm}: had {existing}, creating {create}")
        await asyncio.gather(*(one_run(paradigm, existing + i) for i in range(create)))
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

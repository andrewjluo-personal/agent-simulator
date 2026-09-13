"""Seed demo runs against the configured store and write a DemoSnapshot JSON.

Usage:
  .venv/bin/python scripts/seed_demo.py --n 10 --provider fake \
      --paradigms free_discussion,share_first --rounds 3 --sentences 2 \
      --out ../frontend/src/demo/snapshot.json [--reset-demo]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import llm, orchestrator
from app.models import DemoSnapshot
from app.paradigms import PARADIGMS
from app.scenario import load_scenario
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
    parser.add_argument("--out", default="../frontend/src/demo/snapshot.json")
    parser.add_argument("--reset-demo", action="store_true")
    args = parser.parse_args()

    client: llm.LLMClient
    if args.provider == "fake":
        client = llm.FakeClient()
    else:
        client = llm.AnthropicClient()
    store = get_store()
    if args.reset_demo:
        print(f"deleted {store.delete_demo_runs()} demo runs")

    sem = asyncio.Semaphore(4)
    paradigms = [p.strip() for p in args.paradigms.split(",") if p.strip()]
    for p in paradigms:
        if p not in PARADIGMS:
            sys.exit(f"unknown paradigm {p!r}")

    async def one_run(paradigm: str, seed: int) -> None:
        from typing import cast

        from app.models import Paradigm, RunConfig

        cfg = RunConfig(
            paradigm=cast("Paradigm", paradigm),
            rounds=args.rounds,
            sentences_per_turn=args.sentences,
            seed=seed,
        )
        run = orchestrator.new_run(cfg, provider=client.provider, is_demo=True)
        store.create_run(run)
        async with sem:
            await orchestrator.run_to_completion(store, client, run.id)

    for paradigm in paradigms:
        await asyncio.gather(*(one_run(paradigm, i) for i in range(args.n)))
        runs = [
            store.get_run(s.id) for s in store.list_runs(is_demo=True)
        ]
        these = [r for r in runs if r and r.config.paradigm == paradigm and r.metrics]
        correct = sum(1 for r in these if r.metrics and r.metrics.correct)
        surfaced = [r.metrics.decisive_surfaced for r in these if r.metrics]
        mean = sum(surfaced) / len(surfaced) if surfaced else 0.0
        print(
            f"{paradigm}: {correct}/{len(these)} correct, "
            f"mean decisive surfaced {mean:.2f}"
        )

    summaries = store.list_runs(is_demo=True)[:100]
    full_runs = []
    for s in summaries:
        r = store.get_run(s.id)
        if r is not None:
            full_runs.append(r)
    snapshot = DemoSnapshot(scenario=load_scenario(), runs=full_runs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(snapshot.model_dump_json(by_alias=True, indent=2))
    print(f"wrote {len(full_runs)} runs to {out}")


if __name__ == "__main__":
    asyncio.run(main())

"""Run the Haiku validator over every paper library and write the badges to JSON.

Usage: .venv/bin/python scripts/validate_libraries.py --out /path/badges.json \
    [--trials 10] [--discussion stasser-1985-hidden=5]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import llm, validator
from app.scenarios.papers import PAPER_SCENARIOS

MODEL = "claude-haiku-4-5"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--only", default="")
    parser.add_argument("--discussion", action="append", default=[], help="id=runs")
    args = parser.parse_args()
    discussion = dict(kv.split("=") for kv in args.discussion)
    only = {s for s in args.only.split(",") if s}

    client = llm.AnthropicClient()
    out_path = Path(args.out)
    badges: dict[str, dict[str, object]] = (
        json.loads(out_path.read_text()) if out_path.exists() else {}
    )
    for scenario in PAPER_SCENARIOS:
        if only and scenario.id not in only:
            continue
        if scenario.id in badges:
            print(f"skip {scenario.id} (already done)")
            continue
        print(f"validating {scenario.id} ...", flush=True)
        result = await validator.validate_scenario(
            scenario, client, model=MODEL, trials=args.trials
        )
        runs = int(discussion.get(scenario.id, 0))
        if runs:
            rate, n = await validator.free_discussion_rate(
                scenario, client, runs=runs, provider="anthropic"
            )
            result = result.model_copy(
                update={"free_discussion_rate": rate, "free_discussion_runs": n}
            )
        badges[scenario.id] = result.model_dump(by_alias=True)
        out_path.write_text(json.dumps(badges, indent=2))
        print(f"  {scenario.id}: {json.dumps(badges[scenario.id])}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

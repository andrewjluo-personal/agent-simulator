"""Calibrate scenario fact items: rate each fact's standalone importance N times
and check the unique-vs-shared gap (generalised port of scripts/probe/calibrate.py).

Usage:
  .venv/bin/python scripts/calibrate_items.py --scenario hiring-panel-flat \
      --samples 5 [--model claude-haiku-4-5] [--out json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("LOG_LEVEL", "WARNING")

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from probe_free_discussion import load_probe_scenario

from app import truth
from app.calibration import gap_check
from app.llm import AnthropicClient, LLMClient, LLMRequest
from app.models import Scenario


def rating_system(scenario: Scenario) -> str:
    options = "|".join(c.id for c in scenario.candidates) + "|neutral"
    return f"""{scenario.brief}
You will be shown ONE observation from an interviewer's notes. Rate how much that single
observation, on its own, should move a reasonable panel's recommendation.
Scale: 1 = trivial/minor, 2 = a small point, 3 = a solid point, 4 = a major factor,
5 = decisive on its own.
Respond with JSON only: {{"rating": 1..5, "direction": "{options}"}}"""


async def rate(
    client: LLMClient, system: str, model: str, text: str, samples: int, sem: asyncio.Semaphore
) -> list[float]:
    async def one() -> float:
        async with sem:
            resp = await client.complete(
                LLMRequest(system=system, user=text, model=model, max_tokens=60)
            )
        m = re.search(r"\{.*\}", resp.text, re.DOTALL)
        if not m:
            return -1.0
        try:
            return float(json.loads(m.group(0))["rating"])
        except (json.JSONDecodeError, KeyError, TypeError):
            return -1.0

    return list(await asyncio.gather(*(one() for _ in range(samples))))


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--out", choices=["table", "json"], default="table")
    args = parser.parse_args()

    scenario = load_probe_scenario(args.scenario)
    anthropic = AnthropicClient()
    sem = asyncio.Semaphore(6)
    system = rating_system(scenario)
    results = await asyncio.gather(
        *(
            rate(anthropic, system, args.model, f.memo_text or f.text, args.samples, sem)
            for f in scenario.facts
        )
    )
    ratings = {f.id: r for f, r in zip(scenario.facts, results, strict=True)}
    shared = truth.shared_fact_ids(scenario)
    res = gap_check(ratings, shared)

    if args.out == "json":
        print(
            json.dumps(
                {
                    "scenario_id": scenario.id,
                    "samples": args.samples,
                    "model": args.model,
                    "ratings": ratings,
                    "shared_mean": res.shared_mean,
                    "unique_mean": res.unique_mean,
                    "gap": res.gap,
                    "passes": res.passes,
                    "per_item": res.per_item,
                }
            )
        )
        return 0 if res.passes else 1

    rows = [
        (
            "shared" if f.id in shared else "unique",
            f.id,
            f.valence,
            f.weight,
            res.per_item.get(f.id, 0.0),
            f.memo_text or f.text,
        )
        for f in scenario.facts
    ]
    rows.sort(key=lambda r: (r[0], -r[4]))
    for kind, fid, val, w, avg, txt in rows:
        print(f"{kind:6} {fid:5} {val:3} w={w} rated={avg:.2f}  {txt}")
    print(f"unique mean {res.unique_mean:.2f}")
    print(f"shared mean {res.shared_mean:.2f}")
    print(f"gap {res.gap:+.2f}")
    print(f"CALIBRATION: {'PASS' if res.passes else 'FAIL'} (|gap| < 0.3)")
    return 0 if res.passes else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

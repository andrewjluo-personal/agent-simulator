"""S4: which v3 twin items drive the null Sally lean? Balanced candidate order,
naive prompt, drop-set ablations on the v3 twin null for the pooled reviewer and
for any agent cells that fail the null band."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gate_null import cell_votes
from gate_pool import POOLED, CountingClient
from probe_lib import cost_usd, wilson

from app.llm import AnthropicClient
from app.models import RunConfig, Scenario
from app.samples import (
    FLAT_V3_TYPE,
    FLAT_V3_UNIQUE,
    HIRING_PANEL_FLAT_V3,
    HIRING_PANEL_FLAT_V3_NULL,
)

NULL = HIRING_PANEL_FLAT_V3_NULL
BASE_ID = {f["id"] for f in FLAT_V3_UNIQUE}
CON_IDS = {f.id for f in HIRING_PANEL_FLAT_V3.facts if f.valence == "con"}


def base(fid: str) -> str:
    return fid.removesuffix("x")


def sub(drop: set[str], name: str) -> Scenario:
    keep = [f for f in NULL.facts if f.id not in drop]
    ids = {f.id for f in keep}
    return NULL.model_copy(
        update={
            "id": f"{NULL.id}-{name}",
            "facts": keep,
            "distribution": {a: [i for i in h if i in ids] for a, h in NULL.distribution.items()},
        }
    )


def by_type(t: str) -> set[str]:
    return {f.id for f in NULL.facts if FLAT_V3_TYPE[base(f.id)] == t}


def twins(*bases: str) -> set[str]:
    return {f.id for f in NULL.facts if base(f.id) in set(bases)}


CONDITIONS: dict[str, set[str]] = {
    "baseline": set(),
    "no_VU3": twins("VU3"),
    "no_uniques": {f.id for f in NULL.facts if base(f.id) in BASE_ID},
    "no_behavioural": by_type("behavioural"),
    "no_rigour": by_type("rigour"),
    "no_cons": {f.id for f in NULL.facts if base(f.id) in CON_IDS},
}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="+", default=["pooled", "priya"])
    ap.add_argument("--conds", nargs="+", default=list(CONDITIONS))
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--prompt", default="naive")
    ap.add_argument("--out", default="scripts/probe/out/s4_null_ablate.json")
    args = ap.parse_args()
    client = CountingClient(AnthropicClient())
    out: dict[str, dict[str, object]] = {}
    for name in args.conds:
        s = sub(CONDITIONS[name], name)
        row: dict[str, object] = {"n_items": len(s.facts)}
        for cell in args.cells:
            agent = POOLED if cell == "pooled" else next(a for a in s.agents if a.id == cell)
            hand = [f.id for f in s.facts] if cell == "pooled" else list(s.distribution[cell])
            cfg = RunConfig(prompt_style=args.prompt, fact_style="memo", seed=0)  # type: ignore[arg-type]
            per_seed, by_order = await cell_votes(
                client, s, agent, hand, cfg, "balanced", 1, args.samples
            )
            k = sum(c["sally"] for c in per_seed)
            _rate, lo, hi = wilson(k, args.samples)
            row[cell] = {
                "sally": k,
                "n": args.samples,
                "ci": [lo, hi],
                "by_order": {o: dict(c) for o, c in by_order.items()},
            }
            print(
                f"{name:<15} {cell:<7} items={len(hand):<3} sally={k}/{args.samples} "
                f"[{lo:.2f},{hi:.2f}] { {o: dict(c) for o, c in by_order.items()} }"
            )
        out[name] = row
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"~${cost_usd(client.input_tokens, client.output_tokens):.2f}")


if __name__ == "__main__":
    asyncio.run(main())

"""S4: which v3 twin items drive the pooled-null Sally lean? Pooled reviewer only,
John listed first (order=fixed), seeds 0-7, drop-one-type ablations on the v3 twin null."""

from __future__ import annotations

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


CONDITIONS: dict[str, set[str]] = {
    "baseline": set(),
    "no_behavioural": by_type("behavioural"),
    "no_rigour": by_type("rigour"),
    "no_cons": {f.id for f in NULL.facts if base(f.id) in CON_IDS},
    "no_uniques": {f.id for f in NULL.facts if base(f.id) in BASE_ID},
}


async def main() -> None:
    client = CountingClient(AnthropicClient())
    out: dict[str, dict[str, object]] = {}
    for name, drop in CONDITIONS.items():
        s = sub(drop, name)
        hand = [f.id for f in s.facts]
        row: dict[str, object] = {"n_items": len(hand)}
        for style in ("naive", "default"):
            cfg = RunConfig(prompt_style=style, candidate_order="fixed", fact_style="memo", seed=0)  # type: ignore[arg-type]
            per_seed = await cell_votes(client, s, POOLED, hand, cfg, 8, 1)
            k = sum(c["sally"] for c in per_seed)
            _rate, lo, hi = wilson(k, 8)
            row[style] = {"sally": k, "ci": [lo, hi], "votes": [dict(c) for c in per_seed]}
            print(f"{name:<15} {style:<8} items={len(hand):<3} sally={k}/8 [{lo:.2f},{hi:.2f}]")
        out[name] = row
    Path("scripts/probe/out/s4_null_ablate.json").write_text(json.dumps(out, indent=1))
    print(f"~${cost_usd(client.input_tokens, client.output_tokens):.2f}")


if __name__ == "__main__":
    asyncio.run(main())

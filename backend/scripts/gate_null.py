"""Null gate: on a symmetric pool the pooled reviewer and every agent alone must be
within [lo,hi] Sally under the run prompt; sweeps seeds so memo order / candidate
order vary.

Usage:
  .venv/bin/python scripts/gate_null.py hiring-panel-null [--prompt naive default]
      [--samples 10] [--seeds 2] [--order random|fixed] [--lo 0.35 --hi 0.65]
      [--out scripts/probe/out/gate_null]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from gate_pool import MODEL, POOLED, CountingClient
from probe_lib import cost_usd, load_scenario_arg, wilson

from app import prompts, truth, validate
from app.llm import AnthropicClient, LLMClient, LLMRequest
from app.models import AgentPersona, CandidateOrder, PromptStyle, RunConfig, Scenario
from app.paradigms import get_paradigm


def within(rate: float, lo: float, hi: float) -> bool:
    return lo <= rate <= hi


async def cell_votes(
    client: LLMClient,
    scenario: Scenario,
    agent: AgentPersona,
    hand: list[str],
    cfg: RunConfig,
    seeds: int,
    samples: int,
) -> list[Counter[str]]:
    """One Counter per seed; each Counter holds `samples` ballots at distinct seeds."""
    spec = get_paradigm(cfg.paradigm)
    ids = {c.id for c in scenario.candidates}

    async def one(seed: int) -> str:
        cell_cfg = cfg.model_copy(update={"seed": seed})
        system = prompts.system_prompt(scenario, cell_cfg, agent, hand, spec)
        user = prompts.alone_vote_message(scenario, cell_cfg)
        resp = await client.complete(
            LLMRequest(system=system, user=user, model=MODEL, max_tokens=200)
        )
        raw = validate.parse_json_object(resp.text) or {}
        v = raw.get("vote")
        return v if isinstance(v, str) and v in ids else truth.UNDECIDED

    votes = await asyncio.gather(*(one(s * 1000 + j) for s in range(seeds) for j in range(samples)))
    return [Counter(votes[s * samples : (s + 1) * samples]) for s in range(seeds)]


async def gate(
    client: LLMClient,
    scenario: Scenario,
    style: PromptStyle,
    order: CandidateOrder,
    samples: int,
    seeds: int,
    lo: float,
    hi: float,
) -> dict[str, Any]:
    cfg = RunConfig(prompt_style=style, candidate_order=order, fact_style="memo", seed=0)
    target = scenario.candidates[1].id
    cells: dict[str, tuple[AgentPersona, list[str]]] = {
        "pooled": (POOLED, sorted(truth.pooled_fact_ids(scenario)))
    }
    for a in scenario.agents:
        cells[a.id] = (a, list(scenario.distribution[a.id]))

    result_cells: dict[str, Any] = {}
    for cell_id, (agent, hand) in cells.items():
        per_seed = await cell_votes(client, scenario, agent, hand, cfg, seeds, samples)
        n = seeds * samples
        k = sum(c[target] for c in per_seed)
        rate, ci_lo, ci_hi = wilson(k, n)
        result_cells[cell_id] = {
            "n": n,
            "counts": dict(sum(per_seed, Counter())),
            "per_seed": [dict(c) for c in per_seed],
            "rate": rate,
            "ci": [ci_lo, ci_hi],
            "pass": within(rate, lo, hi),
        }
    return {
        "scenario": scenario.id,
        "prompt": style,
        "order": order,
        "target": target,
        "lo": lo,
        "hi": hi,
        "cells": result_cells,
        "pass": all(c["pass"] for c in result_cells.values()),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("--prompt", nargs="+", default=["naive", "default"])
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--order", choices=["random", "fixed"], default="random")
    parser.add_argument("--lo", type=float, default=0.35)
    parser.add_argument("--hi", type=float, default=0.65)
    parser.add_argument("--out", default="scripts/probe/out/gate_null")
    args = parser.parse_args()
    client = CountingClient(AnthropicClient())
    scenario = load_scenario_arg(args.scenario)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for style in args.prompt:
        res = await gate(
            client, scenario, style, args.order, args.samples, args.seeds, args.lo, args.hi
        )
        (out_dir / f"{scenario.id}_{style}_{args.order}.json").write_text(json.dumps(res, indent=1))
        print(f"[{style} order={args.order}] target={res['target']} band=[{args.lo},{args.hi}]")
        for cell_id, cell in res["cells"].items():
            seeds_str = " ".join(str(s) for s in cell["per_seed"])
            status = "ok" if cell["pass"] else "FAIL"
            print(
                f"  {cell_id:<8} n={cell['n']:<3} {res['target']}_rate={cell['rate']:.2f} "
                f"[{cell['ci'][0]:.2f},{cell['ci'][1]:.2f}] seeds={seeds_str} {status}"
            )
        print(f"  -> {'PASS' if res['pass'] else 'FAIL'}")
        ok = ok and res["pass"]
    print(f"~${cost_usd(client.input_tokens, client.output_tokens):.2f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

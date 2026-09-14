"""G0 null gate for symmetric candidate pools.

Usage:
  .venv/bin/python scripts/gate_null.py scenario --prompt naive default
      --samples 8 --seeds 3 [--twin] [--out scripts/probe/out/gate_null]
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
from probe_lib import (
    cost_usd,
    load_scenario_arg,
    rotate_candidates,
    samples_for,
    twin_null,
    wilson,
)

from app import prompts, truth, validate
from app.llm import AnthropicClient, LLMClient, LLMRequest
from app.models import AgentPersona, PromptStyle, RunConfig, Scenario
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
) -> list[dict[str, str]]:
    """Run seeds × samples ballots with balanced cyclic candidate rotations."""
    spec = get_paradigm(cfg.paradigm)
    k = len(scenario.candidates)
    ids = {candidate.id for candidate in scenario.candidates}

    async def one(seed: int, sample: int) -> dict[str, str]:
        rotated = rotate_candidates(scenario, sample % k)
        cell_cfg = cfg.model_copy(update={"seed": seed, "candidate_order": "fixed"})
        system = prompts.system_prompt(rotated, cell_cfg, agent, hand, spec)
        user = prompts.alone_vote_message(rotated, cell_cfg, agent)
        response = await client.complete(
            LLMRequest(system=system, user=user, model=MODEL, max_tokens=200)
        )
        raw = validate.parse_json_object(response.text) or {}
        vote = raw.get("vote")
        return {
            "first_listed": rotated.candidates[0].id,
            "vote": vote if isinstance(vote, str) and vote in ids else truth.UNDECIDED,
        }

    return list(
        await asyncio.gather(
            *(
                one(seed * 1000 + sample, sample)
                for seed in range(seeds)
                for sample in range(samples)
            )
        )
    )


async def gate(
    client: LLMClient,
    scenario: Scenario,
    style: PromptStyle,
    samples: int,
    seeds: int,
    lo: float | None,
    hi: float | None,
) -> dict[str, Any]:
    k = len(scenario.candidates)
    derived_lo = max(0.0, 1 / k - 0.15)
    derived_hi = min(1.0, 1 / k + 0.15)
    band_lo = derived_lo if lo is None else lo
    band_hi = derived_hi if hi is None else hi
    cfg = RunConfig(prompt_style=style, candidate_order="fixed", fact_style="memo", seed=0)
    cells: list[tuple[str, AgentPersona, list[str]]] = [
        ("pooled", POOLED, sorted(truth.pooled_fact_ids(scenario)))
    ]
    cells.extend(
        (agent.id, agent, list(scenario.distribution[agent.id])) for agent in scenario.agents
    )
    result_cells: dict[str, Any] = {}

    for cell_id, agent, hand in cells:
        ballots = await cell_votes(client, scenario, agent, hand, cfg, seeds, samples)
        counts = Counter(ballot["vote"] for ballot in ballots)
        by_first_listed: dict[str, Counter[str]] = {}
        for ballot in ballots:
            by_first_listed.setdefault(ballot["first_listed"], Counter())[ballot["vote"]] += 1
        rates: dict[str, dict[str, Any]] = {}
        for candidate in scenario.candidates:
            rate, ci_lo, ci_hi = wilson(counts[candidate.id], len(ballots))
            rates[candidate.id] = {"rate": rate, "ci": [ci_lo, ci_hi]}
        result_cells[cell_id] = {
            "n": len(ballots),
            "counts": dict(counts),
            "per_seed": [
                dict(
                    Counter(
                        ballot["vote"] for ballot in ballots[seed * samples : (seed + 1) * samples]
                    )
                )
                for seed in range(seeds)
            ],
            "rates": rates,
            "by_first_listed": {key: dict(value) for key, value in by_first_listed.items()},
            "pass": all(
                within(candidate_rate["rate"], band_lo, band_hi)
                for candidate_rate in rates.values()
            ),
        }

    return {
        "scenario": scenario.id,
        "prompt": style,
        "k": k,
        "samples": samples,
        "seeds": seeds,
        "lo": band_lo,
        "hi": band_hi,
        "cells": result_cells,
        "pass": all(cell["pass"] for cell in result_cells.values()),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("--prompt", nargs="+", default=["naive", "default"])
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--lo", type=float)
    parser.add_argument("--hi", type=float)
    parser.add_argument("--twin", action="store_true")
    parser.add_argument("--out", default="scripts/probe/out/gate_null")
    args = parser.parse_args()
    client = CountingClient(AnthropicClient())
    original = load_scenario_arg(args.scenario)
    scenario = original
    if args.twin:
        scenario = twin_null(scenario)
        changed = sum(scenario.fact(f"{fact.id}~1").text != fact.text for fact in original.facts)
        print(f"{original.id}: rotation_1_changed_facts={changed}/{len(original.facts)}")
    samples = samples_for(len(scenario.candidates), args.samples)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True

    for style in args.prompt:
        result = await gate(client, scenario, style, samples, args.seeds, args.lo, args.hi)
        path = out_dir / f"{scenario.id}_{style}.json"
        path.write_text(json.dumps(result, indent=1))
        print(
            f"{scenario.id} [{style}] k={result['k']} n={samples * args.seeds} "
            f"band=[{result['lo']:.2f},{result['hi']:.2f}]"
        )
        for cell_id, cell in result["cells"].items():
            rates = " ".join(
                f"{candidate}={value['rate']:.2f}[{value['ci'][0]:.2f},{value['ci'][1]:.2f}]"
                for candidate, value in cell["rates"].items()
            )
            status = "PASS" if cell["pass"] else "FAIL"
            print(f"  {cell_id:<8} n={cell['n']:<3} {rates} -> {status}")
        print(f"  -> {'PASS' if result['pass'] else 'FAIL'}")
        ok = ok and result["pass"]

    print(f"total ~${cost_usd(client.input_tokens, client.output_tokens):.2f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

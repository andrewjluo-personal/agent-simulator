"""Hidden-profile gate for a scenario, per prompt style.

Gate (per prompt): the pooled single reviewer (all items) picks the designed-correct
candidate >= 80% of samples AND every agent alone picks the other candidate >= 80%.

Usage:
  .venv/bin/python scripts/gate_pool.py hiring-panel-flat [--prompt naive default]
      [--samples 8] [--fact-style memo]
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

from probe_lib import (
    cost_usd,
    designed_correct,
    load_scenario_arg,
    rotate_candidates,
    samples_for,
    wilson,
)

from app import prompts, truth, validate
from app.llm import AnthropicClient, LLMClient, LLMRequest, LLMResponse
from app.models import AgentPersona, PromptStyle, RunConfig, Scenario
from app.paradigms import get_paradigm

MODEL = "claude-haiku-4-5"


class CountingClient:
    provider = "anthropic"

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.input_tokens = 0
        self.output_tokens = 0

    async def complete(self, req: LLMRequest) -> LLMResponse:
        resp = await self.inner.complete(req)
        self.input_tokens += resp.input_tokens or 0
        self.output_tokens += resp.output_tokens or 0
        return resp


POOLED = AgentPersona(
    id="pooled",
    name="Reviewer",
    role="reviewer with every panelist's notes",
    style="balanced",
)


async def votes(
    client: LLMClient,
    scenario: Scenario,
    agent: AgentPersona,
    hand: list[str],
    cfg: RunConfig,
    samples: int,
    order: str = "balanced",
) -> list[dict[str, str]]:
    del order
    spec = get_paradigm(cfg.paradigm)
    k = len(scenario.candidates)

    async def one(seed: int) -> dict[str, str]:
        # one seed per sample so memo shuffle + run nonce vary as they do in real runs
        rot = rotate_candidates(scenario, seed % k)
        cell_cfg = cfg.model_copy(update={"seed": seed, "candidate_order": "fixed"})
        system = prompts.system_prompt(rot, cell_cfg, agent, hand, spec)
        user = prompts.alone_vote_message(rot, cell_cfg, agent)
        resp = await client.complete(
            LLMRequest(system=system, user=user, model=MODEL, max_tokens=200)
        )
        raw = validate.parse_json_object(resp.text) or {}
        v = raw.get("vote")
        vote = v if isinstance(v, str) and v in {c.id for c in rot.candidates} else truth.UNDECIDED
        reason = raw.get("reason")
        return {
            "first_listed": rot.candidates[0].id,
            "vote": vote,
            "reason": reason if isinstance(reason, str) else "",
        }

    return list(await asyncio.gather(*(one(i) for i in range(samples))))


async def gate(
    client: LLMClient,
    scenario: Scenario,
    style: PromptStyle,
    samples: int,
    fact_style: str,
    order: str = "balanced",
) -> dict[str, Any]:
    del order
    cfg = RunConfig(prompt_style=style, fact_style=fact_style, seed=0, candidate_order="fixed")  # type: ignore[arg-type]
    correct = designed_correct(scenario)
    shared_v = truth.shared_only_verdict(scenario)
    cells = [("pooled", POOLED, sorted(truth.pooled_fact_ids(scenario)))]
    cells.extend((a.id, a, list(scenario.distribution[a.id])) for a in scenario.agents)
    ballots = await asyncio.gather(
        *(votes(client, scenario, agent, hand, cfg, samples) for _, agent, hand in cells)
    )

    candidate_ids = {c.id for c in scenario.candidates}
    result_cells: dict[str, dict[str, Any]] = {}
    for (cell_id, _, _), cell_ballots in zip(cells, ballots):
        counts = Counter(ballot["vote"] for ballot in cell_ballots)
        by_first_listed: dict[str, Counter[str]] = {}
        for ballot in cell_ballots:
            by_first_listed.setdefault(ballot["first_listed"], Counter())[ballot["vote"]] += 1
        reasons = [ballot["reason"][:200] for ballot in cell_ballots[:2]]
        shared_k = sum(ballot["vote"] == shared_v for ballot in cell_ballots)
        shared_rate, shared_lo, shared_hi = wilson(shared_k, len(cell_ballots))
        if correct is None:
            rate: float | None = None
            ci: list[float] | None = None
        else:
            if cell_id == "pooled":
                interest_k = sum(ballot["vote"] == correct for ballot in cell_ballots)
            else:
                interest_k = sum(
                    ballot["vote"] in candidate_ids and ballot["vote"] != correct
                    for ballot in cell_ballots
                )
            rate, ci_lo, ci_hi = wilson(interest_k, len(cell_ballots))
            ci = [ci_lo, ci_hi]
        result_cells[cell_id] = {
            "n": len(cell_ballots),
            "counts": dict(counts),
            "by_first_listed": {key: dict(value) for key, value in by_first_listed.items()},
            "rate": rate,
            "ci": ci,
            "shared_rate": shared_rate,
            "shared_ci": [shared_lo, shared_hi],
            "reasons": reasons,
            "ballots": cell_ballots,
        }

    pooled_cell = result_cells["pooled"]
    pooled_right = pooled_cell["rate"]
    alone_wrong = {a.id: result_cells[a.id]["rate"] for a in scenario.agents}
    shared_rates = {cell_id: cell["shared_rate"] for cell_id, cell in result_cells.items()}
    return {
        "scenario": scenario.id,
        "prompt": style,
        "correct": correct,
        "shared_verdict": shared_v,
        "samples": samples,
        "cells": result_cells,
        "pooled": dict(pooled_cell["counts"]),
        "pooled_right": pooled_right,
        "alone": {a.id: dict(result_cells[a.id]["counts"]) for a in scenario.agents},
        "alone_wrong": alone_wrong,
        "shared_rates": shared_rates,
        "pass": (
            correct is not None
            and pooled_right is not None
            and pooled_right >= 0.8
            and all(v is not None and v >= 0.8 for v in alone_wrong.values())
        ),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?")
    parser.add_argument("--prompt", nargs="+", default=["naive", "default"])
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--fact-style", default="memo")
    parser.add_argument("--order", help="accepted for compatibility; ignored")
    parser.add_argument("--all", action="store_true", help="run every sample scenario")
    parser.add_argument("--force", action="store_true", help="rerun existing output files")
    parser.add_argument("--out", default="scripts/probe/out/gate")
    args = parser.parse_args()
    if args.all and args.scenario:
        parser.error("pass either a scenario or --all, not both")
    if not args.all and not args.scenario:
        parser.error("a scenario or --all is required")
    client = CountingClient(AnthropicClient())
    if args.all:
        from app.samples import SAMPLE_SCENARIOS

        scenarios = SAMPLE_SCENARIOS
    else:
        scenarios = [load_scenario_arg(args.scenario)]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        samples = samples_for(len(scenario.candidates), args.samples)
        for style in args.prompt:
            path = out_dir / f"{scenario.id}_{style}.json"
            if path.exists() and not args.force:
                print(f"{scenario.id} [{style}] skipped (exists) n={samples}")
                continue
            res = await gate(client, scenario, style, samples, args.fact_style)
            path.write_text(json.dumps(res, indent=1))

            def fmt(value: float | None) -> str:
                return "NA" if value is None else f"{value:.2f}"

            print(
                f"{scenario.id} [{style}] n={samples} correct={res['correct']} "
                f"pooled_right={fmt(res['pooled_right'])} alone_wrong="
                + " ".join(f"{a}={fmt(v)}" for a, v in res["alone_wrong"].items())
                + f" -> {'PASS' if res['pass'] else 'FAIL'} "
                f"~${cost_usd(client.input_tokens, client.output_tokens):.2f}"
            )
    print(f"total ~${cost_usd(client.input_tokens, client.output_tokens):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

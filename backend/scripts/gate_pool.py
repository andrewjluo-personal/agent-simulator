"""Hidden-profile gate for a scenario, per prompt style.

Gate (per prompt): the pooled single reviewer (all items) picks the designed-correct
candidate >= 80% of samples AND every agent alone picks the other candidate >= 80%.

Usage:
  .venv/bin/python scripts/gate_pool.py hiring-panel-flat [--prompt naive default]
      [--samples 10] [--fact-style memo]
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

from probe_lib import cost_usd, load_scenario_arg, order_for_sample

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
) -> Counter[str]:
    spec = get_paradigm(cfg.paradigm)
    ids = {c.id for c in scenario.candidates}

    async def one(seed: int) -> tuple[str, str, str]:
        # one seed per sample so memo shuffle + run nonce vary as they do in real runs
        shown = order_for_sample(order, seed % samples)
        cell_cfg = cfg.model_copy(update={"seed": seed, "candidate_order": shown})
        system = prompts.system_prompt(scenario, cell_cfg, agent, hand, spec)
        user = prompts.alone_vote_message(scenario, cell_cfg, agent)
        resp = await client.complete(
            LLMRequest(system=system, user=user, model=MODEL, max_tokens=200)
        )
        raw = validate.parse_json_object(resp.text) or {}
        v = raw.get("vote")
        reason = raw.get("reason")
        return (
            v if isinstance(v, str) and v in ids else truth.UNDECIDED,
            reason if isinstance(reason, str) else "",
            prompts.ordered_candidates(scenario, cell_cfg, agent)[0].id,
        )

    results = await asyncio.gather(*(one(i) for i in range(samples)))
    REASONS[agent.id] = [
        {"seed": i, "first": first, "vote": v, "reason": r}
        for i, (v, r, first) in enumerate(results)
    ]
    return Counter(v for v, _, _ in results)


REASONS: dict[str, list[dict[str, Any]]] = {}


async def gate(
    client: LLMClient,
    scenario: Scenario,
    style: PromptStyle,
    samples: int,
    fact_style: str,
    order: str = "balanced",
) -> dict[str, Any]:
    REASONS.clear()
    cfg = RunConfig(prompt_style=style, fact_style=fact_style, seed=0, candidate_order="fixed")  # type: ignore[arg-type]
    correct = truth.verdict(scenario, truth.pooled_fact_ids(scenario))
    shared_v = truth.verdict(scenario, truth.shared_fact_ids(scenario))
    pooled = await votes(
        client,
        scenario,
        POOLED,
        sorted(truth.pooled_fact_ids(scenario)),
        cfg,
        samples,
        order,
    )
    alone = {
        a.id: await votes(
            client, scenario, a, list(scenario.distribution[a.id]), cfg, samples, order
        )
        for a in scenario.agents
    }
    pooled_right = pooled[correct] / samples
    alone_wrong = {a: c[shared_v] / samples for a, c in alone.items()}
    by_order = {
        a: {
            "first_" + c.id: sum(r["vote"] == shared_v for r in REASONS[a] if r["first"] == c.id)
            for c in scenario.candidates
        }
        for a in alone
    }
    return {
        "scenario": scenario.id,
        "prompt": style,
        "order": order,
        "correct": correct,
        "shared_verdict": shared_v,
        "pooled": dict(pooled),
        "pooled_right": pooled_right,
        "alone": {a: dict(c) for a, c in alone.items()},
        "alone_wrong": alone_wrong,
        "alone_wrong_by_order": by_order,
        "reasons": dict(REASONS),
        "pass": pooled_right >= 0.8 and all(v >= 0.8 for v in alone_wrong.values()),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("--prompt", nargs="+", default=["naive", "default"])
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--fact-style", default="memo")
    parser.add_argument(
        "--order",
        choices=["balanced", "random", "fixed"],
        default="balanced",
        help="candidate order; 'balanced' alternates per sample (--samples must be even)",
    )
    parser.add_argument("--out", default="scripts/probe/out/gate")
    args = parser.parse_args()
    if args.order == "balanced" and args.samples % 2:
        parser.error("--samples must be even for balanced order")
    client = CountingClient(AnthropicClient())
    scenario = load_scenario_arg(args.scenario)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for style in args.prompt:
        res = await gate(client, scenario, style, args.samples, args.fact_style, args.order)
        (out_dir / f"{scenario.id}_{style}.json").write_text(json.dumps(res, indent=1))
        print(
            f"{scenario.id} [{style}] correct={res['correct']} pooled={res['pooled']} "
            f"pooled_right={res['pooled_right']:.2f} alone_wrong="
            + " ".join(
                f"{a}={v:.1f}({'/'.join(str(n) for n in res['alone_wrong_by_order'][a].values())})"
                for a, v in res["alone_wrong"].items()
            )
            + f" -> {'PASS' if res['pass'] else 'FAIL'}"
        )
    print(f"~${cost_usd(client.input_tokens, client.output_tokens):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

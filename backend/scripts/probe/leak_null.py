"""Leak hunt on a perceived-balanced pool: where does the residual candidate prior live?

Conditions (naive prompt, pooled reviewer unless noted, N samples each):
  blurb_only     empty hand -> brief + candidate blurbs only
  items_swapped  facts re-attributed to the other candidate (probe_lib.mirror_scenario);
                 names/blurbs unchanged -> tests item-type/content leak
  full_mirror    items swapped AND blurbs swapped -> tests name/gender leak
  alone_swapped  each agent alone on items_swapped

Usage: .venv/bin/python scripts/probe/leak_null.py scripts/probe/pools/hiring-panel-null.json --samples 10
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from probe_lib import load_scenario_arg, mirror_scenario

from app import prompts, validate
from app.llm import AnthropicClient, LLMRequest
from app.models import AgentPersona, RunConfig, Scenario
from app.paradigms import get_paradigm
from app.validator import REVIEWER

MODEL = "claude-haiku-4-5"


def swap_blurbs(s: Scenario) -> Scenario:
    a, b = s.candidates
    cands = [a.model_copy(update={"blurb": b.blurb}), b.model_copy(update={"blurb": a.blurb})]
    return s.model_copy(update={"id": s.id + "-blurbswap", "candidates": cands})


async def votes(
    client: AnthropicClient, s: Scenario, hand: list[str], agent: AgentPersona, n: int
) -> Counter[str]:
    cfg = RunConfig(scenario_id=s.id, model=MODEL, prompt_style="naive")
    system = prompts.system_prompt(s, cfg, agent, hand, get_paradigm("free_discussion"))
    user = prompts.alone_vote_message(s)
    ids = {c.id for c in s.candidates}

    async def one() -> str:
        r = await client.complete(LLMRequest(system=system, user=user, model=MODEL, max_tokens=400))
        return validate.validate_vote(validate.parse_json_object(r.text), ids)[0]

    return Counter(await asyncio.gather(*(one() for _ in range(n))))


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("scenario")
    p.add_argument("--samples", type=int, default=10)
    args = p.parse_args()
    base = load_scenario_arg(args.scenario)
    client = AnthropicClient()
    n = args.samples
    all_ids = [f.id for f in base.facts]
    swapped = mirror_scenario(base)
    full = swap_blurbs(swapped)
    print("blurb_only      ", dict(await votes(client, base, [], REVIEWER, n)))
    print("pooled_base     ", dict(await votes(client, base, all_ids, REVIEWER, n)))
    print("items_swapped   ", dict(await votes(client, swapped, all_ids, REVIEWER, n)))
    print("full_mirror     ", dict(await votes(client, full, all_ids, REVIEWER, n)))
    for ag in swapped.agents:
        c = await votes(client, swapped, swapped.distribution[ag.id], ag, max(2, n // 5))
        print(f"alone_swapped {ag.id:7}", dict(c))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Leak hunt on a perceived-balanced pool: where does the residual candidate prior live?

Every condition is a private ballot (`prompts.alone_vote_message`) under the naive prompt,
one seed per sample (memo shuffle + run nonce vary as in real runs). Pooled ballots use the
POOLED reviewer persona from gate_pool.py.

Conditions:
  blurb_only     empty hand -> brief + candidate blurbs + persona only
  pooled_base    pooled reviewer, all items, unchanged
  items_swapped  facts re-attributed to the other candidate (probe_lib.mirror_scenario);
                 names/blurbs unchanged -> item content/type leak
  full_mirror    items swapped AND blurbs swapped -> name/gender leak
  alone_swapped  each agent alone on items_swapped
  persona_swap   each agent alone on its real hand, wearing every other agent's persona
                 and a neutral "panelist" persona -> do the persona lines carry the prior?
  cand_order     candidates listed Sally-first (system prompt + vote option string), alone + pooled
  neutral_names  John/Sally -> "Candidate A"/"Candidate B", pronouns neutralised everywhere
  order_split    diagnostic: reverse exactly one surface (candidate list / memo
                 paragraphs / ballot options) while the rest stay in fixed order
  alone_base     each agent alone on its real hand (reference)

Usage:
  .venv/bin/python scripts/probe/leak_null.py hiring-panel-null --samples 10 \
      --cond blurb_only pooled_base items_swapped full_mirror alone_swapped
Results (counts + every ballot reason) are appended to --out as JSON per condition.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from gate_pool import POOLED, CountingClient
from probe_lib import cost_usd, load_scenario_arg, mirror_scenario, order_for_sample

from app import prompts, truth, validate
from app.llm import AnthropicClient, LLMRequest
from app.models import AgentPersona, Candidate, RunConfig, Scenario
from app.paradigms import get_paradigm

MODEL = "claude-haiku-4-5"

NEUTRAL_PERSONA = AgentPersona(id="neutral", name="Panelist", role="panelist", style="neutral")


def swap_blurbs(s: Scenario) -> Scenario:
    a, b = s.candidates
    cands = [a.model_copy(update={"blurb": b.blurb}), b.model_copy(update={"blurb": a.blurb})]
    return s.model_copy(update={"id": s.id + "-blurbswap", "candidates": cands})


def reverse_candidates(s: Scenario) -> Scenario:
    return s.model_copy(
        update={"id": s.id + "-revorder", "candidates": list(reversed(s.candidates))}
    )


@contextlib.contextmanager
def _reversed_surface(which: str):
    """Diagnostic: reverse exactly one prompt surface by routing its builder through
    a reversed-candidates scenario view. Restores everything on exit."""
    orig_lines = prompts._candidate_lines
    orig_memo = prompts._memo_lines
    orig_msg = prompts.alone_vote_message
    if which == "list":

        def lines(s: Scenario, cfg=None, agent=None) -> str:
            return orig_lines(reverse_candidates(s), cfg, agent)

        prompts._candidate_lines = lines
    elif which == "memo":

        def memo(s: Scenario, cfg, agent, hand_fact_ids) -> str:
            return orig_memo(reverse_candidates(s), cfg, agent, hand_fact_ids)

        prompts._memo_lines = memo
    elif which == "options":

        def msg(s: Scenario, cfg=None, agent=None) -> str:
            return orig_msg(reverse_candidates(s), cfg, agent)

        prompts.alone_vote_message = msg
    try:
        yield
    finally:
        prompts._candidate_lines = orig_lines
        prompts._memo_lines = orig_memo
        prompts.alone_vote_message = orig_msg


_PRONOUN = [
    (re.compile(r"\bher as\b"), "them as"),
    (re.compile(r"\b(he|she)\b"), "they"),
    (re.compile(r"\b(He|She)\b"), "They"),
    (re.compile(r"\b(his|her)\b"), "their"),
    (re.compile(r"\b(His|Her)\b"), "Their"),
    (re.compile(r"\b(himself|herself)\b"), "themselves"),
]


def neutralise(text: str, names: dict[str, str]) -> str:
    for old, new in names.items():
        text = re.sub(rf"\b{old}\b", new, text)
    for pat, rep in _PRONOUN:
        text = pat.sub(rep, text)
    return text


def neutral_names(s: Scenario) -> Scenario:
    """Candidates become 'Candidate A'/'Candidate B' (ids cand_a/cand_b); pronouns -> they."""
    letters = ["A", "B", "C"]
    id_map = {c.id: f"cand_{letters[i].lower()}" for i, c in enumerate(s.candidates)}
    name_map = {c.name: f"Candidate {letters[i]}" for i, c in enumerate(s.candidates)}
    cands = [
        Candidate(
            id=id_map[c.id],
            name=name_map[c.name],
            blurb=neutralise(c.blurb, name_map),
        )
        for c in s.candidates
    ]
    facts = [
        f.model_copy(
            update={
                "candidate_id": id_map[f.candidate_id],
                "text": neutralise(f.text, name_map),
                "memo_text": neutralise(f.memo_text, name_map) if f.memo_text else None,
            }
        )
        for f in s.facts
    ]
    return s.model_copy(
        update={
            "id": s.id + "-neutral",
            "brief": neutralise(s.brief, name_map),
            "candidates": cands,
            "facts": facts,
        }
    )


async def votes(
    client: CountingClient,
    s: Scenario,
    hand: list[str],
    agent: AgentPersona,
    n: int,
    order_mode: str = "balanced",
) -> dict[str, Any]:
    spec = get_paradigm("free_discussion")
    ids = {c.id for c in s.candidates}

    async def one(seed: int) -> tuple[str, str]:
        cfg = RunConfig(
            scenario_id=s.id,
            model=MODEL,
            prompt_style="naive",
            seed=seed,
            candidate_order=order_for_sample(order_mode, seed),
        )
        system = prompts.system_prompt(s, cfg, agent, hand, spec)
        user = prompts.alone_vote_message(s, cfg, agent)
        r = await client.complete(LLMRequest(system=system, user=user, model=MODEL, max_tokens=300))
        raw = validate.parse_json_object(r.text) or {}
        v = raw.get("vote")
        vote = v if isinstance(v, str) and v in ids else truth.UNDECIDED
        return vote, str(raw.get("reason", ""))

    rows = await asyncio.gather(*(one(i) for i in range(n)))
    return {"counts": dict(Counter(v for v, _ in rows)), "reasons": [f"{v}: {r}" for v, r in rows]}


def fmt(counts: dict[str, int]) -> str:
    return " ".join(f"{k}={v}" for k, v in sorted(counts.items()))


async def run_condition(
    client: CountingClient,
    cond: str,
    base: Scenario,
    n: int,
    out: dict[str, Any],
    order: str = "balanced",
) -> None:
    all_ids = [f.id for f in base.facts]
    swapped = mirror_scenario(base)

    async def rec(
        label: str,
        s: Scenario,
        hand: list[str],
        agent: AgentPersona,
        k: int,
        cell_order: str | None = None,
    ) -> None:
        res = await votes(client, s, hand, agent, k, cell_order or order)
        out[label] = res
        print(f"{label:34} n={k:<3} {fmt(res['counts'])}", flush=True)

    if cond == "blurb_only":
        await rec("blurb_only pooled", base, [], POOLED, n)
        for ag in base.agents:
            await rec(f"blurb_only alone {ag.id}", base, [], ag, max(2, n // 2))
    elif cond == "pooled_base":
        await rec("pooled_base", base, all_ids, POOLED, n)
    elif cond == "alone_base":
        for ag in base.agents:
            await rec(f"alone_base {ag.id}", base, base.distribution[ag.id], ag, n)
    elif cond == "items_swapped":
        await rec("items_swapped pooled", swapped, all_ids, POOLED, n)
    elif cond == "full_mirror":
        full = swap_blurbs(swapped)
        await rec("full_mirror pooled", full, all_ids, POOLED, n)
    elif cond == "alone_swapped":
        for ag in swapped.agents:
            await rec(f"alone_swapped {ag.id}", swapped, swapped.distribution[ag.id], ag, n)
    elif cond == "persona_swap":
        k = max(2, n // 2)
        personas = list(base.agents) + [NEUTRAL_PERSONA]
        for ag in base.agents:
            for p in personas:
                if p.id == ag.id:
                    continue
                await rec(f"persona_swap {ag.id}<-{p.id}", base, base.distribution[ag.id], p, k)
    elif cond == "cand_order":
        rev = reverse_candidates(base)
        await rec("cand_order pooled", rev, all_ids, POOLED, n)
        for ag in rev.agents:
            await rec(f"cand_order alone {ag.id}", rev, rev.distribution[ag.id], ag, n)
    elif cond == "order_split":
        # sanity: the swap machinery is transparent when nothing is reversed
        spec = get_paradigm("free_discussion")
        cfg_fix = RunConfig(
            scenario_id=base.id,
            model=MODEL,
            prompt_style="naive",
            seed=0,
            candidate_order="fixed",
        )
        ag = base.agents[0]
        expected_sys = prompts.system_prompt(base, cfg_fix, ag, base.distribution[ag.id], spec)
        expected_msg = prompts.alone_vote_message(base, cfg_fix, ag)
        with _reversed_surface("none"):
            assert (
                prompts.system_prompt(base, cfg_fix, ag, base.distribution[ag.id], spec)
                == expected_sys
            )
            assert prompts.alone_vote_message(base, cfg_fix, ag) == expected_msg
        for variant in ("list", "memo", "options"):
            with _reversed_surface(variant):
                await rec(f"order_split {variant} pooled", base, all_ids, POOLED, n, "fixed")
                for ag in base.agents:
                    await rec(
                        f"order_split {variant} alone {ag.id}",
                        base,
                        base.distribution[ag.id],
                        ag,
                        n,
                        "fixed",
                    )
    elif cond == "neutral_names":
        neu = neutral_names(base)
        await rec("neutral_names blurb_only", neu, [], POOLED, n)
        await rec("neutral_names pooled", neu, all_ids, POOLED, n)
        for ag in neu.agents:
            await rec(f"neutral_names alone {ag.id}", neu, neu.distribution[ag.id], ag, n)
    else:
        raise SystemExit(f"unknown condition {cond!r}")


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("scenario")
    p.add_argument("--samples", type=int, default=10)
    p.add_argument("--cond", nargs="+", default=["blurb_only", "pooled_base"])
    p.add_argument(
        "--order",
        choices=["balanced", "random", "fixed"],
        default="balanced",
        help="candidate order; 'balanced' alternates per sample (--samples must be even)",
    )
    p.add_argument("--out", default="scripts/probe/out/s3/leak_null.json")
    args = p.parse_args()
    if args.order == "balanced" and args.samples % 2:
        p.error("--samples must be even for balanced order")
    base = load_scenario_arg(args.scenario)
    client = CountingClient(AnthropicClient())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out: dict[str, Any] = json.loads(out_path.read_text()) if out_path.exists() else {}
    for cond in args.cond:
        await run_condition(client, cond, base, args.samples, out, args.order)
        out_path.write_text(json.dumps(out, indent=1))
    print(f"~${cost_usd(client.input_tokens, client.output_tokens):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Free-discussion ablation probe: sweep prompt_style x transcript_visibility cells
of the real orchestrator and record per-run JSONL.

Usage:
  .venv/bin/python scripts/probe_free_discussion.py \
      --scenario hiring-panel-flat --cell fd-naive-hidden \
      --prompt-style naive --transcript-visibility none \
      --runs 20 --out probes.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("LOG_LEVEL", "WARNING")

_BACKEND = str(Path(__file__).parent.parent)
sys.path.insert(0, _BACKEND)
sys.path.insert(0, str(Path(__file__).parent))

from validate_scenario import CountingClient

from app import orchestrator, prompts, scenario_gen, truth, validate
from app.llm import AnthropicClient, LLMClient, LLMRequest
from app.models import RunConfig, Scenario, Vote
from app.paradigms import get_paradigm
from app.probe_stats import echo_by_round
from app.samples import SAMPLES_BY_ID
from app.store import MemoryStore
from app.validator import REVIEWER

MIRROR_SWAP = {
    "John": "Sally",
    "Sally": "John",
    "John's": "Sally's",
    "Sally's": "John's",
    "his": "her",
    "her": "his",
    "he": "she",
    "she": "he",
    "him": "her",
    "He": "She",
    "She": "He",
}
_MIRROR_PAT = re.compile(r"\b(" + "|".join(re.escape(k) for k in MIRROR_SWAP) + r")\b")


def mirror_scenario(base: Scenario) -> Scenario:
    """John<->Sally name/pronoun swap (copied from scripts/probe/mirror_pool.py)."""

    def swap(text: str) -> str:
        return _MIRROR_PAT.sub(lambda m: MIRROR_SWAP[m.group(1)], text)

    mirror = base.model_copy(deep=True)
    mirror.id = f"{base.id}-mirror"
    for f in mirror.facts:
        f.candidate_id = "sally" if f.candidate_id == "john" else "john"
        f.text = swap(f.text)
        if f.memo_text:
            f.memo_text = swap(f.memo_text)
    return mirror


def load_probe_scenario(scenario_id: str) -> Scenario:
    if scenario_id.endswith("-mirror"):
        base_id = scenario_id[: -len("-mirror")]
        base = SAMPLES_BY_ID.get(base_id)
        if base is None:
            raise SystemExit(f"unknown scenario {base_id!r} for mirroring")
        return mirror_scenario(base)
    scenario = SAMPLES_BY_ID.get(scenario_id)
    if scenario is None:
        raise SystemExit(f"unknown scenario {scenario_id!r}")
    return scenario


def _votes_dict(votes: list[Vote], round_idx: int) -> dict[str, str]:
    return {v.agent_id: v.choice for v in votes if v.round == round_idx}


async def one_run(
    client: LLMClient,
    scenario: Scenario,
    args: argparse.Namespace,
    seed: int,
    sem: asyncio.Semaphore,
    done: list[bool],
    out: Path,
) -> dict[str, Any]:
    store = MemoryStore()
    store.upsert_scenario(scenario)
    cfg = RunConfig(
        scenario_id=scenario.id,
        paradigm="free_discussion",
        rounds=args.rounds,
        seed=seed,
        model=args.model,
        prompt_style=args.prompt_style,
        transcript_visibility=args.transcript_visibility,
    )
    run = orchestrator.new_run(store, cfg, provider=client.provider)
    store.create_run(run)
    async with sem:
        final = await orchestrator.run_to_completion(store, client, run.id)
    m = final.metrics
    shared = truth.shared_fact_ids(scenario)
    cited = {c for t in final.turns for c in t.cited}
    uniques_cited = sorted(cited - shared)
    spoken = truth.verdict(scenario, shared | cited)
    vote_rounds = sorted({v.round for v in final.votes if v.round >= 0})
    record: dict[str, Any] = {
        "kind": "run",
        "cell": args.cell,
        "scenario_id": scenario.id,
        "n_agents": len(scenario.agents),
        "rounds": cfg.rounds,
        "model": cfg.model,
        "prompt_style": cfg.prompt_style,
        "transcript_visibility": cfg.transcript_visibility,
        "seed": seed,
        "pre_votes": _votes_dict(final.votes, -1),
        "votes_by_round": [_votes_dict(final.votes, r) for r in vote_rounds],
        "final_tally": m.final_tally if m else {},
        "final_majority": m.majority_candidate_id if m else "undecided",
        "correct_candidate": m.correct_candidate_id if m else "undecided",
        "correct": bool(m and m.correct),
        "spoken_verdict": spoken,
        "final_differs_from_spoken": (m.majority_candidate_id if m else "undecided") != spoken,
        "uniques_cited": uniques_cited,
        "n_uniques_cited": len(uniques_cited),
        "n_uniques_total": len(truth.unique_fact_ids(scenario)),
        "decisive_surfaced_count": m.decisive_surfaced_count if m else 0,
        "decisive_total": m.decisive_total if m else 0,
        "echo_by_round": echo_by_round(final.turns, cfg.rounds),
        "tokens": {
            "input": m.tokens_total.input if m else 0,
            "output": m.tokens_total.output if m else 0,
        },
        "turns": [
            {
                "round": t.round,
                "agent_id": t.agent_id,
                "sentences": t.sentences,
                "cited": t.cited,
                "lean": t.lean,
            }
            for t in final.turns
        ],
        "votes": [
            {
                "round": v.round,
                "agent_id": v.agent_id,
                "choice": v.choice,
                "reason": v.reason,
            }
            for v in final.votes
        ],
    }
    done.append(bool(record["correct"]))
    with out.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    print(
        f"seed {seed}: correct={record['correct']} majority={record['final_majority']} "
        f"spoken={spoken} uniques={record['n_uniques_cited']}/{record['n_uniques_total']} "
        f"decisive={record['decisive_surfaced_count']}/{record['decisive_total']} "
        f"running={sum(done)}/{len(done)}",
        flush=True,
    )
    return record


async def _one_vote(
    client: LLMClient, system: str, user: str, model: str, candidate_ids: set[str]
) -> str:
    resp = await client.complete(LLMRequest(system=system, user=user, model=model, max_tokens=400))
    choice, _conf, _reason = validate.validate_vote(
        validate.parse_json_object(resp.text), candidate_ids
    )
    return choice


async def pooled_baseline(
    client: LLMClient, scenario: Scenario, args: argparse.Namespace
) -> dict[str, Any]:
    cfg = RunConfig(
        scenario_id=scenario.id,
        model=args.model,
        prompt_style=args.prompt_style,
        transcript_visibility=args.transcript_visibility,
    )
    spec = get_paradigm("free_discussion")
    all_fact_ids = [f.id for f in scenario.facts]
    system = prompts.system_prompt(scenario, cfg, REVIEWER, all_fact_ids, spec)
    user = prompts.alone_vote_message(scenario)
    candidate_ids = {c.id for c in scenario.candidates}
    votes = [
        await _one_vote(client, system, user, args.model, candidate_ids)
        for _ in range(args.pooled_baseline)
    ]
    right = truth.pooled_verdict(scenario)
    right_rate = sum(1 for v in votes if v == right) / len(votes) if votes else 0.0
    return {
        "kind": "pooled_baseline",
        "cell": args.cell,
        "scenario_id": scenario.id,
        "model": args.model,
        "prompt_style": cfg.prompt_style,
        "votes": votes,
        "right_rate": right_rate,
    }


async def alone_baseline(
    client: LLMClient, scenario: Scenario, args: argparse.Namespace
) -> dict[str, Any]:
    cfg = RunConfig(
        scenario_id=scenario.id,
        model=args.model,
        prompt_style=args.prompt_style,
        transcript_visibility=args.transcript_visibility,
    )
    spec = get_paradigm("free_discussion")
    candidate_ids = {c.id for c in scenario.candidates}
    user = prompts.alone_vote_message(scenario)
    votes: dict[str, str] = {}
    for agent in scenario.agents:
        system = prompts.system_prompt(scenario, cfg, agent, scenario.distribution[agent.id], spec)
        votes[agent.id] = await _one_vote(client, system, user, args.model, candidate_ids)
    wrong = truth.shared_only_verdict(scenario)
    wrong_rate = sum(1 for v in votes.values() if v == wrong) / len(votes) if votes else 0.0
    return {
        "kind": "alone_baseline",
        "cell": args.cell,
        "scenario_id": scenario.id,
        "model": args.model,
        "prompt_style": cfg.prompt_style,
        "votes": votes,
        "wrong_rate": wrong_rate,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="hiring-panel-flat")
    parser.add_argument("--n-agents", type=int, default=0, help="0 = scenario's own panel")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument(
        "--prompt-style",
        choices=["default", "naive", "naive_no_repeat", "naive_consensus"],
        default="default",
    )
    parser.add_argument(
        "--transcript-visibility",
        choices=["full", "last_round", "none"],
        default="full",
    )
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--cell", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pooled-baseline", type=int, default=0)
    parser.add_argument("--alone-baseline", action="store_true")
    args = parser.parse_args()

    scenario = load_probe_scenario(args.scenario)
    if args.n_agents and args.n_agents != len(scenario.agents):
        scenario = scenario_gen.redistribute(scenario, args.n_agents, seed=0)
    if not args.cell:
        args.cell = f"{scenario.id}/{args.prompt_style}/{args.transcript_visibility}"

    client = CountingClient(AnthropicClient())
    sem = asyncio.Semaphore(args.concurrency)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    done: list[bool] = []
    lines: list[dict[str, Any]] = list(
        await asyncio.gather(
            *(
                one_run(client, scenario, args, seed, sem, done, out)
                for seed in range(args.seed_start, args.seed_start + args.runs)
            )
        )
    )
    if args.pooled_baseline:
        line = await pooled_baseline(client, scenario, args)
        with out.open("a") as fh:  # noqa: ASYNC230 - sync append
            fh.write(json.dumps(line) + "\n")
        lines.append(line)
    if args.alone_baseline:
        line = await alone_baseline(client, scenario, args)
        with out.open("a") as fh:  # noqa: ASYNC230 - sync append
            fh.write(json.dumps(line) + "\n")
        lines.append(line)

    n_correct = sum(done)
    print(
        f"cell {args.cell}: {n_correct}/{args.runs} correct "
        f"({n_correct / args.runs:.2f}); tokens {client.input_tokens} in / "
        f"{client.output_tokens} out"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

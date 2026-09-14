"""Free-discussion probe: N seeded runs of one scenario, one JSONL row per run plus a
transcript dump, with optional planted round-1 turns (P1) and randomised order (P2).

Usage:
  .venv/bin/python scripts/probe_free_discussion.py --scenario hiring-panel-flat-v2
      --prompt naive --runs 8 --seed-start 0 --dump-dir scripts/probe/out/p1/control
      [--plant FILE.json] [--order clockwise|random] [--rounds 3] [--concurrency 4]

  # P1 presets (plant text + dump dir chosen for you):
  .venv/bin/python scripts/probe_free_discussion.py --cell a|b|c|cprime|d [--runs 8]

Plant file: {"round": 1, "speaker": "<agent_id>", "text": "..."} (round is 1-based).
Summarise a directory of cells with scripts/summarize_probe.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from gate_pool import CountingClient
from probe_lib import cost_usd, echo_by_round, load_scenario_arg, spoken_verdict, wilson

from app import orchestrator, truth
from app.llm import AnthropicClient
from app.models import PromptStyle, RunConfig, RunState, Scenario, TurnOrder
from app.orchestrator import Plant
from app.store import MemoryStore

MODEL = "claude-haiku-4-5"

# P1 cells on hiring-panel-flat-v2. Speaker "dana" is moved to the front of round 1.
# (a)/(b) are length-matched evaluative frames on SHARED items only; (c)/(c') are
# length-matched flat statements of one unique item held by dana (F1 Sally, G1 John).
P1_CELLS: dict[str, dict[str, Any]] = {
    "a": {
        "desc": "pro-John framing of shared items",
        "plant": (
            "Honestly the notes make this easy: John has eight years of Go, leads a team of six "
            "and knows the payments domain, while Sally has no Go, paused and restarted answers, "
            "and submitted late. John is clearly the stronger candidate here."
        ),
    },
    "b": {
        "desc": "pro-Sally framing of shared items",
        "plant": (
            "Honestly the notes make this easy: Sally asked about on-call and incidents, thinks "
            "before answering and maintains a Postgres tool, while John only asked about title "
            "and pay and omitted setup docs. Sally is clearly the stronger candidate here."
        ),
    },
    "c": {
        "desc": "one Sally unique (F1), flat",
        "plant": None,  # filled from the fact's memo text at runtime
        "fact": "F1",
    },
    "cprime": {
        "desc": "one John unique (G1), flat",
        "plant": None,
        "fact": "G1",
    },
    "d": {"desc": "control (no plant)", "plant": None},
}
P1_SCENARIO = "hiring-panel-flat-v2"
P1_SPEAKER = "dana"


def load_plants(path: str | None) -> tuple[Plant, ...]:
    if not path:
        return ()
    data = json.loads(Path(path).read_text())
    items = data if isinstance(data, list) else [data]
    return tuple(
        Plant(round_idx=int(p["round"]) - 1, speaker=p["speaker"], text=p["text"]) for p in items
    )


def cell_plants(scenario: Scenario, cell: str) -> tuple[Plant, ...]:
    spec = P1_CELLS[cell]
    text = spec["plant"]
    if spec.get("fact"):
        f = scenario.fact(spec["fact"])
        cand = next(c for c in scenario.candidates if c.id == f.candidate_id)
        text = f"One thing from my notes on {cand.name}: {f.memo_text or f.text}"
    if text is None:
        return ()
    return (Plant(round_idx=0, speaker=P1_SPEAKER, text=text),)


def run_row(final: RunState, scenario: Scenario, plants: tuple[Plant, ...]) -> dict[str, Any]:
    pre = {v.agent_id: v.choice for v in final.votes if v.round == -1}
    rounds = sorted({v.round for v in final.votes if v.round >= 0})
    votes_by_round = {
        str(r): {v.agent_id: v.choice for v in final.votes if v.round == r} for r in rounds
    }
    uniques = truth.unique_fact_ids(scenario)
    decisive = truth.decisive_fact_ids(scenario)
    cited_all = {f for t in final.turns for f in t.cited}
    uniques_by_round = {
        str(r): sorted({f for t in final.turns if t.round == r for f in t.cited} & uniques)
        for r in range(final.config.rounds)
    }
    r1 = [t for t in final.turns if t.round == 0]
    first = r1[0].agent_id if r1 else None
    planted_ids = {p.speaker for p in plants if p.round_idx == 0}
    first_free = next((t.agent_id for t in r1 if t.agent_id not in planted_ids), None)
    m = final.metrics
    tin = sum(t.input_tokens or 0 for t in final.turns)
    tout = sum(t.output_tokens or 0 for t in final.turns)
    return {
        "run_id": final.id,
        "seed": final.config.seed,
        "scenario": scenario.id,
        "prompt_style": final.config.prompt_style,
        "turn_order": final.config.turn_order,
        "planted": [p.__dict__ for p in plants],
        "correct_candidate": truth.pooled_verdict(scenario),
        "pre_votes": pre,
        "votes_by_round": votes_by_round,
        "uniques_cited_by_round": uniques_by_round,
        "uniques_cited": sorted(cited_all & uniques),
        "decisive_cited": sorted(cited_all & decisive),
        "spoken_verdict": spoken_verdict(scenario, cited_all),
        "final_majority": m.majority_candidate_id if m else truth.UNDECIDED,
        "final_tally": m.final_tally if m else {},
        "first_speaker": {"agent_id": first, "pre_vote": pre.get(first or "")},
        "first_free_speaker": {"agent_id": first_free, "pre_vote": pre.get(first_free or "")},
        "echo_by_round": echo_by_round(
            [{"round": t.round, "text": " ".join(t.sentences)} for t in final.turns]
        ),
        "input_tokens": tin,
        "output_tokens": tout,
        "cost_usd": cost_usd(tin, tout),
    }


def write_transcript(path: Path, final: RunState) -> None:
    lines = []
    for v in final.votes:
        if v.round == -1:
            lines.append(f"pre-vote {v.agent_id}: {v.choice}")
    for t in final.turns:
        lines.append(f"R{t.round + 1} {t.agent_id}: {' '.join(t.sentences)}  [{','.join(t.cited)}]")
    for v in final.votes:
        if v.round >= 0:
            lines.append(f"vote r{v.round + 1} {v.agent_id}: {v.choice} -- {v.reason or ''}")
    path.write_text("\n".join(lines) + "\n")


async def one(
    client: CountingClient,
    scenario: Scenario,
    seed: int,
    prompt: PromptStyle,
    order: TurnOrder,
    rounds: int,
    plants: tuple[Plant, ...],
    sem: asyncio.Semaphore,
) -> RunState:
    store = MemoryStore()
    store.upsert_scenario(scenario)
    run = orchestrator.new_run(
        store,
        RunConfig(
            scenario_id=scenario.id,
            paradigm="free_discussion",
            seed=seed,
            fact_style="memo",
            rounds=rounds,
            turn_order=order,
            prompt_style=prompt,
            model=MODEL,
        ),
        provider="anthropic",
    )
    store.create_run(run)
    async with sem:
        return await orchestrator.run_to_completion(store, client, run.id, plants)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=P1_SCENARIO)
    ap.add_argument("--prompt", choices=["naive", "default"], default="naive")
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--dump-dir")
    ap.add_argument("--plant")
    ap.add_argument("--order", choices=["clockwise", "random"], default="random")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--cell", choices=sorted(P1_CELLS))
    args = ap.parse_args()

    scenario = load_scenario_arg(args.scenario)
    plants = load_plants(args.plant)
    if args.cell:
        plants = cell_plants(scenario, args.cell)
        args.dump_dir = args.dump_dir or f"scripts/probe/out/p1/{args.cell}"
    dump = Path(args.dump_dir or f"scripts/probe/out/fd/{scenario.id}")
    dump.mkdir(parents=True, exist_ok=True)

    client = CountingClient(AnthropicClient())
    sem = asyncio.Semaphore(args.concurrency)
    seeds = range(args.seed_start, args.seed_start + args.runs)
    finals = await asyncio.gather(
        *(
            one(client, scenario, s, args.prompt, args.order, args.rounds, plants, sem)
            for s in seeds
        )
    )
    rows = []
    with (dump / "runs.jsonl").open("a") as fh:
        for final in finals:
            row = run_row(final, scenario, plants)
            rows.append(row)
            fh.write(json.dumps(row) + "\n")
            write_transcript(dump / f"{args.prompt}_seed{final.config.seed}.txt", final)

    correct = truth.pooled_verdict(scenario)
    n = len(rows)
    k = sum(r["final_majority"] == correct for r in rows)
    dis = sum(r["final_majority"] != r["spoken_verdict"] for r in rows)
    _, lo, hi = wilson(k, n)
    print(f"{scenario.id} [{args.prompt}, {args.order}] cell={args.cell or '-'} n={n}")
    if plants:
        print(f"  plant ({P1_SPEAKER} first, r1): {plants[0].text}")
    print(f"  final {correct}: {k}/{n} = {k / n:.2f}  Wilson95 [{lo:.2f}, {hi:.2f}]")
    print(f"  P3 majority != spoken verdict: {dis}/{n}")
    print(
        f"  pre-vote {correct} mean: {sum(sum(v == correct for v in r['pre_votes'].values()) / 5 for r in rows) / n:.2f}"
    )
    print(f"  uniques cited/run: {sum(len(r['uniques_cited']) for r in rows) / n:.1f}")
    print(f"  seeds: {[r['seed'] for r in rows]} finals: {[r['final_majority'] for r in rows]}")
    print(f"  cost ≈ ${cost_usd(client.input_tokens, client.output_tokens):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

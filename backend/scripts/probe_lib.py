"""Shared, LLM-free helpers for the mechanism-probe scripts (probe_free_discussion,
summarize_probe, perceived_profile). Pure functions so they are unit-testable."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from app import truth
from app.models import CandidateOrder, Scenario

HAIKU_USD_PER_M_IN = 0.8
HAIKU_USD_PER_M_OUT = 4.0


def order_for_sample(order_mode: str, j: int) -> CandidateOrder:
    """Candidate order for sample index j; `balanced` alternates fixed/reversed."""
    if order_mode == "balanced":
        return "fixed" if j % 2 == 0 else "reversed"
    return order_mode  # type: ignore[return-value]


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * HAIKU_USD_PER_M_IN + output_tokens * HAIKU_USD_PER_M_OUT) / 1e6


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """(rate, lo, hi) Wilson score interval."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    toks = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def ngram_overlap(text: str, previous: Iterable[str], n: int = 4) -> float:
    """Fraction of `text`'s n-grams that appear in any of `previous`. 0.0 if `text`
    has fewer than n tokens."""
    own = _ngrams(text, n)
    if not own:
        return 0.0
    prev: set[tuple[str, ...]] = set()
    for p in previous:
        prev |= _ngrams(p, n)
    return len(own & prev) / len(own)


def echo_by_round(turns: Sequence[dict[str, Any]]) -> dict[int, float]:
    """Mean 4-gram overlap of each turn with the previous round's turns, per round.
    `turns` are dicts with keys round, text. Round 0 has no previous round -> omitted."""
    by_round: dict[int, list[str]] = {}
    for t in turns:
        by_round.setdefault(int(t["round"]), []).append(str(t["text"]))
    out: dict[int, float] = {}
    for r in sorted(by_round):
        if r - 1 not in by_round:
            continue
        vals = [ngram_overlap(txt, by_round[r - 1]) for txt in by_round[r]]
        out[r] = sum(vals) / len(vals) if vals else 0.0
    return out


_SWAP = {
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
_SWAP_PAT = re.compile(r"\b(" + "|".join(re.escape(k) for k in _SWAP) + r")\b")


def swap_names(s: str) -> str:
    return _SWAP_PAT.sub(lambda m: _SWAP[m.group(1)], s)


def mirror_scenario(scenario: Scenario, suffix: str = "-mirror") -> Scenario:
    """Swap every fact's candidate (two-candidate John/Sally scenarios only) so the
    designed-correct candidate flips while wording stays the same."""
    ids = [c.id for c in scenario.candidates]
    if len(ids) != 2:
        raise ValueError("mirror requires exactly two candidates")
    other = {ids[0]: ids[1], ids[1]: ids[0]}
    facts = []
    for f in scenario.facts:
        facts.append(
            f.model_copy(
                update={
                    "candidate_id": other[f.candidate_id],
                    "text": swap_names(f.text),
                    "memo_text": swap_names(f.memo_text) if f.memo_text else None,
                }
            )
        )
    return scenario.model_copy(update={"id": scenario.id + suffix, "facts": facts})


def load_scenario_arg(arg: str) -> Scenario:
    """`<sample id>`, `<sample id>:mirror`, or a path to a Scenario JSON file."""
    from app.samples import SAMPLES_BY_ID

    path = Path(arg)
    if path.suffix == ".json" and path.exists():
        return Scenario.model_validate(json.loads(path.read_text()))
    base, _, mod = arg.partition(":")
    scenario = SAMPLES_BY_ID[base]
    if mod == "mirror":
        return mirror_scenario(scenario)
    if mod:
        raise ValueError(f"unknown scenario modifier {mod!r}")
    return scenario


def spoken_verdict(scenario: Scenario, cited: Iterable[str]) -> str:
    """Arithmetic verdict of shared ∪ cited (what the room actually heard)."""
    return truth.verdict(scenario, truth.shared_fact_ids(scenario) | set(cited))


# --- run-record analysis (one JSONL row per run) -------------------------------


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def odds_ratio(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    """OR with Haldane-Anscombe 0.5 correction and 95% CI. Table:
    a = exposed & outcome, b = exposed & no outcome, c = unexposed & outcome,
    d = unexposed & no outcome."""
    a2, b2, c2, d2 = (x + 0.5 for x in (a, b, c, d))
    or_ = (a2 * d2) / (b2 * c2)
    se = math.sqrt(1 / a2 + 1 / b2 + 1 / c2 + 1 / d2)
    return or_, math.exp(math.log(or_) - 1.96 * se), math.exp(math.log(or_) + 1.96 * se)


def summarize_runs(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a cell. Expects the keys written by probe_free_discussion."""
    n = len(rows)
    if n == 0:
        return {"n": 0}
    correct = sum(1 for r in rows if r["final_majority"] == r["correct_candidate"])
    rate, lo, hi = wilson(correct, n)
    disagree = sum(1 for r in rows if r["final_majority"] != r["spoken_verdict"])
    uniques = [len(r["uniques_cited"]) for r in rows]
    decisive = [len(r["decisive_cited"]) for r in rows]

    # P2: first free (model-generated) speaker's pre-vote vs final majority.
    a = b = c = d = 0
    for r in rows:
        fs = r.get("first_free_speaker") or r.get("first_speaker")
        if not fs:
            continue
        pre = r["pre_votes"].get(fs["agent_id"])
        outcome = r["final_majority"] == r["correct_candidate"]
        if pre == r["correct_candidate"]:
            a += outcome
            b += not outcome
        else:
            c += outcome
            d += not outcome
    or_, or_lo, or_hi = odds_ratio(a, b, c, d)

    echo_rounds: dict[int, list[float]] = {}
    for r in rows:
        for k, v in (r.get("echo_by_round") or {}).items():
            echo_rounds.setdefault(int(k), []).append(float(v))
    echo = {k: sum(v) / len(v) for k, v in sorted(echo_rounds.items())}

    pre_correct = [
        sum(1 for v in r["pre_votes"].values() if v == r["correct_candidate"])
        / max(1, len(r["pre_votes"]))
        for r in rows
    ]
    tokens_in = sum(int(r.get("input_tokens", 0)) for r in rows)
    tokens_out = sum(int(r.get("output_tokens", 0)) for r in rows)
    return {
        "n": n,
        "correct": correct,
        "correct_rate": rate,
        "correct_ci": (lo, hi),
        "pre_vote_correct_mean": sum(pre_correct) / n,
        "disagree_rate": disagree / n,
        "disagree": disagree,
        "mean_uniques_cited": sum(uniques) / n,
        "mean_decisive_cited": sum(decisive) / n,
        "first_speaker_table": {"a": a, "b": b, "c": c, "d": d},
        "first_speaker_or": or_,
        "first_speaker_or_ci": (or_lo, or_hi),
        "echo_by_round": echo,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "cost_usd": cost_usd(tokens_in, tokens_out),
    }


def format_summary_table(cells: dict[str, dict[str, Any]]) -> str:
    head = (
        "| cell | n | final-correct | 95% CI | pre-vote correct | P3 disagree | "
        "uniques/run | decisive/run | first-speaker OR | echo r2 | echo r3 | cost |"
    )
    lines = [head, "|" + "---|" * 12]
    for name, s in cells.items():
        if s.get("n", 0) == 0:
            lines.append(f"| {name} | 0 | | | | | | | | | | |")
            continue
        lo, hi = s["correct_ci"]
        e = s["echo_by_round"]
        lines.append(
            f"| {name} | {s['n']} | {s['correct']}/{s['n']} = {s['correct_rate']:.2f} | "
            f"[{lo:.2f}, {hi:.2f}] | {s['pre_vote_correct_mean']:.2f} | "
            f"{s['disagree']}/{s['n']} = {s['disagree_rate']:.2f} | "
            f"{s['mean_uniques_cited']:.1f} | {s['mean_decisive_cited']:.1f} | "
            f"{s['first_speaker_or']:.2f} [{s['first_speaker_or_ci'][0]:.2f}, "
            f"{s['first_speaker_or_ci'][1]:.2f}] | "
            f"{e.get(1, float('nan')):.2f} | {e.get(2, float('nan')):.2f} | ${s['cost_usd']:.2f} |"
        )
    return "\n".join(lines)

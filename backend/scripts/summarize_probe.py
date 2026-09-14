"""Summarise probe_free_discussion.py JSONL output: one markdown row per cell.

Usage:
  .venv/bin/python scripts/summarize_probe.py probes.jsonl [more.jsonl ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.probe_stats import wilson_ci


def load_lines(paths: list[str]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for path in paths:
        for raw in Path(path).read_text().splitlines():
            raw = raw.strip()
            if raw:
                lines.append(json.loads(raw))
    return lines


_COST_PER_M = {  # (input $/Mtok, output $/Mtok)
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-5": (3.0, 15.0),
}


def _cost(record: dict[str, Any]) -> float:
    prices = _COST_PER_M.get(str(record.get("model", "")))
    if prices is None:
        return 0.0
    tokens = record.get("tokens", {})
    return float(tokens.get("input", 0) * prices[0] + tokens.get("output", 0) * prices[1]) / 1e6


def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.2f}"


def cell_rows(lines: list[dict[str, Any]]) -> list[str]:
    runs: dict[str, list[dict[str, Any]]] = {}
    pooled: dict[str, float] = {}
    alone: dict[str, float] = {}
    for line in lines:
        cell = str(line.get("cell", ""))
        if line.get("kind") == "run":
            runs.setdefault(cell, []).append(line)
        elif line.get("kind") == "pooled_baseline":
            pooled[cell] = float(line.get("right_rate", 0.0))
        elif line.get("kind") == "alone_baseline":
            alone[cell] = float(line.get("wrong_rate", 0.0))

    n_rounds = max((len(r.get("echo_by_round", [])) for rs in runs.values() for r in rs), default=0)
    header = (
        "| cell | n | correct | Wilson 95% CI | uniques cited | decisive surfaced | "
        "% final≠spoken | "
        + " | ".join(f"echo r{r + 1}" for r in range(n_rounds))
        + " | pooled right | alone wrong | tokens (in/out) | est. cost |"
    )
    sep = "|" + "---|" * (header.count("|") - 1)
    rows = [header, sep]
    for cell in sorted(runs):
        rs = runs[cell]
        n = len(rs)
        k = sum(1 for r in rs if r.get("correct"))
        lo, hi = wilson_ci(k, n)
        uniques = [
            r["n_uniques_cited"] / r["n_uniques_total"] for r in rs if r.get("n_uniques_total")
        ]
        decisive = [
            r["decisive_surfaced_count"] / r["decisive_total"]
            for r in rs
            if r.get("decisive_total")
        ]
        differs = sum(1 for r in rs if r.get("final_differs_from_spoken")) / n
        echo_means = [
            sum(
                (r.get("echo_by_round", [])[i] if i < len(r.get("echo_by_round", [])) else 0.0)
                for r in rs
            )
            / n
            for i in range(n_rounds)
        ]
        tok_in = sum(r.get("tokens", {}).get("input", 0) for r in rs) / n
        tok_out = sum(r.get("tokens", {}).get("output", 0) for r in rs) / n
        rows.append(
            f"| {cell} | {n} | {k / n:.2f} | [{lo:.2f}, {hi:.2f}] | "
            f"{_fmt(sum(uniques) / len(uniques) if uniques else None)} | "
            f"{_fmt(sum(decisive) / len(decisive) if decisive else None)} | "
            f"{differs:.2f} | "
            + " | ".join(f"{e:.2f}" for e in echo_means)
            + f" | {_fmt(pooled.get(cell))} | {_fmt(alone.get(cell))} | "
            f"{tok_in:.0f}/{tok_out:.0f} | ${sum(_cost(r) for r in rs):.2f} |"
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    lines = load_lines(args.files)
    print("\n".join(cell_rows(lines)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

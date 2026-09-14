"""Generate the committed S5 scenario audit from probe outputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
GATE_DIR = ROOT / "backend/scripts/probe/out/gate_s5"
NULL_DIR = ROOT / "backend/scripts/probe/out/gate_null_s5"
STATIC_PATH = ROOT / "docs/probes/S5_static_table.txt"
REPORT_PATH = ROOT / "docs/probes/S5_scenario_audit.md"
SURVIVORS = {
    "stasser-1985-hidden",
    "hiddenbench-laboratory-theft-deduction",
    "hiddenbench-company-acquisition-decision",
}
SERVED = SURVIVORS | {"hiring-panel-flat-v2", "hiring-panel-null"}
RETIRED = {
    "hiring-panel-v1",
    "hiring-panel-3",
    "hiring-panel-7",
    "hiring-panel-9",
    "hiring-weak-profile-v1",
    "hiring-adversarial-v1",
    "hiring-panel-flat",
}


def load_jsons(directory: Path, suffix: str) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for path in directory.glob(f"*_{suffix}.json"):
        body = json.loads(path.read_text())
        scenario = body["scenario"].removesuffix("-twin")
        result[(scenario, body["prompt"])] = body
    return result


def pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value * 100:.0f}%"


def ci(value: float, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.96
    denominator = 1 + z * z / n
    centre = (value + z * z / (2 * n)) / denominator
    half = z * ((value * (1 - value) / n + z * z / (4 * n * n)) ** 0.5) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def parse_static(text: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    rows: dict[str, dict[str, str]] = {}
    lines = text.rstrip().splitlines()
    for line in lines:
        if not line or line.startswith(("scenario ", "S5 static", "correct =", "Per-agent")):
            continue
        parts = line.split()
        if len(parts) < 8 or not re.fullmatch(r"\d+", parts[1]):
            continue
        status_index = next(
            (i for i, value in enumerate(parts[7:], 7) if value == "PASS" or value == "FAIL"),
            None,
        )
        if status_index is None:
            continue
        alone = " ".join(parts[7:status_index])
        margins = re.search(r"\((?:margins )?([^)]+)\)", alone)
        min_alone = "—"
        if margins:
            values = [int(value) for value in re.findall(r"-?\d+", margins.group(1))]
            if values:
                min_alone = str(min(values))
        rows[parts[0]] = {
            "k": parts[1],
            "agents": parts[3],
            "pooled_margin": parts[5],
            "min_alone": min_alone,
            "status": " ".join(parts[status_index:]),
        }
    return rows, lines


def rate_line(data: dict[str, Any], *, include_ci: bool = True) -> str:
    bits = []
    for candidate, value in data["rates"].items():
        text = pct(value["rate"])
        if include_ci:
            text += f" [{pct(value['ci'][0])}–{pct(value['ci'][1])}]"
        bits.append(f"{candidate} {text}")
    return "; ".join(bits)


def order_split(cell: dict[str, Any], correct: str, pooled: bool) -> tuple[list[str], list[str]]:
    columns: list[str] = []
    flags: list[str] = []
    for first, counts in cell["by_first_listed"].items():
        n = sum(counts.values())
        if pooled:
            numerator = counts.get(correct, 0)
        else:
            numerator = sum(
                count for vote, count in counts.items() if vote not in {correct, "undecided"}
            )
        lo, hi = ci(numerator / n if n else 0.0, n)
        columns.append(
            f"{first}: {dict(counts)} ({pct(numerator / n if n else 0.0)} [{pct(lo)}–{pct(hi)}])"
        )
        if numerator / n < 0.5:
            flags.append(f"{first}={pct(numerator / n)}")
    return columns, flags


def g1_order_table(body: dict[str, Any]) -> str:
    correct = body["correct"]
    rows = []
    for cell_id, cell in body["cells"].items():
        columns, _ = order_split(cell, correct, cell_id == "pooled")
        rows.append(f"| {cell_id} | " + " | ".join(columns) + " |")
    orders = sorted({first for cell in body["cells"].values() for first in cell["by_first_listed"]})
    return "\n".join(
        [
            "| cell | " + " | ".join(orders) + " |",
            "| --- | " + " | ".join("---" for _ in orders) + " |",
            *rows,
        ]
    )


def g0_order_table(body: dict[str, Any]) -> str:
    orders = sorted({first for cell in body["cells"].values() for first in cell["by_first_listed"]})
    rows = []
    for cell_id, cell in body["cells"].items():
        columns = []
        for first in orders:
            counts = cell["by_first_listed"].get(first, {})
            n = sum(counts.values())
            rates = []
            for candidate in cell["rates"]:
                value = counts.get(candidate, 0) / n if n else 0.0
                lo, hi = ci(value, n)
                rates.append(f"{candidate} {pct(value)} [{pct(lo)}–{pct(hi)}]")
            columns.append(f"{dict(counts)}; " + "; ".join(rates))
        rows.append(f"| {cell_id} | " + " | ".join(columns) + " |")
    return "\n".join(
        [
            "| cell | " + " | ".join(orders) + " |",
            "| --- | " + " | ".join("---" for _ in orders) + " |",
            *rows,
        ]
    )


def order_dependence(body: dict[str, Any]) -> list[str]:
    flags = []
    for cell_id, cell in body["cells"].items():
        _, bad = order_split(cell, body["correct"], cell_id == "pooled")
        if bad:
            metric = "pooled correct" if cell_id == "pooled" else "alone-wrong"
            flags.append(f"{cell_id} {metric} below 50% at " + ", ".join(bad))
    return flags


def verdict(scenario: str, naive: dict[str, Any], default: dict[str, Any]) -> str:
    if scenario in SURVIVORS:
        result = "FAILS-G0"
    elif naive["pass"] and default["pass"]:
        result = "PASS-G1G2"
    elif naive["correct"] is None or default["correct"] is None:
        result = "FAIL-G2"
    else:
        result = "FAIL-G1/G2"
    if scenario in RETIRED:
        return f"{result} (retired by #30)"
    if scenario in {"hiring-panel-flat-v2", "hiring-panel-null"}:
        return f"{result} (pre-#30 5-panelist S5; re-tuned in #30)"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    parser.add_argument("--static", type=Path, default=STATIC_PATH)
    args = parser.parse_args()
    gate = load_jsons(GATE_DIR, "*")
    null = load_jsons(NULL_DIR, "*")
    static, static_lines = parse_static(args.static.read_text())
    scenarios = sorted({scenario for scenario, _ in gate})

    lines = [
        "# S5 scenario audit",
        "",
        (
            "Method: WIF authentication with `claude-haiku-4-5`, balanced cyclic candidate rotation, "
            "8 samples/cell for 2-candidate scenarios and 6 samples/cell for 3-candidate scenarios, "
            "under both naive and default prompts. G0 used twin-null scenarios with 3 seeds × 6 = "
            "18 ballots/cell and a null band of 1/k ± 15 percentage points (`[0.18, 0.48]` for k=3). "
            "Total cost: G1/G2 $1.69 for 25 scenarios × 2 prompts; G0 $0.66 first pass + $0.19 "
            "company rerun."
        ),
        "",
        "## Main table",
        "",
        "| scenario | k | agents | static pooled margin | static min alone margin | G1 naive alone-wrong | G1 default alone-wrong | G2 naive pooled-right | G2 default pooled-right | G0 pooled naive/default | verdict | served |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | --- | --- | :---: |",
    ]
    for scenario in scenarios:
        naive = gate[(scenario, "naive")]
        default = gate[(scenario, "default")]
        meta = static.get(scenario, {})
        naive_rates = "/".join(pct(v) for v in naive["alone_wrong"].values())
        default_rates = "/".join(pct(v) for v in default["alone_wrong"].values())
        g0 = []
        for prompt in ("naive", "default"):
            if scenario not in SURVIVORS:
                g0.append("not run")
            else:
                pooled = null[(scenario, prompt)]["cells"]["pooled"]["rates"]
                g0.append(
                    ", ".join(
                        f"{candidate} {pct(value['rate'])}" for candidate, value in pooled.items()
                    )
                )
        lines.append(
            f"| {scenario} | {meta.get('k', '?')} | {meta.get('agents', '?')} | "
            f"{meta.get('pooled_margin', '—')} | {meta.get('min_alone', '—')} | {naive_rates} | "
            f"{default_rates} | {pct(naive['pooled_right'])} | {pct(default['pooled_right'])} | "
            f"{' / '.join(g0)} | {verdict(scenario, naive, default)} | "
            f"{'yes' if scenario in SERVED else 'no'} |"
        )

    lines += ["", "## Survivor detail"]
    for scenario in sorted(SURVIVORS):
        lines += ["", f"### {scenario}"]
        for prompt in ("naive", "default"):
            body = gate[(scenario, prompt)]
            null_body = null[(scenario, prompt)]
            lines += [
                "",
                f"#### G1/G2 — {prompt}",
                f"Correct candidate: `{body['correct']}`; shared-only verdict: `{body['shared_verdict']}`.",
                "",
                g1_order_table(body),
                "",
                "Reason excerpts (pooled):",
                *[f"- {reason}" for reason in body["cells"]["pooled"]["reasons"][:2]],
            ]
            first_agent = next(agent for agent in body["cells"] if agent != "pooled")
            lines += [
                f"Reason excerpts ({first_agent}):",
                *[f"- {reason}" for reason in body["cells"][first_agent]["reasons"][:2]],
                "",
                f"#### G0 twin-null — {prompt}",
                f"Null band: [{null_body['lo']:.2f}, {null_body['hi']:.2f}].",
                "",
                g0_order_table(null_body),
                "",
                "Reason excerpts: gate_null does not persist reason text; no G0 excerpts were available.",
            ]
            flags = order_dependence(body)
            lines.append("order dependence: " + ("; ".join(flags) if flags else "none"))

    lines += ["", "## Notes for non-survivors"]
    for scenario in scenarios:
        if scenario in SURVIVORS:
            continue
        body = gate[(scenario, "naive")]
        failing = "G2" if body["correct"] is None else "G1/G2"
        cell_id = (
            "pooled"
            if body["correct"] is None or body["pooled_right"] < 0.8
            else next(agent for agent, rate in body["alone_wrong"].items() if rate < 0.8)
        )
        cell = body["cells"][cell_id]
        columns, _ = order_split(cell, body["correct"] or "", cell_id == "pooled")
        lines += [
            "",
            (
                f"- **{scenario}** — failing gate: {failing}; naive `{cell_id}` counts: "
                f"`{cell['counts']}` with Wilson CI `{cell['ci']}`."
            ),
            f"  - Counts: `{cell['counts']}`; Wilson CI: `{cell['ci']}`; first-listed split: "
            + "; ".join(columns),
            "  - Reason excerpts: " + " | ".join(cell["reasons"][:2]),
        ]

    lines += [
        "",
        "## Known issue: HiddenBench converter mis-tags items",
        "",
        "backend/app/scenarios/papers/hiddenbench.py infers each fact's candidate/valence via `_mentions(text, answers)` against the full answer strings (e.g. 'Option B: AI hardware startup'), so facts that refer to a candidate by short alias ('Option B has a stable revenue base…') are tagged to the wrong candidate (here option-c-logistics-software-company) or dropped. Consequences: the static arithmetic table for hiddenbench-* is unreliable (two scenarios that 'fail' statically pass G1/G2 with Haiku), and the frontend's designed-verdict panels for these scenarios are wrong. Not fixed in this PR per user decision; fix = alias-aware matching (full name, colon-prefix, id; longest-first, word-boundary) as implemented for twin_null in scripts/probe_lib.py, then re-derive candidate/valence and re-run the static check.",
        "",
        "## Appendix: static arithmetic table",
        "",
        "```text",
        *static_lines,
        "```",
        "",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines))


if __name__ == "__main__":
    main()

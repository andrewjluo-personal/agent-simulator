"""Perceived-valence calibration: does the model read each item's sign the way the
scenario designer coded it?

For every fact in a scenario, ask the model (n samples each) how the item, on its
own, moves the recommendation, under two prompts:
  (i)  calibrate: {"rating": 1..5, "direction": <candidate id>|"neutral"} — signed as
       +rating if direction == the item's candidate, -rating if the other candidate, 0
       if neutral (i.e. sign is relative to the item's candidate, like `valence`).
  (ii) neutral:   {"score": -2..+2} — more/less likely to recommend the item's candidate.

Prints per-item designed vs perceived sign, lists disagreements, and recomputes the
shared-only / per-hand / pooled tallies with perceived weights.

Usage:
  .venv/bin/python scripts/perceived_profile.py hiring-panel-flat hiring-panel-flat:mirror \
      hiring-panel-v1 [--samples 5] [--out DIR]
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

from probe_lib import cost_usd, load_scenario_arg

from app import truth, validate
from app.llm import AnthropicClient, LLMClient, LLMRequest
from app.models import Fact, Scenario

MODEL = "claude-haiku-4-5"


def _candidate_lines(scenario: Scenario) -> str:
    return "\n".join(f"- {c.name}: {c.blurb}" for c in scenario.candidates)


def calibrate_system(scenario: Scenario) -> str:
    ids = "|".join(f'"{c.id}"' for c in scenario.candidates)
    return f"""{scenario.brief}
Candidates:
{_candidate_lines(scenario)}

You will be shown ONE observation from an interviewer's notes. Rate how much that single
observation, on its own, should move a reasonable panel's recommendation, and toward whom.
Scale: 1 = trivial/minor, 2 = a small point, 3 = a solid point, 4 = a major factor,
5 = decisive on its own. "direction" is the candidate the observation favours.
Respond with JSON only: {{"rating": 1..5, "direction": {ids}|"neutral"}}"""


def neutral_system(scenario: Scenario, candidate_name: str) -> str:
    return f"""{scenario.brief}
Candidates:
{_candidate_lines(scenario)}

You will be shown ONE observation from an interviewer's notes about {candidate_name}.
Does it make you more or less likely to recommend {candidate_name}?
-2 = clearly less likely, -1 = slightly less, 0 = no effect, +1 = slightly more,
+2 = clearly more likely.
Respond with JSON only: {{"score": -2..2}}"""


def _int(raw: dict[str, Any] | None, key: str) -> int | None:
    if not raw or key not in raw:
        return None
    try:
        return round(float(raw[key]))
    except (TypeError, ValueError):
        return None


class Rater:
    def __init__(self, client: LLMClient, samples: int, concurrency: int = 6) -> None:
        self.client = client
        self.samples = samples
        self.sem = asyncio.Semaphore(concurrency)
        self.input_tokens = 0
        self.output_tokens = 0

    async def _ask(self, system: str, user: str) -> dict[str, Any] | None:
        async with self.sem:
            resp = await self.client.complete(
                LLMRequest(system=system, user=user, model=MODEL, max_tokens=60)
            )
        self.input_tokens += resp.input_tokens or 0
        self.output_tokens += resp.output_tokens or 0
        return validate.parse_json_object(resp.text)

    async def calibrate(self, scenario: Scenario, fact: Fact) -> list[int]:
        system = calibrate_system(scenario)
        text = fact.memo_text or fact.text
        other = {c.id for c in scenario.candidates} - {fact.candidate_id}
        out: list[int] = []
        for raw in await asyncio.gather(*(self._ask(system, text) for _ in range(self.samples))):
            rating = _int(raw, "rating")
            direction = str((raw or {}).get("direction", "neutral")).lower()
            if rating is None:
                continue
            if direction == fact.candidate_id:
                out.append(rating)
            elif direction in other:
                out.append(-rating)
            else:
                out.append(0)
        return out

    async def neutral(self, scenario: Scenario, fact: Fact) -> list[int]:
        name = next(c.name for c in scenario.candidates if c.id == fact.candidate_id)
        system = neutral_system(scenario, name)
        text = fact.memo_text or fact.text
        out: list[int] = []
        for raw in await asyncio.gather(*(self._ask(system, text) for _ in range(self.samples))):
            score = _int(raw, "score")
            if score is not None:
                out.append(max(-2, min(2, score)))
        return out


def _mean(xs: list[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _sign(x: float, eps: float = 0.5) -> int:
    return 0 if abs(x) < eps else (1 if x > 0 else -1)


def tallies(scenario: Scenario, weight: dict[str, float]) -> dict[str, dict[str, float]]:
    """Per-candidate totals under an arbitrary signed weight per fact, for
    shared-only, each hand, and pooled."""

    def total(ids: set[str] | list[str]) -> dict[str, float]:
        t = {c.id: 0.0 for c in scenario.candidates}
        for fid in set(ids):
            t[scenario.fact(fid).candidate_id] += weight[fid]
        return {k: round(v, 2) for k, v in t.items()}

    out = {"shared": total(truth.shared_fact_ids(scenario))}
    for agent_id, held in scenario.distribution.items():
        out[f"hand:{agent_id}"] = total(held)
    out["pooled"] = total(truth.pooled_fact_ids(scenario))
    return out


def _winner(t: dict[str, float]) -> str:
    best = max(t.values())
    winners = [k for k, v in t.items() if v == best]
    return winners[0] if len(winners) == 1 else truth.UNDECIDED


async def profile(scenario: Scenario, rater: Rater) -> dict[str, Any]:
    cal = await asyncio.gather(*(rater.calibrate(scenario, f) for f in scenario.facts))
    neu = await asyncio.gather(*(rater.neutral(scenario, f) for f in scenario.facts))
    shared = truth.shared_fact_ids(scenario)
    items: list[dict[str, Any]] = []
    for f, c, n in zip(scenario.facts, cal, neu, strict=True):
        designed = truth.signed_weight(f)
        cm, nm = _mean(c), _mean(n)
        items.append(
            {
                "id": f.id,
                "candidate": f.candidate_id,
                "kind": "shared" if f.id in shared else "unique",
                "designed": designed,
                "calibrate_signed": c,
                "calibrate_mean": round(cm, 2),
                "neutral_scores": n,
                "neutral_mean": round(nm, 2),
                "disagree_calibrate": _sign(designed) != 0 and _sign(cm) == -_sign(designed),
                "disagree_neutral": _sign(designed) != 0 and _sign(nm) == -_sign(designed),
                "weak_calibrate": _sign(designed) != 0 and _sign(cm) == 0,
                "weak_neutral": _sign(designed) != 0 and _sign(nm) == 0,
                "text": f.memo_text or f.text,
            }
        )
    designed_w = {f.id: float(truth.signed_weight(f)) for f in scenario.facts}
    cal_w = {it["id"]: float(it["calibrate_mean"]) for it in items}
    neu_w = {it["id"]: float(it["neutral_mean"]) for it in items}
    return {
        "scenario": scenario.id,
        "items": items,
        "tallies": {
            "designed": tallies(scenario, designed_w),
            "calibrate": tallies(scenario, cal_w),
            "neutral": tallies(scenario, neu_w),
        },
    }


def render(result: dict[str, Any]) -> str:
    lines = [f"## {result['scenario']}", ""]
    lines.append(
        "| id | kind | cand | designed | calibrate (±rating) | neutral (−2..2) | flag | text |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for it in sorted(result["items"], key=lambda x: (x["kind"], x["candidate"], x["id"])):
        flags = []
        if it["disagree_calibrate"]:
            flags.append("DIS-cal")
        if it["disagree_neutral"]:
            flags.append("DIS-neu")
        if it["weak_calibrate"]:
            flags.append("weak-cal")
        if it["weak_neutral"]:
            flags.append("weak-neu")
        lines.append(
            f"| {it['id']} | {it['kind']} | {it['candidate']} | {it['designed']:+d} | "
            f"{it['calibrate_mean']:+.1f} | {it['neutral_mean']:+.1f} | {' '.join(flags)} | "
            f"{it['text']} |"
        )
    lines.append("")
    lines.append("| tally | designed | calibrate | neutral |")
    lines.append("|---|---|---|---|")
    t = result["tallies"]
    for key in t["designed"]:
        cells = []
        for src in ("designed", "calibrate", "neutral"):
            tt = t[src][key]
            cells.append(" / ".join(f"{k} {v:+.1f}" for k, v in tt.items()) + f" → {_winner(tt)}")
        lines.append(f"| {key} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenarios", nargs="+")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--out", default="scripts/probe/out/perceived")
    args = parser.parse_args()

    rater = Rater(AnthropicClient(), args.samples)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for arg in args.scenarios:
        scenario = load_scenario_arg(arg)
        result = await profile(scenario, rater)
        (out_dir / f"{scenario.id}.json").write_text(json.dumps(result, indent=1))
        text = render(result)
        (out_dir / f"{scenario.id}.md").write_text(text)
        print(text)
        print()
    print(
        f"tokens: {rater.input_tokens} in / {rater.output_tokens} out "
        f"(~${cost_usd(rater.input_tokens, rater.output_tokens):.2f})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

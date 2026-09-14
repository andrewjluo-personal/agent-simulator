"""Rewrite the scenario snapshot embedded in a sample's finished runs after a
tag-only fix to its facts (candidate_id / valence / weight), and re-stamp them.

Each run row carries its own copy of the scenario, which the replay UI uses to
tint fact chips and compute the "if each voted alone" badge. When a sample's
fact tags are corrected without changing fact ids, texts, or the distribution,
the recorded transcripts and votes stay valid, so the runs can be kept: this
script swaps in the current code definition of the scenario, moves the runs
to its new per-scenario stamp, and upserts the scenario row so /api/demo keeps
serving them before the next deploy. It refuses to touch runs whose stored facts
differ from the code in anything other than tags (or whose pooled verdict or
decisive set would change), because then metrics.correct / decisive_surfaced
would no longer hold.

Requires DATABASE_URL.

Usage:
  .venv/bin/python scripts/retag_demo_runs.py <scenario_id> --from <old_stamp> [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from psycopg.types.json import Jsonb

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import db, truth
from app.engine_version import scenario_engine_version
from app.models import Scenario
from app.samples import SAMPLES_BY_ID

_TAG_FIELDS = {"candidate_id", "valence", "weight"}


def _untagged(scenario: Scenario) -> dict[str, object]:
    body = scenario.model_dump(exclude={"validation", "created_at", "is_sample", "title", "source"})
    body["facts"] = [
        {k: v for k, v in fact.items() if k not in _TAG_FIELDS} for fact in body["facts"]
    ]
    return body


def _check_compatible(stored: Scenario, current: Scenario) -> None:
    if _untagged(stored) != _untagged(current):
        raise SystemExit("stored scenario differs from code in more than fact tags; aborting")
    if truth.pooled_verdict(stored) != truth.pooled_verdict(current):
        raise SystemExit("pooled verdict would change; aborting")
    if truth.decisive_fact_ids(stored) != truth.decisive_fact_ids(current):
        raise SystemExit("decisive fact set would change; aborting")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario_id")
    parser.add_argument("--from", dest="old_stamp", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    current = SAMPLES_BY_ID[args.scenario_id]
    new_stamp = scenario_engine_version(current)
    if new_stamp == args.old_stamp:
        raise SystemExit("old stamp equals the current stamp; nothing to do")

    with db.connection() as conn:
        rows = conn.execute(
            "select id, scenario from runs where scenario_id = %s and engine_version = %s and status = 'done'",
            (args.scenario_id, args.old_stamp),
        ).fetchall()
        if not rows:
            raise SystemExit(f"no finished runs for {args.scenario_id} with stamp {args.old_stamp}")
        for row in rows:
            _check_compatible(Scenario.model_validate(row["scenario"]), current)
        print(f"{len(rows)} runs compatible; new stamp {new_stamp}")
        if args.dry_run:
            return
        cur = conn.execute(
            "update runs set scenario = %s, engine_version = %s "
            "where scenario_id = %s and engine_version = %s and status = 'done'",
            (Jsonb(current.model_dump(by_alias=True)), new_stamp, args.scenario_id, args.old_stamp),
        )
        print(f"{cur.rowcount} runs updated")
    db.Store().upsert_scenario(current)
    print("scenario row upserted")


if __name__ == "__main__":
    main()

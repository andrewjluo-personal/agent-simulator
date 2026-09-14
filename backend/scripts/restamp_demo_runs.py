"""Re-stamp demo runs after a sample-pool-only change.

Runs are now stamped per scenario (scenario_engine_version). When samples.py was
removed from the engine hash, scenario edits stopped invalidating other
scenarios' demos — but runs seeded under the old scheme carry the old global
stamp. This script rewrites engine_version for demo runs that carry any of the
--from <old_stamp> values to each sample scenario's current per-scenario stamp.
--from is repeatable: pass every old global stamp present in prod.

Only valid when the engine files (prompts.py, orchestrator.py, truth.py,
paradigms.py) are unchanged since the runs were made — verified for old stamp
cf661a0a20ef (commit 63194d4 vs main: only samples.py differs).

Requires DATABASE_URL (uses the same connection helpers as app/db.py).

Usage:
  .venv/bin/python scripts/restamp_demo_runs.py \
      --from cf661a0a20ef --from c69df7af8564 [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import db
from app.engine_version import scenario_engine_version
from app.samples import SAMPLE_SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="old_stamps", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with db.connection() as conn:
        for scenario in SAMPLE_SCENARIOS:
            new_stamp = scenario_engine_version(scenario)
            if args.dry_run:
                row = conn.execute(
                    "select count(*) as n from runs where is_demo "
                    "and scenario_id = %s and engine_version = any(%s)",
                    (scenario.id, args.old_stamps),
                ).fetchone()
                n = row["n"] if row else 0
                print(f"{scenario.id}: {n} runs would be re-stamped to {new_stamp}")
                continue
            cur = conn.execute(
                "update runs set engine_version = %s "
                "where is_demo and scenario_id = %s and engine_version = any(%s)",
                (new_stamp, scenario.id, args.old_stamps),
            )
            print(f"{scenario.id}: {cur.rowcount} runs re-stamped to {new_stamp}")


if __name__ == "__main__":
    main()

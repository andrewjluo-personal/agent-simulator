"""Convert selected HiddenBench tasks into Scenario JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import truth
from app.models import Scenario
from app.scenarios.papers.hiddenbench import convert_task


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--ids", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tasks: list[dict[str, Any]] = json.loads(args.input.read_text())
    wanted = {int(value) for value in args.ids.split(",") if value}
    scenarios: list[Scenario] = []
    warning_count = 0
    warning_ids: list[str] = []
    for task in tasks:
        if int(task["id"]) not in wanted:
            continue
        scenario = convert_task(task)
        if truth.pooled_verdict(scenario) != next(
            candidate.id
            for candidate in scenario.candidates
            if candidate.name == task["correct_answer"]
        ):
            warning = " WARNING: pooled arithmetic does not select the correct answer"
            scenario.source.notes = (scenario.source.notes or "") + warning
            warning_count += 1
            warning_ids.append(scenario.id)
        scenarios.append(scenario)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps([scenario.model_dump(by_alias=True) for scenario in scenarios], indent=2) + "\n"
    )
    print(f"wrote {len(scenarios)} scenarios; warnings={warning_count}; warning_ids={warning_ids}")


if __name__ == "__main__":
    main()

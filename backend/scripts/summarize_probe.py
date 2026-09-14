"""Summarise probe_free_discussion output.

Usage:
  .venv/bin/python scripts/summarize_probe.py DIR [DIR ...]
DIR is either a cell directory containing runs.jsonl or a parent whose subdirectories are cells.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from probe_lib import format_summary_table, read_jsonl, summarize_runs


def collect(paths: list[Path]) -> dict[str, dict[str, Any]]:
    cells: dict[str, dict[str, Any]] = {}
    for p in paths:
        if (p / "runs.jsonl").exists():
            cells[p.name] = summarize_runs(read_jsonl(p / "runs.jsonl"))
            continue
        for sub in sorted(p.iterdir()):
            if (sub / "runs.jsonl").exists():
                cells[sub.name] = summarize_runs(read_jsonl(sub / "runs.jsonl"))
    return cells


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    print(format_summary_table(collect([Path(a) for a in argv])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

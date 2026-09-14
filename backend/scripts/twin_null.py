"""Build a symmetric twin-null scenario from a sample scenario."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from probe_lib import load_scenario_arg, twin_null


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = twin_null(load_scenario_arg(args.scenario))
    text = result.model_dump_json(indent=2, by_alias=True)
    if args.out:
        args.out.write_text(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

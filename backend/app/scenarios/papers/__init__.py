"""Paper-aligned scenario libraries.

`haiku_badges.json` holds stored Haiku validation results produced by
`scripts/validate_libraries.py`; they are attached as `Scenario.validation`.
"""

import json
from pathlib import Path

from app.models import Scenario, ValidationResult

from .hiddenbench import HIDDENBENCH_SCENARIOS
from .stasser_1985 import STASSER_1985_SCENARIOS
from .stasser_1992 import STASSER_1992_SCENARIOS

BADGE_MODEL = "claude-haiku-4-5"
_BADGES: dict[str, ValidationResult] = {
    scenario_id: ValidationResult.model_validate(body)
    for scenario_id, body in json.loads(
        (Path(__file__).parent / "haiku_badges.json").read_text()
    ).items()
}


def _with_badge(scenario: Scenario) -> Scenario:
    badge = _BADGES.get(scenario.id)
    if badge is None:
        return scenario
    return scenario.model_copy(update={"validation": {BADGE_MODEL: badge}})


PAPER_SCENARIOS: list[Scenario] = [
    _with_badge(s) for s in STASSER_1985_SCENARIOS + STASSER_1992_SCENARIOS + HIDDENBENCH_SCENARIOS
]

__all__ = ["PAPER_SCENARIOS"]

"""Paper-aligned scenario libraries."""

from app.models import Scenario

from .hiddenbench import HIDDENBENCH_SCENARIOS
from .stasser_1985 import STASSER_1985_SCENARIOS
from .stasser_1992 import STASSER_1992_SCENARIOS

PAPER_SCENARIOS: list[Scenario] = (
    STASSER_1985_SCENARIOS + STASSER_1992_SCENARIOS + HIDDENBENCH_SCENARIOS
)

__all__ = ["PAPER_SCENARIOS"]

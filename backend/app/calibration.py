"""Item-calibration logic: do unique (hidden-profile-critical) facts carry the same
rated importance as shared facts? Pure functions; the script does the sampling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationResult:
    shared_mean: float
    unique_mean: float
    gap: float  # unique_mean - shared_mean
    passes: bool
    per_item: dict[str, float]


def gap_check(
    ratings: Mapping[str, Sequence[float]],
    shared_ids: set[str],
    threshold: float = 0.3,
) -> CalibrationResult:
    """Mean rating per item, then the unique-vs-shared mean gap. Passes when the
    absolute gap is strictly below `threshold`."""
    per_item = {k: sum(v) / len(v) for k, v in ratings.items() if v}
    shared = [m for k, m in per_item.items() if k in shared_ids]
    unique = [m for k, m in per_item.items() if k not in shared_ids]
    shared_mean = sum(shared) / len(shared) if shared else 0.0
    unique_mean = sum(unique) / len(unique) if unique else 0.0
    gap = unique_mean - shared_mean
    return CalibrationResult(
        shared_mean=shared_mean,
        unique_mean=unique_mean,
        gap=gap,
        passes=abs(gap) < threshold,
        per_item=per_item,
    )

from __future__ import annotations

from app.calibration import gap_check


def test_gap_check_passes_small_gap() -> None:
    res = gap_check(
        {"S1": [4.0, 4.0], "S2": [4.0], "U1": [4.2, 4.0], "U2": [4.1]},
        {"S1", "S2"},
    )
    assert res.shared_mean == 4.0
    assert abs(res.unique_mean - 4.1) < 1e-9
    assert abs(res.gap - 0.1) < 1e-9
    assert res.passes


def test_gap_check_fails_large_positive_gap() -> None:
    res = gap_check({"S1": [3.0], "U1": [3.5]}, {"S1"})
    assert res.gap == 0.5
    assert not res.passes


def test_gap_check_fails_large_negative_gap() -> None:
    res = gap_check({"S1": [3.5], "U1": [3.0]}, {"S1"})
    assert res.gap == -0.5
    assert not res.passes


def test_gap_check_boundary_is_strict() -> None:
    # 1.3 - 1.0 lands exactly on the threshold; strict < means boundary fails
    res = gap_check({"S1": [1.0], "U1": [1.3]}, {"S1"}, threshold=0.3)
    assert abs(res.gap - 0.3) < 1e-9
    assert not res.passes

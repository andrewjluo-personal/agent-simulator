from __future__ import annotations

from app import probe_stats
from app.models import Turn


def _turn(seq: int, round_: int, agent: str, sentences: list[str]) -> Turn:
    return Turn(
        seq=seq,
        round=round_,
        agent_id=agent,
        sentences=sentences,
        cited=[],
        hallucinated=[],
        lean="sally",
        confidence=0.5,
    )


def test_wilson_ci_known_values() -> None:
    lo, hi = probe_stats.wilson_ci(0, 20)
    assert lo == 0.0
    assert abs(hi - 0.1611) < 0.005

    lo, hi = probe_stats.wilson_ci(20, 20)
    assert abs(lo - 0.8389) < 0.005
    assert hi == 1.0

    lo, hi = probe_stats.wilson_ci(6, 7)
    assert abs(lo - 0.4869) < 0.005
    assert abs(hi - 0.9743) < 0.005


def test_wilson_ci_empty() -> None:
    assert probe_stats.wilson_ci(0, 0) == (0.0, 0.0)


def test_echo_identical_repeated_sentence() -> None:
    earlier = [_turn(0, 0, "a", ["Sally closed the ledger migration without downtime"])]
    turn = _turn(1, 0, "b", ["Sally closed the ledger migration without downtime"])
    assert probe_stats.turn_echo(turn, earlier) == 1.0


def test_echo_disjoint() -> None:
    earlier = [_turn(0, 0, "a", ["Sally closed the ledger migration without downtime"])]
    turn = _turn(1, 0, "b", ["completely unrelated words about something else entirely"])
    assert probe_stats.turn_echo(turn, earlier) == 0.0


def test_echo_skips_short_turns_and_same_agent() -> None:
    earlier = [
        _turn(0, 0, "a", ["one two three four five six"]),
        _turn(1, 0, "a", ["echoed content"]),
    ]
    # same-agent earlier text must not count
    echo = probe_stats.turn_echo(_turn(2, 0, "a", ["one two three four five six"]), earlier)
    assert echo == 0.0
    # <4 words -> skipped (None)
    assert probe_stats.turn_echo(_turn(3, 0, "b", ["too short"]), earlier) is None
    assert probe_stats.echo_by_round(
        [_turn(0, 0, "a", ["too short"]), _turn(1, 1, "b", ["too short"])], 2
    ) == [0.0, 0.0]

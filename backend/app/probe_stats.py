"""Pure statistics helpers shared by the ablation probe scripts."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

from .models import Turn


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _ngrams(text: str, n: int = 4) -> set[tuple[str, ...]]:
    words = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def turn_echo(turn: Turn, earlier: Sequence[Turn]) -> float | None:
    """Fraction of this turn's word 4-grams already used by a DIFFERENT agent in an
    earlier turn. None when the turn has fewer than 4 words (skipped)."""
    grams = _ngrams(" ".join(turn.sentences))
    if not grams:
        return None
    prior: set[tuple[str, ...]] = set()
    for t in earlier:
        if t.agent_id != turn.agent_id:
            prior |= _ngrams(" ".join(t.sentences))
    return len(grams & prior) / len(grams)


def echo_by_round(turns: Sequence[Turn], n_rounds: int) -> list[float]:
    """Mean echo per round index 0..n_rounds-1 (0.0 for rounds with no usable turns)."""
    ordered = sorted(turns, key=lambda t: t.seq)
    out: list[float] = []
    for r in range(n_rounds):
        vals = [
            e
            for t in ordered
            if t.round == r
            for e in [turn_echo(t, [u for u in ordered if u.seq < t.seq])]
            if e is not None
        ]
        out.append(sum(vals) / len(vals) if vals else 0.0)
    return out

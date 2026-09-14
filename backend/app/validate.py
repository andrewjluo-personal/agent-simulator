"""Parse and truncate raw model output. Never raises on bad model output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .models import FactStyle, Scenario
from .truth import UNDECIDED, match_facts

MAX_WORDS = 40
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = _FENCE.sub("", text.strip())
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _clip(sentence: str) -> str:
    words = sentence.split()
    return " ".join(words[:MAX_WORDS])


def _clamp_confidence(value: Any, default: float = 0.5) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, conf))


@dataclass
class ValidatedTurn:
    sentences: list[str] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)
    hallucinated: list[str] = field(default_factory=list)
    lean: str = UNDECIDED
    confidence: float = 0.0


def validate_board(
    raw: dict[str, Any] | None,
    hand: set[str],
    candidate_ids: set[str],
    opinions_allowed: bool,
    *,
    scenario: Scenario,
    fact_style: FactStyle,
) -> ValidatedTurn:
    if raw is None:
        return ValidatedTurn()
    out = ValidatedTurn()
    if fact_style == "labelled":
        items = raw.get("fact_ids")
        seen_ids: set[str] = set()
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, str) or item in seen_ids:
                    continue
                seen_ids.add(item)
                (out.cited if item in hand else out.hallucinated).append(item)
    else:
        facts = raw.get("facts")
        seen_cited: set[str] = set()
        all_facts = scenario.facts
        if isinstance(facts, list):
            for text in facts:
                if not isinstance(text, str):
                    continue
                matched = match_facts([text], all_facts)
                held = [fact_id for fact_id in matched if fact_id in hand]
                for fact_id in held:
                    if fact_id not in seen_cited:
                        seen_cited.add(fact_id)
                        out.cited.append(fact_id)
                if not matched:
                    out.hallucinated.append(f"unmatched:{text[:60]}")
    note = raw.get("note")
    if isinstance(note, str) and note:
        first = re.split(r"(?<=[.!?])\s+", note.strip(), maxsplit=1)[0]
        out.sentences = [_clip(first)]
    lean = raw.get("current_lean")
    out.lean = lean if isinstance(lean, str) and lean in candidate_ids else UNDECIDED
    if not opinions_allowed:
        out.lean = UNDECIDED
    out.confidence = _clamp_confidence(raw.get("confidence"), default=0.5)
    return out


def validate_moderator(
    raw: dict[str, Any] | None, agent_ids: set[str]
) -> tuple[list[str], str | None]:
    if raw is None:
        return [], None
    sentences = raw.get("sentences")
    clipped = [_clip(s) for s in sentences if isinstance(s, str)][:2] if isinstance(sentences, list) else []
    addressed = raw.get("address_agent_id")
    return clipped, addressed if isinstance(addressed, str) and addressed in agent_ids else None


def validate_turn(
    raw: dict[str, Any] | None,
    hand: set[str],
    common_ground: set[str],
    candidate_ids: set[str],
    sentences_per_turn: int,
    opinions_allowed: bool,
    *,
    inferred_cited: list[str] | None = None,
) -> ValidatedTurn:
    if raw is None:
        return ValidatedTurn()
    out = ValidatedTurn()
    sentences = raw.get("sentences")
    if isinstance(sentences, list):
        out.sentences = [_clip(s) for s in sentences if isinstance(s, str)][:sentences_per_turn]
    known = hand | common_ground
    if inferred_cited is not None:
        # memo mode: citations inferred lexically; best-effort, may catch facts the
        # agent neither holds nor has heard
        out.cited = [f for f in inferred_cited if f in known]
        out.hallucinated = [f for f in inferred_cited if f not in known]
    else:
        items = raw.get("items_referenced")
        seen: set[str] = set()
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, str) or item in seen:
                    continue
                seen.add(item)
                (out.cited if item in known else out.hallucinated).append(item)
    lean = raw.get("current_lean")
    out.lean = lean if isinstance(lean, str) and lean in candidate_ids else UNDECIDED
    if not opinions_allowed:
        out.lean = UNDECIDED
    out.confidence = _clamp_confidence(raw.get("confidence"), default=0.5)
    return out


def validate_vote(raw: dict[str, Any] | None, candidate_ids: set[str]) -> tuple[str, float, str]:
    if raw is None:
        return UNDECIDED, 0.0, ""
    vote = raw.get("vote", raw.get("choice"))
    choice = vote if isinstance(vote, str) and vote in candidate_ids else UNDECIDED
    confidence = _clamp_confidence(raw.get("confidence"), default=0.5)
    reason = raw.get("reason")
    return choice, confidence, reason if isinstance(reason, str) else ""

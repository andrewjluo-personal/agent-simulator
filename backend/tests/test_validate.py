from __future__ import annotations

import json

from app.validate import parse_json_object, validate_turn, validate_vote

CANDIDATES = {"john", "sally"}


def test_truncates_sentences_to_limit_and_words() -> None:
    raw = {
        "sentences": [" ".join(["w"] * 50), "short", 42, "another"],
        "items_referenced": [],
        "current_lean": "john",
        "confidence": 0.9,
    }
    vt = validate_turn(raw, set(), set(), CANDIDATES, 2, True)
    assert len(vt.sentences) == 2
    assert len(vt.sentences[0].split()) == 40
    assert vt.sentences[1] == "short"


def test_fenced_json_parses() -> None:
    raw = parse_json_object('```json\n{"sentences": [], "items_referenced": []}\n```')
    assert raw == {"sentences": [], "items_referenced": []}


def test_json_with_prose_around() -> None:
    raw = parse_json_object('here you go {"a": 1} hope that helps')
    assert raw == {"a": 1}
    assert parse_json_object("no json") is None


def test_hallucinated_partition() -> None:
    raw = {
        "sentences": ["s"],
        "items_referenced": ["S1", "X99", "S2", "S1"],
        "current_lean": "sally",
        "confidence": 2.0,
    }
    vt = validate_turn(raw, {"S1"}, {"S2"}, CANDIDATES, 5, True)
    assert vt.cited == ["S1", "S2"]
    assert vt.hallucinated == ["X99"]
    assert vt.lean == "sally"
    assert vt.confidence == 1.0


def test_lean_coerced_when_opinions_not_allowed() -> None:
    raw = {"sentences": [], "items_referenced": [], "current_lean": "john", "confidence": 0.5}
    vt = validate_turn(raw, set(), set(), CANDIDATES, 5, False)
    assert vt.lean == "undecided"


def test_none_raw_gives_placeholder() -> None:
    vt = validate_turn(None, {"S1"}, set(), CANDIDATES, 5, True)
    assert vt.sentences == [] and vt.lean == "undecided" and vt.confidence == 0.0


def test_validate_vote() -> None:
    raw = json.loads('{"vote": "sally", "confidence": 0.7, "reason": "because"}')
    assert validate_vote(raw, CANDIDATES) == ("sally", 0.7, "because")
    assert validate_vote({"vote": "nobody"}, CANDIDATES)[0] == "undecided"
    assert validate_vote(None, CANDIDATES) == ("undecided", 0.0, "")

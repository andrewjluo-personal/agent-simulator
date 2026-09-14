"""Importer-backed HiddenBench scenarios."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models import AgentPersona, Candidate, Fact, Scenario, ScenarioSource

_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "been",
    "being",
    "from",
    "have",
    "into",
    "more",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "under",
    "were",
    "which",
    "with",
}


def _slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", value.lower())


def _distinctive_option_tokens(answer: str) -> list[str]:
    return [
        token
        for token in _tokens(answer)
        if len(token) >= 5 and token not in {"candidate", "option", "choice"}
    ]


def _mentions(text: str, answers: list[str]) -> list[int]:
    lower = text.lower()
    found: list[int] = []
    for index, answer in enumerate(answers):
        if answer.lower() in lower or any(
            token in lower for token in _distinctive_option_tokens(answer)
        ):
            found.append(index)
    return found


def _keywords(text: str, answers: list[str]) -> list[str]:
    words = _tokens(text)
    preferred = {token for answer in answers for token in _distinctive_option_tokens(answer)}
    ordered: list[str] = []
    for token in words:
        if token in _STOPWORDS or token in ordered:
            continue
        if token in preferred or len(token) >= 6:
            ordered.append(token)
    if len(ordered) < 2:
        for token in words:
            if token not in _STOPWORDS and token not in ordered:
                ordered.append(token)
            if len(ordered) >= 2:
                break
    return ordered[:3]


def _candidate_ids(answers: list[str]) -> list[str]:
    ids: list[str] = []
    for index, answer in enumerate(answers, start=1):
        candidate_id = _slug(answer) or f"opt{index}"
        if candidate_id in ids:
            candidate_id = f"opt{index}"
        ids.append(candidate_id)
    return ids


def convert_task(task: dict[str, Any]) -> Scenario:
    answers = [str(answer) for answer in task["possible_answers"]]
    candidate_ids = _candidate_ids(answers)
    correct_index = answers.index(str(task["correct_answer"]))
    flagged: list[str] = []
    facts: list[Fact] = []

    def add_fact(fact_id: str, text: str, hidden: bool) -> None:
        mentions = _mentions(text, answers)
        if hidden:
            wrong_mentions = [index for index in mentions if index != correct_index]
            if wrong_mentions:
                candidate_index = wrong_mentions[0]
                valence = "con"
            else:
                candidate_index = correct_index
                valence = "pro"
            if len(mentions) != 1 or (mentions and mentions[0] == correct_index):
                flagged.append(
                    f"{fact_id}: valence inferred: {valence} for {answers[candidate_index]!r}; "
                    f"option mentions={', '.join(answers[i] for i in mentions) or 'none'}"
                )
        elif len(mentions) == 1:
            candidate_index = mentions[0]
            valence = "pro"
        else:
            candidate_index = correct_index
            valence = "pro"
            flagged.append(
                f"{fact_id}: valence inferred: pro for {answers[candidate_index]!r}; "
                f"shared option mentions={', '.join(answers[i] for i in mentions) or 'none'}"
            )
        facts.append(
            Fact(
                id=fact_id,
                candidate_id=candidate_ids[candidate_index],
                valence=valence,  # type: ignore[arg-type]
                weight=1,
                text=text,
                memo_text=text,
                keywords=_keywords(text, answers),
            )
        )

    for index, text in enumerate(task["shared_information"], start=1):
        add_fact(f"S{index}", str(text), hidden=False)
    for index, text in enumerate(task["hidden_information"], start=1):
        add_fact(f"H{index}", str(text), hidden=True)

    rationale = str(task.get("rationale") or "No rationale was supplied in the benchmark task.")
    notes = (
        f"Converted from HiddenBench task data verbatim. Rationale: {rationale} "
        f"Design uses {len(answers)} candidates, {len(task['hidden_information'])} participants, "
        f"{len(task['shared_information'])} shared facts, and "
        f"{len(task['hidden_information'])} hidden facts ({len(facts)} total). "
        "No human-group result is reported in the supplied benchmark; approx. human result "
        "is not available."
    )
    if flagged:
        notes += " Valence inferred: " + " | ".join(flagged)
    return Scenario(
        id=f"hiddenbench-{_slug(str(task['name']))}",
        title=f"HiddenBench — {str(task['name']).replace('_', ' ').title()}",
        brief=str(task["description"]),
        is_sample=True,
        candidates=[
            Candidate(id=candidate_id, name=answer, blurb="")
            for candidate_id, answer in zip(candidate_ids, answers, strict=True)
        ],
        facts=facts,
        agents=[
            AgentPersona(
                id=f"p{index}",
                name=f"Participant {index}",
                role="community member",
                style="cooperative",
            )
            for index in range(1, len(task["hidden_information"]) + 1)
        ],
        distribution={
            f"p{index}": [
                f"S{shared_index}" for shared_index in range(1, len(task["shared_information"]) + 1)
            ]
            + [f"H{index}"]
            for index in range(1, len(task["hidden_information"]) + 1)
        },
        source=ScenarioSource(
            kind="paper",
            paper="HiddenBench (Yassellee et al., 2025)",
            doi_or_url="https://github.com/yassellee/HiddenBench",
            fidelity="verbatim",
            notes=notes,
        ),
    )


_DATA_PATH = Path(__file__).with_name("hiddenbench_data.json")
HIDDENBENCH_SCENARIOS: list[Scenario] = []
if _DATA_PATH.exists():
    HIDDENBENCH_SCENARIOS = [
        Scenario.model_validate(item) for item in json.loads(_DATA_PATH.read_text())
    ]

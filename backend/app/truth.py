"""Ground-truth scoring over a scenario's fact distribution. Pure functions."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from .models import Fact, Scenario

UNDECIDED = "undecided"


def _signed_weight(scenario: Scenario, fact_id: str) -> tuple[str, int]:
    fact = scenario.fact(fact_id)
    return fact.candidate_id, fact.weight if fact.valence == "pro" else -fact.weight


def scores(scenario: Scenario, fact_ids: Iterable[str]) -> dict[str, int]:
    totals = {c.id: 0 for c in scenario.candidates}
    for fact_id in set(fact_ids):
        candidate_id, signed = _signed_weight(scenario, fact_id)
        totals[candidate_id] += signed
    return totals


def verdict(scenario: Scenario, fact_ids: Iterable[str]) -> str:
    totals = scores(scenario, fact_ids)
    best = max(totals.values()) if totals else 0
    winners = [cid for cid, total in totals.items() if total == best]
    return winners[0] if len(winners) == 1 else UNDECIDED


def holders(scenario: Scenario, fact_id: str) -> list[str]:
    return [agent_id for agent_id, held in scenario.distribution.items() if fact_id in held]


def shared_fact_ids(scenario: Scenario) -> set[str]:
    return {f.id for f in scenario.facts if len(holders(scenario, f.id)) == len(scenario.agents)}


def unique_fact_ids(scenario: Scenario) -> set[str]:
    return {f.id for f in scenario.facts if len(holders(scenario, f.id)) == 1}


def pooled_fact_ids(scenario: Scenario) -> set[str]:
    pooled: set[str] = set()
    for held in scenario.distribution.values():
        pooled.update(held)
    return pooled


def pooled_verdict(scenario: Scenario) -> str:
    return verdict(scenario, pooled_fact_ids(scenario))


def shared_only_verdict(scenario: Scenario) -> str:
    return verdict(scenario, shared_fact_ids(scenario))


def alone_votes(scenario: Scenario) -> dict[str, str]:
    return {agent_id: verdict(scenario, held) for agent_id, held in scenario.distribution.items()}


def decisive_fact_ids(scenario: Scenario) -> set[str]:
    """Unique facts that favor the pooled-correct candidate."""
    correct = pooled_verdict(scenario)
    if correct == UNDECIDED:
        return set()
    out: set[str] = set()
    for fact_id in unique_fact_ids(scenario):
        fact = scenario.fact(fact_id)
        if (fact.valence == "pro") == (fact.candidate_id == correct):
            out.add(fact_id)
    return out


def is_hidden_profile(scenario: Scenario) -> bool:
    pooled = pooled_verdict(scenario)
    return pooled != UNDECIDED and shared_only_verdict(scenario) != pooled


STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "with",
    "is",
    "was",
    "were",
    "be",
    "has",
    "have",
    "had",
    "that",
    "this",
    "it",
    "its",
    "her",
    "his",
    "she",
    "he",
    "they",
    "their",
    "our",
    "we",
    "you",
    "i",
    "not",
    "no",
    "but",
    "as",
    "by",
    "from",
    "about",
    "which",
    "who",
    "than",
    "then",
    "so",
    "very",
    "also",
    "said",
    "says",
}


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > 4 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> list[str]:
    """Normalised content tokens: lowercase, punctuation stripped, stopwords and
    crude suffixes removed."""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return [_stem(t) for t in cleaned.split() if t not in STOPWORDS]


def _contains_subseq(haystack: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    return any(
        haystack[i : i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1)
    )


def match_facts(sentences: list[str], facts: Iterable[Fact]) -> list[str]:
    """Infer which facts a set of sentences refers to, without ids (memo mode).
    Deterministic lexical matching: primary signal = any fact keyword present as a
    token/phrase in a normalised sentence; secondary = content-word overlap between the
    sentence and `memo_text or text` (>= 3 shared content words, or Jaccard >= 0.25).
    Returns fact ids in `facts` order, deduplicated. Best-effort; paraphrases that
    share no keywords or content words will be missed."""
    fact_list = list(facts)
    sent_tokens = _tokens(" ".join(sentences))
    sent_set = set(sent_tokens)
    out: list[str] = []
    for fact in fact_list:
        matched = any(_contains_subseq(sent_tokens, _tokens(keyword)) for keyword in fact.keywords)
        if not matched:
            fact_set = set(_tokens(fact.memo_text or fact.text))
            shared = sent_set & fact_set
            union = sent_set | fact_set
            matched = len(shared) >= 3 or (bool(union) and len(shared) / len(union) >= 0.25)
        if matched:
            out.append(fact.id)
    return out


def _majority(choices: Iterable[str]) -> str:
    tally = Counter(c for c in choices if c != UNDECIDED)
    if not tally:
        return UNDECIDED
    best = max(tally.values())
    winners = [cid for cid, n in tally.items() if n == best]
    return winners[0] if len(winners) == 1 else UNDECIDED


def majority(choices: Iterable[str], *, chair_choice: str | None = None) -> str:
    """Plurality winner; on a tie the chair's ballot decides outright."""
    tally = Counter(c for c in choices if c != UNDECIDED)
    if not tally:
        return UNDECIDED
    best = max(tally.values())
    winners = [cid for cid, n in tally.items() if n == best]
    if len(winners) == 1:
        return winners[0]
    if chair_choice and chair_choice != UNDECIDED:
        return chair_choice
    return UNDECIDED

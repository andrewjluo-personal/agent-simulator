"""Sample scenarios, backend-owned. Seeded into the store so users can select
and reset them; user edits live in the DB, samples only fill in missing rows.

Every sample is a Stasser-style item pool: ~40 neutral attribute items with small
weights. The shared set favours the wrong candidate; the unique set, pooled,
favours the right one by a modest margin. Valence/weight never appear in prompts.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from . import scenario_gen
from .models import Scenario
from .scenarios.papers import PAPER_SCENARIOS

if TYPE_CHECKING:
    from .store import Store


def _fact(
    fact_id: str,
    candidate_id: str,
    valence: str,
    weight: int,
    text: str,
    memo_text: str,
    keywords: list[str],
) -> dict[str, Any]:
    return {
        "id": fact_id,
        "candidateId": candidate_id,
        "valence": valence,
        "weight": weight,
        "text": text,
        "memoText": memo_text,
        "keywords": keywords,
    }


# ---------------------------------------------------------------------------
# hiring-panel-v1 — John (shared favourite) vs Sally (pooled favourite), 5 agents
# ---------------------------------------------------------------------------
HIRING_PANEL_AGENTS: list[dict[str, str]] = [
    {
        "id": "dana",
        "name": "Dana",
        "role": "Hiring manager",
        "style": "direct and decisive; wants to close the loop",
    },
    {
        "id": "marcus",
        "name": "Marcus",
        "role": "Staff engineer",
        "style": "precise, evidence-first, dislikes vibes",
    },
    {
        "id": "priya",
        "name": "Priya",
        "role": "Recruiter",
        "style": "warm, focused on references and team fit",
    },
    {
        "id": "tom",
        "name": "Tom",
        "role": "QA lead",
        "style": "skeptical, asks what could go wrong",
    },
    {
        "id": "omar",
        "name": "Omar",
        "role": "Peer engineer",
        "style": "collegial, detail-oriented",
    },
]

HIRING_PANEL_CANDIDATES: list[dict[str, str]] = [
    {
        "id": "john",
        "name": "John",
        "blurb": "Eight years of Go; currently a team lead at a payments company",
    },
    {
        "id": "sally",
        "name": "Sally",
        "blurb": "Six years of Python and Java backend work on data platforms",
    },
]

# Shared items (held by every panelist): John's positives, Sally's negatives, filler.
_HP_SHARED: list[dict[str, Any]] = [
    _fact(
        "J1",
        "john",
        "pro",
        1,
        "John answered every behavioural question in the panel round without pausing and kept each answer under two minutes.",
        "Answered all behavioural questions fluently and concisely.",
        ["behavioural", "fluent", "two minutes"],
    ),
    _fact(
        "J2",
        "john",
        "pro",
        2,
        "John has eight years of professional Go, which is the team's primary backend language.",
        "Eight years of professional Go.",
        ["eight years", "Go", "primary language"],
    ),
    _fact(
        "J3",
        "john",
        "pro",
        1,
        "John's CV lists him as team lead for six engineers at his current employer.",
        "Listed as team lead for six engineers.",
        ["team lead", "six engineers"],
    ),
    _fact(
        "J4",
        "john",
        "pro",
        1,
        "John's current employer is a payments company most of the panel has heard of.",
        "Current employer is a well-known payments company.",
        ["payments company", "employer", "brand"],
    ),
    _fact(
        "J5",
        "john",
        "pro",
        1,
        "John submitted the take-home within a day; the code follows standard Go project layout.",
        "Take-home submitted within a day; standard Go layout.",
        ["take-home", "within a day", "layout"],
    ),
    _fact(
        "J6",
        "john",
        "pro",
        1,
        "John used payments vocabulary (settlement, chargeback, reconciliation) correctly throughout the loop.",
        "Used payments domain vocabulary correctly.",
        ["vocabulary", "settlement", "reconciliation"],
    ),
    _fact(
        "J7",
        "john",
        "pro",
        1,
        "John is available to start in two weeks.",
        "Available to start in two weeks.",
        ["available", "two weeks", "start date"],
    ),
    _fact(
        "J8",
        "john",
        "pro",
        1,
        "John holds a current AWS Solutions Architect certification.",
        "Holds an AWS Solutions Architect certification.",
        ["AWS", "certification", "solutions architect"],
    ),
    _fact(
        "J9",
        "john",
        "con",
        1,
        "John's take-home README omits setup and run instructions.",
        "Take-home README omits setup instructions.",
        ["README", "setup instructions", "take-home"],
    ),
    _fact(
        "J10",
        "john",
        "con",
        1,
        "In the closing round John asked about title and compensation and did not ask about the product.",
        "Closing questions were about title and compensation only.",
        ["closing round", "title", "compensation"],
    ),
    _fact(
        "J11",
        "john",
        "con",
        1,
        "John's compensation ask is at the top of the posted band.",
        "Compensation ask at the top of the band.",
        ["compensation", "top of band", "ask"],
    ),
    _fact(
        "S1",
        "sally",
        "pro",
        1,
        "Sally's written design sample is organised into numbered sections with a stated assumptions list.",
        "Design sample is organised with numbered sections and stated assumptions.",
        ["design sample", "numbered sections", "assumptions"],
    ),
    _fact(
        "S2",
        "sally",
        "pro",
        1,
        "Sally has six years of backend work in Python and Java on data platforms.",
        "Six years of Python and Java backend work.",
        ["six years", "Python", "Java"],
    ),
    _fact(
        "S3",
        "sally",
        "pro",
        1,
        "Sally maintains an open-source Postgres migration tool with a few hundred GitHub stars.",
        "Maintains an open-source Postgres migration tool.",
        ["open-source", "Postgres", "migration tool"],
    ),
    _fact(
        "S4",
        "sally",
        "pro",
        1,
        "In the closing round Sally asked about the on-call rotation and the team's last three incidents.",
        "Closing questions were about on-call and recent incidents.",
        ["closing round", "on-call", "incidents"],
    ),
    _fact(
        "S5",
        "sally",
        "con",
        2,
        "Sally has not written Go professionally; the team's services are in Go.",
        "No professional Go experience.",
        ["no Go", "Go experience", "primary language"],
    ),
    _fact(
        "S6",
        "sally",
        "con",
        2,
        "Sally paused for several seconds before two panel answers and asked to restart one of them.",
        "Paused before two panel answers and restarted one.",
        ["paused", "restart", "panel answers"],
    ),
    _fact(
        "S7",
        "sally",
        "con",
        1,
        "Sally's most recent role lasted 14 months.",
        "Most recent tenure was 14 months.",
        ["14 months", "tenure", "recent role"],
    ),
    _fact(
        "S8",
        "sally",
        "con",
        1,
        "Sally has had no direct reports and no formal lead title.",
        "No direct reports or formal lead title.",
        ["no direct reports", "lead title", "management"],
    ),
    _fact(
        "S9",
        "sally",
        "con",
        1,
        "Sally asked to work in an editor rather than on the whiteboard for the coding round.",
        "Asked to use an editor instead of the whiteboard.",
        ["editor", "whiteboard", "coding round"],
    ),
    _fact(
        "S10",
        "sally",
        "con",
        1,
        "Sally submitted the take-home about an hour before the deadline.",
        "Take-home submitted an hour before the deadline.",
        ["take-home", "deadline", "an hour before"],
    ),
    _fact(
        "S11",
        "sally",
        "con",
        1,
        "Sally's background is in logistics data platforms rather than payments.",
        "Background in logistics data platforms, not payments.",
        ["logistics", "background", "payments"],
    ),
]

# Unique decisive items (Sally positives, John negatives) — held by one agent each.
_HP_DECISIVE: list[dict[str, Any]] = [
    _fact(
        "S12",
        "sally",
        "pro",
        2,
        "At her last company Sally was the named lead on a ledger migration that moved 2B rows with no recorded downtime.",
        "Named lead on a 2B-row ledger migration with no recorded downtime.",
        ["ledger migration", "2B rows", "no downtime"],
    ),
    _fact(
        "S13",
        "sally",
        "pro",
        2,
        "In the debugging round Sally located a race condition causing silent data loss in the sample service in 18 minutes.",
        "Located a silent data-loss race condition in the debugging round in 18 minutes.",
        ["race condition", "data loss", "18 minutes"],
    ),
    _fact(
        "S14",
        "sally",
        "pro",
        2,
        "Sally's design answer covered the double-spend case and proposed idempotency keys before the interviewer raised it.",
        "Covered the double-spend case with idempotency keys unprompted.",
        ["double-spend", "idempotency keys", "design answer"],
    ),
    _fact(
        "S15",
        "sally",
        "pro",
        2,
        "Four engineers Sally mentored were promoted within two years; two now lead teams.",
        "Four mentees promoted within two years; two now lead teams.",
        ["mentored", "promoted", "lead teams"],
    ),
    _fact(
        "S16",
        "sally",
        "pro",
        1,
        "A post-mortem template Sally wrote was adopted across her previous org's engineering group.",
        "Wrote a post-mortem template adopted org-wide.",
        ["post-mortem", "template", "adopted"],
    ),
    _fact(
        "S17",
        "sally",
        "pro",
        1,
        "Sally reduced batch settlement infrastructure cost by 40% by rewriting the job, and documented the approach.",
        "Cut batch settlement infrastructure cost 40% and documented it.",
        ["40%", "settlement job", "cost"],
    ),
    _fact(
        "S18",
        "sally",
        "pro",
        1,
        "Sally's former skip-level manager said she would hire Sally first for an under-specified problem.",
        "Former skip-level would hire her first for an under-specified problem.",
        ["skip-level", "reference", "under-specified"],
    ),
    _fact(
        "J12",
        "john",
        "con",
        2,
        "A back-channel reference says three of John's six reports left within a year; two named John in exit interviews.",
        "Three of six reports left within a year; two named him in exit interviews.",
        ["reports left", "exit interviews", "back-channel"],
    ),
    _fact(
        "J13",
        "john",
        "con",
        2,
        "John's take-home matches a public blog post solution, including variable names and an unusual comment.",
        "Take-home matches a public blog post, including variable names and a comment.",
        ["blog post", "take-home", "variable names"],
    ),
    _fact(
        "J14",
        "john",
        "con",
        2,
        "A former colleague says John was one of twelve contributors on the platform migration he described as leading.",
        "Colleague describes him as one of twelve contributors on the migration he said he led.",
        ["twelve contributors", "migration", "led"],
    ),
    _fact(
        "J15",
        "john",
        "con",
        2,
        "John interrupted the QA engineer twice during the panel and did not return to their question.",
        "Interrupted the QA engineer twice and did not return to the question.",
        ["interrupted", "QA engineer", "question"],
    ),
    _fact(
        "J16",
        "john",
        "con",
        1,
        "Asked about an outage on his service, John said it was not his; the public post-mortem lists him as owner.",
        "Said an outage on his service was not his; the post-mortem lists him as owner.",
        ["outage", "post-mortem", "owner"],
    ),
]

# Unique counter items (favour the shared-only verdict) — one per agent.
_HP_COUNTER: list[dict[str, Any]] = [
    _fact(
        "J17",
        "john",
        "pro",
        1,
        "John's former manager says he has met every delivery date they set together.",
        "Former manager reports he has met every delivery date.",
        ["delivery dates", "former manager", "reference"],
    ),
    _fact(
        "J18",
        "john",
        "pro",
        1,
        "John has given two conference talks on Go service architecture.",
        "Two conference talks on Go service architecture.",
        ["conference talks", "Go", "architecture"],
    ),
    _fact(
        "J19",
        "john",
        "pro",
        1,
        "John finished the live coding exercise with ten minutes to spare.",
        "Finished the live coding exercise early.",
        ["live coding", "ten minutes", "finished early"],
    ),
    _fact(
        "S19",
        "sally",
        "con",
        1,
        "One edge-case test in Sally's take-home fails; her notes flag it as known.",
        "One take-home edge-case test fails; flagged as known in her notes.",
        ["edge-case", "failing test", "take-home"],
    ),
    _fact(
        "S20",
        "sally",
        "con",
        1,
        "Sally estimated three months to become productive in Go.",
        "Estimates three months to become productive in Go.",
        ["three months", "Go", "ramp-up"],
    ),
]

_HP_SHARED_IDS = [f["id"] for f in _HP_SHARED]

HIRING_PANEL_V1 = Scenario.model_validate(
    {
        "id": "hiring-panel-v1",
        "title": "Senior Backend Engineer: John vs. Sally",
        "brief": "The panel must recommend exactly one candidate for a senior backend role on a payments team. Each panelist attended different parts of the interview loop and holds different evidence.",
        "isSample": True,
        "candidates": HIRING_PANEL_CANDIDATES,
        "agents": HIRING_PANEL_AGENTS,
        "facts": _HP_SHARED + _HP_DECISIVE + _HP_COUNTER,
        "distribution": {
            "dana": _HP_SHARED_IDS + ["S12", "S14", "J16", "J17"],
            "marcus": _HP_SHARED_IDS + ["S13", "S15", "J15", "J18"],
            "priya": _HP_SHARED_IDS + ["S16", "J12", "J19"],
            "tom": _HP_SHARED_IDS + ["S18", "J13", "S19"],
            "omar": _HP_SHARED_IDS + ["S17", "J14", "S20"],
        },
        "validation": {
            "claude-haiku-4-5": {
                "aloneWrongRate": {
                    "dana": 1.0,
                    "marcus": 1.0,
                    "priya": 1.0,
                    "tom": 1.0,
                    "omar": 1.0,
                },
                "pooledRightRate": 1.0,
                "trials": 10,
                "date": "2026-09-13",
                "passed": True,
                "freeDiscussionRate": 1.0,
                "freeDiscussionRuns": 10,
            }
        },
    }
)

FLAT_DECISIVE: list[dict[str, Any]] = [
    _fact(
        "F1",
        "sally",
        "pro",
        1,
        "Sally has taken part in two cross-team incident reviews at her current company.",
        "Took part in two cross-team incident reviews.",
        ["incident reviews", "cross-team", "took part"],
    ),
    _fact(
        "F2",
        "sally",
        "pro",
        1,
        "One other team at Sally's company has adopted her migration tool.",
        "One other team has adopted her migration tool.",
        ["migration tool", "one other team", "adopted"],
    ),
    _fact(
        "F3",
        "sally",
        "pro",
        1,
        "In the debugging round Sally found the planted bug within the allotted time.",
        "Found the planted bug in the debugging round within the allotted time.",
        ["debugging round", "planted bug", "allotted time"],
    ),
    _fact(
        "F4",
        "sally",
        "pro",
        1,
        "Sally's design answer included a short section on logging and metrics.",
        "Design answer included a short section on logging and metrics.",
        ["logging", "metrics", "design answer"],
    ),
    _fact(
        "F5",
        "sally",
        "pro",
        1,
        "One engineer Sally mentored has since been promoted.",
        "One mentee has since been promoted.",
        ["mentored", "promoted", "one engineer"],
    ),
    _fact(
        "F6",
        "sally",
        "pro",
        1,
        "Sally has contributed several pages to her team's on-call runbook.",
        "Has contributed pages to her team's on-call runbook.",
        ["on-call", "runbook", "contributed"],
    ),
    _fact(
        "F7",
        "sally",
        "pro",
        1,
        "A former skip-level manager described Sally as dependable.",
        "Former skip-level describes her as dependable.",
        ["skip-level", "reference", "dependable"],
    ),
    _fact(
        "F8",
        "sally",
        "pro",
        1,
        "Sally has a small Go side project on GitHub with recent commits.",
        "Has a small Go side project with recent commits.",
        ["Go", "side project", "GitHub"],
    ),
    _fact(
        "G1",
        "john",
        "con",
        1,
        "Two of John's six reports left the team within the last year.",
        "Two of six reports left within the last year.",
        ["reports left", "attrition", "last year"],
    ),
    _fact(
        "G2",
        "john",
        "con",
        1,
        "The platform migration John described leading listed eleven other contributors.",
        "The migration he described leading had eleven other contributors.",
        ["migration", "eleven contributors", "led"],
    ),
    _fact(
        "G3",
        "john",
        "con",
        1,
        "When asked about his on-call experience, John answered about team process instead.",
        "Answered a question about his on-call experience with team process.",
        ["on-call", "answered indirectly", "team process"],
    ),
    _fact(
        "G4",
        "john",
        "con",
        1,
        "One of John's last two roles lasted under 18 months.",
        "One of his last two roles lasted under 18 months.",
        ["18 months", "tenure", "one role"],
    ),
    _fact(
        "G5",
        "john",
        "con",
        1,
        "John started answering before the QA engineer had finished one question.",
        "Started answering before the QA engineer finished one question.",
        ["started answering", "QA engineer", "question"],
    ),
    _fact(
        "G6",
        "john",
        "con",
        1,
        "John's former manager described him as a strong individual contributor who is still growing as a lead.",
        "Former manager: strong individual contributor, still growing as a lead.",
        ["former manager", "individual contributor", "growing as a lead"],
    ),
]

FLAT_SHARED: list[dict[str, Any]] = [
    {**fact, "weight": 1} if fact["id"] == "S6" else fact
    for fact in _HP_SHARED
    if fact["id"] not in ("J8", "S9")
]
FLAT_SHARED_IDS = [fact["id"] for fact in FLAT_SHARED]

FLAT_COUNTER: list[dict[str, Any]] = [
    _fact(
        "J17",
        "john",
        "pro",
        1,
        "John's former manager says he has met every delivery date they set together.",
        "Former manager reports he has met every delivery date.",
        ["delivery dates", "former manager", "reference"],
    ),
    _fact(
        "J18",
        "john",
        "pro",
        1,
        "John has given two conference talks on Go service architecture.",
        "Two conference talks on Go service architecture.",
        ["conference talks", "Go", "architecture"],
    ),
    _fact(
        "S20",
        "sally",
        "con",
        1,
        "Sally estimated three months to become productive in Go.",
        "Estimates three months to become productive in Go.",
        ["three months", "Go", "ramp-up"],
    ),
]

HIRING_PANEL_FLAT = Scenario.model_validate(
    {
        "id": "hiring-panel-flat",
        "title": "Hiring panel (flat items)",
        "brief": HIRING_PANEL_V1.brief,
        "isSample": True,
        "candidates": HIRING_PANEL_CANDIDATES,
        "agents": HIRING_PANEL_AGENTS,
        "facts": FLAT_SHARED + FLAT_DECISIVE + FLAT_COUNTER,
        "distribution": {
            "dana": FLAT_SHARED_IDS + ["F1", "F5", "G1", "J17"],
            "marcus": FLAT_SHARED_IDS + ["F2", "F6", "G2", "J18"],
            "priya": FLAT_SHARED_IDS + ["F3", "F7", "G3"],
            "tom": FLAT_SHARED_IDS + ["F4", "F8", "G4"],
            "omar": FLAT_SHARED_IDS + ["G5", "G6", "S20"],
        },
        "validation": {},
    }
)


def _facts(rows: list[tuple[str, str, str, int, str, str, list[str]]]) -> list[dict[str, Any]]:
    return [_fact(*row) for row in rows]


# Flat pool rebuilt against Haiku's *perceived* item valences (docs/probes/S1_report.md):
# S10 (perceived +1 for Sally) replaced; F4 and G2/G3/G6 (perceived ~0) dropped; J17/J18/S20
# counters dropped; small Sally uniques added so the perceived pooled margin clears the noise
# floor while every hand still favours John on shared items.
_FLAT_V2_S10 = _fact(
    "S10",
    "sally",
    "con",
    1,
    "Sally submitted her take-home twenty minutes after the deadline.",
    "Take-home submitted twenty minutes after the deadline.",
    ["take-home", "after the deadline", "twenty minutes"],
)
FLAT_V2_SHARED: list[dict[str, Any]] = [
    _FLAT_V2_S10 if fact["id"] == "S10" else fact for fact in FLAT_SHARED
]
FLAT_V2_SHARED_IDS = [fact["id"] for fact in FLAT_V2_SHARED]
_FLAT_V2_KEEP = {"F1", "F2", "F3", "F5", "F6", "F7", "F8", "G1", "G4", "G5"}
FLAT_V2_UNIQUE: list[dict[str, Any]] = [
    fact for fact in FLAT_DECISIVE if fact["id"] in _FLAT_V2_KEEP
] + _facts(
    [
        (
            "F9",
            "sally",
            "pro",
            1,
            "Sally's take-home included a load-test script and its results for the hot path.",
            "Her take-home included a load-test script and results for the hot path.",
            ["load-test", "take-home", "hot path"],
        ),
        (
            "F10",
            "sally",
            "pro",
            1,
            "At a previous job Sally rolled back a bad deploy within ten minutes using a runbook she wrote.",
            "Rolled back a bad deploy within ten minutes using a runbook she wrote.",
            ["rolled back", "ten minutes", "runbook"],
        ),
        (
            "F11",
            "sally",
            "pro",
            1,
            "Sally's design sample called out the idempotency of retries explicitly.",
            "Her design sample called out the idempotency of retries explicitly.",
            ["idempotency", "retries", "design sample"],
        ),
        (
            "F12",
            "sally",
            "pro",
            1,
            "A reference says Sally volunteered to own the least popular service on her team.",
            "Reference: she volunteered to own the least popular service on the team.",
            ["volunteered", "least popular service", "reference"],
        ),
        (
            "F13",
            "sally",
            "pro",
            1,
            "Sally has run her team's weekly incident review meeting for the past year.",
            "Has run her team's weekly incident review for the past year.",
            ["incident review", "weekly", "past year"],
        ),
        (
            "F14",
            "sally",
            "pro",
            1,
            "Sally wrote the onboarding guide that new hires on her team still use.",
            "Wrote the onboarding guide new hires on her team still use.",
            ["onboarding guide", "new hires", "wrote"],
        ),
        (
            "F15",
            "sally",
            "pro",
            1,
            "In the debugging round Sally added a regression test before fixing the bug.",
            "Added a regression test before fixing the bug in the debugging round.",
            ["regression test", "debugging round", "before fixing"],
        ),
        (
            "G7",
            "john",
            "con",
            1,
            "John's take-home has no tests.",
            "His take-home has no tests.",
            ["take-home", "no tests"],
        ),
        (
            "G8",
            "john",
            "con",
            1,
            "John could not explain why he chose the concurrency model in his take-home.",
            "Could not explain why he chose the concurrency model in his take-home.",
            ["concurrency model", "could not explain", "take-home"],
        ),
    ]
)

_NULL_SWAP = {
    "John": "Sally",
    "Sally": "John",
    "John's": "Sally's",
    "Sally's": "John's",
    "his": "her",
    "her": "his",
    "he": "she",
    "she": "he",
    "him": "her",
    "His": "Her",
    "Her": "His",
    "He": "She",
    "She": "He",
}
_NULL_SWAP_PAT = re.compile(r"\b(" + "|".join(re.escape(k) for k in _NULL_SWAP) + r")\b")
# Domain-specific items whose twin would contradict the other candidate's profile
# (Go / payments / language background).
_NULL_EXCLUDE = {"J2", "J4", "J6", "S2", "S5", "S11", "F8"}


def _null_swap(s: str) -> str:
    return _NULL_SWAP_PAT.sub(lambda m: _NULL_SWAP[m.group(1)], s)


def _null_twin(fact: dict[str, Any]) -> dict[str, Any]:
    other = "sally" if fact["candidateId"] == "john" else "john"
    return {
        **fact,
        "id": fact["id"] + "x",
        "candidateId": other,
        "valence": "neutral",
        "text": _null_swap(fact["text"]),
        "memoText": _null_swap(fact["memoText"]),
    }


def _null_pool(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every coherent item appears once for each candidate (pronouns swapped), all
    valences neutral: designed and perceived margins are 0 by construction, so the
    Sally rate on this pool is the raw name/order bias."""
    out: list[dict[str, Any]] = []
    for fact in facts:
        if fact["id"] in _NULL_EXCLUDE:
            continue
        out.append({**fact, "valence": "neutral"})
        out.append(_null_twin(fact))
    return out


NULL_SHARED = _null_pool(FLAT_V2_SHARED)
NULL_UNIQUE = _null_pool(FLAT_V2_UNIQUE)
NULL_SHARED_IDS = [fact["id"] for fact in NULL_SHARED]


def _null_hand(ids: list[str]) -> list[str]:
    return (
        NULL_SHARED_IDS
        + [i for i in ids if i not in _NULL_EXCLUDE]
        + [i + "x" for i in ids if i not in _NULL_EXCLUDE]
    )


HIRING_PANEL_NULL_CANDIDATES = [
    {
        "id": "john",
        "name": "John",
        "blurb": "Seven years of backend engineering; currently a senior engineer on a platform team",
    },
    {
        "id": "sally",
        "name": "Sally",
        "blurb": "Seven years of backend engineering; currently a senior engineer on a platform team",
    },
]

HIRING_PANEL_NULL = Scenario.model_validate(
    {
        "id": "hiring-panel-null",
        "title": "Hiring panel (null: symmetric items, zero margin)",
        "brief": "The panel must recommend exactly one candidate for a senior backend engineer role. Each panelist attended different parts of the interview loop and holds different evidence.",
        "isSample": True,
        "candidates": HIRING_PANEL_NULL_CANDIDATES,
        "agents": HIRING_PANEL_AGENTS,
        "facts": NULL_SHARED + NULL_UNIQUE,
        "distribution": {
            "dana": _null_hand(["F1", "F5", "F9", "G1"]),
            "marcus": _null_hand(["F2", "F6", "F10", "G4"]),
            "priya": _null_hand(["F3", "F7", "F11", "G5"]),
            "tom": _null_hand(["F12", "F13", "G7"]),
            "omar": _null_hand(["F14", "F15", "G8"]),
        },
        "validation": {},
    }
)

HIRING_PANEL_FLAT_V2 = Scenario.model_validate(
    {
        "id": "hiring-panel-flat-v2",
        "title": "Hiring panel (flat items, perceived-calibrated)",
        "brief": HIRING_PANEL_V1.brief,
        "isSample": True,
        "candidates": HIRING_PANEL_CANDIDATES,
        "agents": HIRING_PANEL_AGENTS,
        "facts": FLAT_V2_SHARED + FLAT_V2_UNIQUE,
        "distribution": {
            "dana": FLAT_V2_SHARED_IDS + ["F1", "F5", "F9", "G1"],
            "marcus": FLAT_V2_SHARED_IDS + ["F2", "F6", "F10", "G4"],
            "priya": FLAT_V2_SHARED_IDS + ["F3", "F7", "F11", "G5"],
            "tom": FLAT_V2_SHARED_IDS + ["F8", "F12", "F13", "G7"],
            "omar": FLAT_V2_SHARED_IDS + ["F14", "F15", "G8"],
        },
        # Gate results from docs/probes/S1_report.md §5 (claude-haiku-4-5, 10
        # trials, default prompt): pooled reviewer Sally 10/10; each agent alone
        # picks the shared-only candidate John 10/10. Naive prompt also passes
        # (pooled 10/10; alone 10, 10, 10, 8, 10).
        "validation": {
            "claude-haiku-4-5": {
                "aloneWrongRate": {
                    "dana": 1.0,
                    "marcus": 1.0,
                    "priya": 1.0,
                    "tom": 1.0,
                    "omar": 1.0,
                },
                "pooledRightRate": 1.0,
                "trials": 10,
                "date": "2026-09-14",
                "passed": True,
            }
        },
    }
)


def _haiku(
    agent_ids: list[str], pooled: float, passed: bool, *, alone: dict[str, float] | None = None
) -> dict[str, Any]:
    return {
        "claude-haiku-4-5": {
            "aloneWrongRate": {a: (alone or {}).get(a, 1.0) for a in agent_ids},
            "pooledRightRate": pooled,
            "trials": 10,
            "date": "2026-09-13",
            "passed": passed,
        }
    }


def _ids(facts: list[dict[str, Any]]) -> list[str]:
    return [f["id"] for f in facts]


# ---------------------------------------------------------------------------
# incident-review-v1 — deploy (shared favourite) vs ledger pool (pooled favourite)

_IR_SHARED = _facts(
    [
        (
            "D1",
            "deploy",
            "pro",
            2,
            "Error rate first crossed the alert threshold nine minutes after the config deploy reached 40% of the fleet.",
            "Errors crossed the alert threshold nine minutes after the deploy reached 40% of the fleet",
            ["nine minutes", "40%", "threshold"],
        ),
        (
            "D2",
            "deploy",
            "pro",
            2,
            "The deploy changed files under the namespace that holds database connection settings.",
            "Deploy changed files under the database connection-settings namespace",
            ["namespace", "connection settings"],
        ),
        (
            "D3",
            "deploy",
            "pro",
            1,
            "The deploy dashboard shows error rate rising as rollout percentage increased.",
            "Error rate rose as rollout percentage increased",
            ["rollout percentage", "dashboard"],
        ),
        (
            "D4",
            "deploy",
            "pro",
            1,
            "The deploy shipped during a scheduled change-freeze window.",
            "Deploy shipped during a change-freeze window",
            ["change freeze", "window"],
        ),
        (
            "D5",
            "deploy",
            "pro",
            1,
            "Two other services that took the same deploy logged elevated error rates for several minutes.",
            "Two other services on the same deploy logged elevated errors",
            ["other services", "elevated"],
        ),
        (
            "D6",
            "deploy",
            "pro",
            1,
            "The deploy author noted in the pull request that the change bundled two unrelated edits.",
            "PR notes say the change bundled two unrelated edits",
            ["pull request", "bundled"],
        ),
        (
            "D7",
            "deploy",
            "pro",
            1,
            "Regions that received the deploy first also reported the first customer tickets.",
            "First-deployed regions reported the first customer tickets",
            ["regions", "first tickets"],
        ),
        (
            "D8",
            "deploy",
            "pro",
            1,
            "An outage on this service eight months ago was initially attributed to a deploy.",
            "Outage eight months ago was initially attributed to a deploy",
            ["eight months", "attributed"],
        ),
        (
            "D9",
            "deploy",
            "con",
            1,
            "The deploy passed canary and staged-rollout health checks.",
            "Deploy passed canary and staged-rollout health checks",
            ["canary", "health checks"],
        ),
        (
            "D10",
            "deploy",
            "con",
            1,
            "The deploy pipeline's automatic rollback fired at 10:05.",
            "Automatic rollback fired at 10:05",
            ["rollback", "10:05"],
        ),
        (
            "D11",
            "deploy",
            "con",
            1,
            "The same deploy had run in staging for two days without error alerts.",
            "Same deploy ran in staging for two days without alerts",
            ["staging", "two days"],
        ),
        (
            "D12",
            "deploy",
            "con",
            1,
            "The deploy's diff was 14 lines across two files.",
            "Diff was 14 lines across two files",
            ["diff", "14 lines"],
        ),
        (
            "P1",
            "pool",
            "pro",
            1,
            "The ledger database's connection pool reached its configured maximum during the incident.",
            "Ledger connection pool reached its configured maximum during the incident",
            ["pool", "maximum"],
        ),
        (
            "P2",
            "pool",
            "pro",
            1,
            "Request latency to the ledger database rose during the incident window.",
            "Latency to the ledger database rose during the incident",
            ["latency", "ledger"],
        ),
        (
            "P3",
            "pool",
            "pro",
            1,
            "Pool wait-queue depth was above zero for most of the incident.",
            "Pool wait-queue depth was above zero for most of the incident",
            ["wait queue", "depth"],
        ),
        (
            "P4",
            "pool",
            "pro",
            1,
            "The ledger database is shared by three services.",
            "Ledger database is shared by three services",
            ["shared", "three services"],
        ),
        (
            "P5",
            "pool",
            "con",
            2,
            "Ledger database CPU and disk metrics stayed within normal range throughout.",
            "Ledger CPU and disk metrics stayed within normal range",
            ["CPU", "disk", "normal range"],
        ),
        (
            "P6",
            "pool",
            "con",
            2,
            "No schema or index changes were applied to the ledger database in the past month.",
            "No schema or index changes in the past month",
            ["schema", "index"],
        ),
        (
            "P7",
            "pool",
            "con",
            1,
            "The pool-size configuration value had not been edited in the last quarter.",
            "Pool-size configuration value not edited in the last quarter",
            ["pool size", "quarter"],
        ),
        (
            "P8",
            "pool",
            "con",
            1,
            "The database team's on-call received no pages before the incident.",
            "Database on-call received no pages before the incident",
            ["database on-call", "pages"],
        ),
        (
            "P9",
            "pool",
            "con",
            1,
            "Slow-query logs for the incident window contain no new query shapes.",
            "Slow-query logs show no new query shapes",
            ["slow query", "query shapes"],
        ),
        (
            "P10",
            "pool",
            "con",
            1,
            "The database vendor's status page reported no incidents that day.",
            "Database vendor status page reported no incidents",
            ["vendor status", "no incidents"],
        ),
        (
            "P11",
            "pool",
            "con",
            1,
            "The ledger database was restarted for patching four days earlier without issues.",
            "Ledger database restarted for patching four days earlier without issues",
            ["restart", "patching"],
        ),
        (
            "P12",
            "pool",
            "con",
            1,
            "Replication lag stayed under one second during the incident.",
            "Replication lag stayed under one second",
            ["replication lag", "one second"],
        ),
    ]
)

_IR_DECISIVE = _facts(
    [
        (
            "P13",
            "pool",
            "pro",
            2,
            "Pool wait-queue alarms first fired forty minutes before the deploy pipeline started.",
            "Pool wait-queue alarms fired forty minutes before the deploy pipeline started",
            ["forty minutes", "before the deploy", "alarms"],
        ),
        (
            "P14",
            "pool",
            "pro",
            2,
            "Pool checkout latency doubled at 09:12, an hour before the deploy began.",
            "Pool checkout latency doubled at 09:12, before the deploy",
            ["09:12", "checkout latency"],
        ),
        (
            "P15",
            "pool",
            "pro",
            2,
            "A change three sprints ago halved the pool's max size in a shared config library.",
            "A change three sprints ago halved the pool max size in a shared config library",
            ["three sprints", "halved", "max size"],
        ),
        (
            "P16",
            "pool",
            "pro",
            2,
            "Request timeouts in traces align with pool-wait spans rather than config reloads.",
            "Timeouts in traces align with pool-wait spans, not config reloads",
            ["traces", "pool wait", "config reload"],
        ),
        (
            "P17",
            "pool",
            "pro",
            2,
            "Duplicate-charge support tickets began Monday night, before the deploy.",
            "Duplicate-charge tickets began Monday night, before the deploy",
            ["Monday night", "duplicate charge"],
        ),
        (
            "P18",
            "pool",
            "pro",
            1,
            "A batch reconciliation job doubled its connection count after Monday's data backfill.",
            "Batch reconciliation job doubled its connection count after Monday's backfill",
            ["batch job", "backfill", "connections"],
        ),
        (
            "D13",
            "deploy",
            "con",
            2,
            "The changed line in the connection-settings file was a comment; effective values were identical before and after.",
            "Changed line in connection settings was a comment; effective values unchanged",
            ["comment", "effective values"],
        ),
        (
            "D14",
            "deploy",
            "con",
            2,
            "Error rates continued to climb for an hour after the deploy was rolled back.",
            "Errors kept climbing for an hour after rollback",
            ["after rollback", "an hour"],
        ),
        (
            "D15",
            "deploy",
            "con",
            2,
            "The postmortem for the outage eight months ago was later amended to name pool exhaustion as the cause.",
            "The earlier postmortem was amended to name pool exhaustion",
            ["amended", "postmortem", "pool exhaustion"],
        ),
        (
            "D16",
            "deploy",
            "con",
            2,
            "Services that took the deploy but do not use the ledger database showed no error increase.",
            "Deployed services that do not use the ledger database showed no error increase",
            ["no ledger", "no error increase"],
        ),
        (
            "D17",
            "deploy",
            "con",
            1,
            "The elevated errors in the two other services were 5xx responses from the ledger service, not local faults.",
            "Other services' errors were 5xx responses from the ledger service",
            ["5xx", "ledger service"],
        ),
        (
            "D18",
            "deploy",
            "con",
            1,
            "Rollout percentage and error rate diverged after 09:50, when rollout paused and errors kept rising.",
            "Rollout paused at 09:50 while errors kept rising",
            ["09:50", "paused", "diverged"],
        ),
    ]
)

_IR_COUNTER = _facts(
    [
        (
            "D19",
            "deploy",
            "pro",
            1,
            "The deploy modified a retry setting used by the ledger client.",
            "Deploy modified a retry setting in the ledger client",
            ["retry", "ledger client"],
        ),
        (
            "D20",
            "deploy",
            "pro",
            1,
            "The deploy's release notes did not list all changed files.",
            "Release notes did not list all changed files",
            ["release notes", "changed files"],
        ),
        (
            "D21",
            "deploy",
            "pro",
            1,
            "A deploy-related alert fired in the release channel during the incident.",
            "A deploy-related alert fired in the release channel",
            ["release channel", "alert"],
        ),
        (
            "P19",
            "pool",
            "con",
            1,
            "A pool-saturation metric was disabled in a dashboard migration two weeks earlier.",
            "Pool-saturation metric was disabled two weeks earlier",
            ["metric disabled", "dashboard migration"],
        ),
        (
            "P20",
            "pool",
            "con",
            1,
            "The ledger database handled a similar request peak the previous week without incident.",
            "Ledger database handled a similar peak the previous week without incident",
            ["previous week", "request peak"],
        ),
    ]
)

_IR_SHARED_IDS = _ids(_IR_SHARED)

INCIDENT_REVIEW_V1 = Scenario.model_validate(
    {
        "id": "incident-review-v1",
        "title": "Post-mortem Panel: Config Deploy vs. Ledger Pool",
        "brief": "Five engineers must agree on the primary root cause of Tuesday's payments outage before the postmortem is published. Each watched different dashboards and logs during the incident.",
        "isSample": True,
        "candidates": [
            {
                "id": "deploy",
                "name": "Config deploy",
                "blurb": "Tuesday's configuration deploy to the payments service",
            },
            {
                "id": "pool",
                "name": "Ledger pool",
                "blurb": "Connection-pool exhaustion in the ledger database",
            },
        ],
        "agents": [
            {
                "id": "kai",
                "name": "Kai",
                "role": "SRE on-call",
                "style": "timeline-obsessed, terse",
            },
            {
                "id": "lena",
                "name": "Lena",
                "role": "Database engineer",
                "style": "methodical, trusts audit logs",
            },
            {
                "id": "jules",
                "name": "Jules",
                "role": "Support lead",
                "style": "customer-impact focused, plain-spoken",
            },
            {
                "id": "mei",
                "name": "Mei",
                "role": "Backend lead",
                "style": "reads code first, argues second",
            },
            {
                "id": "ravi",
                "name": "Ravi",
                "role": "Platform engineer",
                "style": "systems-minded, traces dependencies",
            },
        ],
        "facts": _IR_SHARED + _IR_DECISIVE + _IR_COUNTER,
        "distribution": {
            "kai": _IR_SHARED_IDS + ["P13", "D13", "D18", "D19"],
            "lena": _IR_SHARED_IDS + ["P18", "D14", "P19"],
            "jules": _IR_SHARED_IDS + ["P17", "D15", "D20"],
            "mei": _IR_SHARED_IDS + ["P14", "P16", "D16", "D21"],
            "ravi": _IR_SHARED_IDS + ["P15", "D17", "P20"],
        },
        "validation": _haiku(["kai", "lena", "jules", "mei", "ravi"], 1.0, True),
    }
)


# ---------------------------------------------------------------------------
# vendor-selection-v1 — Northwind (shared favourite) vs Contoso (pooled favourite)

_VS_SHARED = _facts(
    [
        (
            "N1",
            "northwind",
            "pro",
            2,
            "Northwind's quoted three-year price is 18% below Contoso's.",
            "Three-year quote is 18% below Contoso's",
            ["18%", "three-year price"],
        ),
        (
            "N2",
            "northwind",
            "pro",
            2,
            "Northwind's proposal lists a six-week onboarding timeline.",
            "Proposal lists a six-week onboarding timeline",
            ["six weeks", "onboarding"],
        ),
        (
            "N3",
            "northwind",
            "pro",
            1,
            "Northwind's demo covered every item on the committee's must-have list.",
            "Demo covered every must-have item",
            ["demo", "must-have list"],
        ),
        (
            "N4",
            "northwind",
            "pro",
            1,
            "Northwind includes a named account manager in the base tier.",
            "Named account manager included in the base tier",
            ["account manager", "base tier"],
        ),
        (
            "N5",
            "northwind",
            "pro",
            1,
            "Northwind's agent UI scored highest in the committee's usability walkthrough.",
            "Agent UI scored highest in the usability walkthrough",
            ["usability", "walkthrough"],
        ),
        (
            "N6",
            "northwind",
            "pro",
            1,
            "Northwind lists 40 customers in our industry vertical.",
            "Lists 40 customers in our vertical",
            ["40 customers", "vertical"],
        ),
        (
            "N7",
            "northwind",
            "pro",
            1,
            "Northwind agreed to a 60-day termination clause.",
            "Agreed to a 60-day termination clause",
            ["termination", "60 days"],
        ),
        (
            "N8",
            "northwind",
            "pro",
            1,
            "Northwind answered every RFP question within one business day.",
            "Answered every RFP question within one business day",
            ["RFP", "one business day"],
        ),
        (
            "N9",
            "northwind",
            "con",
            1,
            "Northwind was founded three years ago.",
            "Founded three years ago",
            ["founded", "three years"],
        ),
        (
            "N10",
            "northwind",
            "con",
            1,
            "Northwind's SOC 2 report covers only the last six months.",
            "SOC 2 report covers only the last six months",
            ["SOC 2", "six months"],
        ),
        (
            "N11",
            "northwind",
            "con",
            1,
            "Northwind's API rate limit is 100 requests per minute on the proposed tier.",
            "API rate limit is 100 requests per minute on the proposed tier",
            ["rate limit", "100 per minute"],
        ),
        (
            "N12",
            "northwind",
            "con",
            1,
            "Northwind's data residency options are limited to US regions.",
            "Data residency limited to US regions",
            ["data residency", "US regions"],
        ),
        (
            "C1",
            "contoso",
            "pro",
            1,
            "Contoso has operated the product for eleven years.",
            "Has operated the product for eleven years",
            ["eleven years", "operated"],
        ),
        (
            "C2",
            "contoso",
            "pro",
            1,
            "Contoso publishes a 99.95% uptime SLA.",
            "Publishes a 99.95% uptime SLA",
            ["SLA", "99.95%"],
        ),
        (
            "C3",
            "contoso",
            "pro",
            1,
            "Contoso's platform lists our identity provider among its supported SSO integrations.",
            "Lists our identity provider among supported SSO integrations",
            ["SSO", "identity provider"],
        ),
        (
            "C4",
            "contoso",
            "pro",
            1,
            "Contoso's contract fixes the price for the full term.",
            "Contract fixes the price for the full term",
            ["fixed price", "full term"],
        ),
        (
            "C5",
            "contoso",
            "con",
            2,
            "Contoso's quoted onboarding timeline is fourteen weeks.",
            "Quoted onboarding timeline is fourteen weeks",
            ["fourteen weeks", "onboarding"],
        ),
        (
            "C6",
            "contoso",
            "con",
            2,
            "Contoso's proposal came in 18% above Northwind's.",
            "Proposal is 18% above Northwind's",
            ["18% above", "proposal"],
        ),
        (
            "C7",
            "contoso",
            "con",
            1,
            "Contoso's demo was rescheduled twice.",
            "Demo was rescheduled twice",
            ["demo", "rescheduled"],
        ),
        (
            "C8",
            "contoso",
            "con",
            1,
            "Contoso's admin UI ranked lowest in the usability walkthrough.",
            "Admin UI ranked lowest in the usability walkthrough",
            ["admin UI", "lowest"],
        ),
        (
            "C9",
            "contoso",
            "con",
            1,
            "Contoso charges separately for premium support.",
            "Charges separately for premium support",
            ["premium support", "separate charge"],
        ),
        (
            "C10",
            "contoso",
            "con",
            1,
            "Contoso's roadmap presentation listed no new features for our use case in the next year.",
            "Roadmap lists no new features for our use case next year",
            ["roadmap", "next year"],
        ),
        (
            "C11",
            "contoso",
            "con",
            1,
            "Contoso requires a twelve-month minimum commitment.",
            "Requires a twelve-month minimum commitment",
            ["twelve months", "minimum commitment"],
        ),
        (
            "C12",
            "contoso",
            "con",
            1,
            "Contoso's RFP responses took four business days on average.",
            "RFP responses averaged four business days",
            ["RFP", "four days"],
        ),
    ]
)

_VS_DECISIVE = _facts(
    [
        (
            "C13",
            "contoso",
            "pro",
            2,
            "Two reference customers moved from Northwind to Contoso within the last year.",
            "Two reference customers moved from Northwind to Contoso in the last year",
            ["reference customers", "moved"],
        ),
        (
            "C14",
            "contoso",
            "pro",
            2,
            "Contoso's integration test with our ticketing export completed end to end.",
            "Integration test with our ticketing export completed end to end",
            ["integration test", "end to end"],
        ),
        (
            "C15",
            "contoso",
            "pro",
            2,
            "Contoso's penetration test report shows zero open high-severity findings.",
            "Penetration test report shows zero open high-severity findings",
            ["penetration test", "high severity"],
        ),
        (
            "C16",
            "contoso",
            "pro",
            2,
            "Contoso's price includes data migration; Northwind's quote lists it as a separate line item.",
            "Price includes data migration, which Northwind quotes separately",
            ["data migration", "included"],
        ),
        (
            "C17",
            "contoso",
            "pro",
            2,
            "Contoso resolved the pilot team's three support tickets within the contracted response time.",
            "Resolved the pilot team's three tickets within the contracted response time",
            ["pilot tickets", "response time"],
        ),
        (
            "C18",
            "contoso",
            "pro",
            1,
            "Contoso's contract permits exporting all data in an open format at any time.",
            "Contract permits full data export in an open format at any time",
            ["data export", "open format"],
        ),
        (
            "N13",
            "northwind",
            "con",
            2,
            "Northwind's quote excludes the reporting module the pilot team used daily.",
            "Quote excludes the reporting module the pilot team used daily",
            ["reporting module", "excluded"],
        ),
        (
            "N14",
            "northwind",
            "con",
            2,
            "Northwind's integration test with our ticketing export failed on attachments over 10 MB.",
            "Integration test failed on attachments over 10 MB",
            ["attachments", "10 MB"],
        ),
        (
            "N15",
            "northwind",
            "con",
            2,
            "Northwind's status page lists four outages longer than 30 minutes in the last quarter.",
            "Status page lists four outages over 30 minutes last quarter",
            ["four outages", "status page"],
        ),
        (
            "N16",
            "northwind",
            "con",
            2,
            "Northwind's order form raises the per-seat price 12% annually after year one.",
            "Per-seat price rises 12% annually after year one",
            ["12% annually", "per-seat"],
        ),
        (
            "N17",
            "northwind",
            "con",
            1,
            "Northwind's account manager role is shared across 25 accounts.",
            "Account manager is shared across 25 accounts",
            ["25 accounts", "account manager"],
        ),
        (
            "N18",
            "northwind",
            "con",
            1,
            "Northwind's SOC 2 report lists two exceptions in access control.",
            "SOC 2 report lists two access-control exceptions",
            ["SOC 2", "exceptions"],
        ),
    ]
)

_VS_COUNTER = _facts(
    [
        (
            "N19",
            "northwind",
            "pro",
            1,
            "Northwind offered a three-month pilot extension at no charge.",
            "Offered a three-month pilot extension at no charge",
            ["pilot extension", "no charge"],
        ),
        (
            "N20",
            "northwind",
            "pro",
            1,
            "Northwind's mobile app ranked highest in the pilot survey.",
            "Mobile app ranked highest in the pilot survey",
            ["mobile app", "pilot survey"],
        ),
        (
            "N21",
            "northwind",
            "pro",
            1,
            "Northwind committed to a shared Slack channel for our team.",
            "Committed to a shared Slack channel for our team",
            ["Slack channel", "shared"],
        ),
        (
            "C19",
            "contoso",
            "con",
            1,
            "Contoso's pilot required two support calls to configure SSO.",
            "Pilot required two support calls to configure SSO",
            ["support calls", "SSO"],
        ),
        (
            "C20",
            "contoso",
            "con",
            1,
            "Contoso invoices annually in advance.",
            "Invoices annually in advance",
            ["annual", "in advance"],
        ),
    ]
)

_VS_SHARED_IDS = _ids(_VS_SHARED)

VENDOR_SELECTION_V1 = Scenario.model_validate(
    {
        "id": "vendor-selection-v1",
        "title": "Procurement Committee: Northwind vs. Contoso",
        "brief": "A procurement committee must select one ticketing platform vendor for a three-year contract. Each member ran a different part of the evaluation and holds different findings.",
        "isSample": True,
        "candidates": [
            {
                "id": "northwind",
                "name": "Northwind",
                "blurb": "Ticketing platform vendor, founded three years ago",
            },
            {
                "id": "contoso",
                "name": "Contoso",
                "blurb": "Ticketing platform vendor, eleven years in market",
            },
        ],
        "agents": [
            {
                "id": "vera",
                "name": "Vera",
                "role": "Procurement lead",
                "style": "deadline-driven; wants the contract signed this quarter",
            },
            {
                "id": "noah",
                "name": "Noah",
                "role": "Finance analyst",
                "style": "spreadsheet-minded, totals everything",
            },
            {
                "id": "ingrid",
                "name": "Ingrid",
                "role": "Solutions architect",
                "style": "integration-first, dislikes slideware",
            },
            {
                "id": "sofia",
                "name": "Sofia",
                "role": "Operations lead",
                "style": "speaks for the agents who will use it daily",
            },
            {
                "id": "hugo",
                "name": "Hugo",
                "role": "Security reviewer",
                "style": "pragmatic; signs off once the paperwork is in order",
            },
        ],
        "facts": _VS_SHARED + _VS_DECISIVE + _VS_COUNTER,
        "distribution": {
            "vera": _VS_SHARED_IDS + ["C13", "N13", "N16", "N19"],
            "noah": _VS_SHARED_IDS + ["C16", "C15", "N18", "C20"],
            "ingrid": _VS_SHARED_IDS + ["C14", "N14", "N20"],
            "sofia": _VS_SHARED_IDS + ["C17", "N15", "N21"],
            "hugo": _VS_SHARED_IDS + ["C18", "N17", "C19"],
        },
        "validation": _haiku(["vera", "noah", "ingrid", "sofia", "hugo"], 1.0, True),
    }
)


# ---------------------------------------------------------------------------
# hiring-weak-profile-v1 — same item pool as v1, thinner shared set, 4 decisive
# items, pooled margin +2

_HP_BY_ID = {f["id"]: f for f in _HP_SHARED + _HP_DECISIVE + _HP_COUNTER}


def _hp_facts(ids: list[str], weights: dict[str, int] | None = None) -> list[dict[str, Any]]:
    return [{**_HP_BY_ID[i], "weight": (weights or {}).get(i, _HP_BY_ID[i]["weight"])} for i in ids]


_WEAK_SHARED_IDS = [i for i in _HP_SHARED_IDS if i not in {"J8", "S10", "S11"}]
_WEAK_DECISIVE_IDS = ["S12", "S13", "J12", "J13"]

HIRING_WEAK_PROFILE_V1 = Scenario.model_validate(
    {
        "id": "hiring-weak-profile-v1",
        "title": "Senior Backend Engineer: John vs. Sally (weak profile)",
        "brief": HIRING_PANEL_V1.brief,
        "isSample": True,
        "candidates": HIRING_PANEL_CANDIDATES,
        "agents": [
            {
                "id": "lena",
                "name": "Lena",
                "role": "HR partner",
                "style": "listens for how people treat others",
            },
            {
                "id": "kai",
                "name": "Kai",
                "role": "Release manager",
                "style": "process-minded, risk-averse",
            },
            {
                "id": "ines",
                "name": "Ines",
                "role": "Support lead",
                "style": "empathetic, tests the edge cases",
            },
            {
                "id": "felix",
                "name": "Felix",
                "role": "Finance partner",
                "style": "numbers-driven, questions the cost",
            },
            {
                "id": "theo",
                "name": "Theo",
                "role": "Data engineer",
                "style": "methodical, follows the numbers",
            },
        ],
        "facts": _hp_facts(_WEAK_SHARED_IDS)
        + _hp_facts(_WEAK_DECISIVE_IDS, {"S12": 3, "S13": 2, "J12": 3, "J13": 2}),
        "distribution": {
            "lena": _WEAK_SHARED_IDS + ["J12"],
            "kai": _WEAK_SHARED_IDS + ["S12"],
            "ines": _WEAK_SHARED_IDS + ["J13"],
            "felix": _WEAK_SHARED_IDS + ["S13"],
            "theo": _WEAK_SHARED_IDS,
        },
        "validation": _haiku(
            ["lena", "kai", "ines", "felix", "theo"], 0.5, False, alone={"lena": 0.9}
        ),
    }
)


# ---------------------------------------------------------------------------
# hiring-adversarial-v1 — same item pool as v1; one sponsor holds only the
# pro-John / anti-Sally uniques, the other four split the decisive items

HIRING_ADVERSARIAL_V1 = Scenario.model_validate(
    {
        "id": "hiring-adversarial-v1",
        "title": "Senior Backend Engineer: John vs. Sally (biased sponsor)",
        "brief": HIRING_PANEL_V1.brief + " Victor referred John and sponsored the requisition.",
        "isSample": True,
        "candidates": HIRING_PANEL_CANDIDATES,
        "agents": [
            {
                "id": "victor",
                "name": "Victor",
                "role": "Executive sponsor",
                "style": "referred John; wants the requisition closed this week",
            },
            {
                "id": "grace",
                "name": "Grace",
                "role": "Engineering director",
                "style": "big-picture, budget-aware",
            },
            {
                "id": "ravi",
                "name": "Ravi",
                "role": "Platform engineer",
                "style": "systems-minded, traces dependencies",
            },
            {
                "id": "mei",
                "name": "Mei",
                "role": "Product manager",
                "style": "customer-focused, clarifies tradeoffs",
            },
            {
                "id": "nadia",
                "name": "Nadia",
                "role": "Security engineer",
                "style": "threat-models everything; terse",
            },
        ],
        "facts": _HP_SHARED + _HP_DECISIVE + _HP_COUNTER,
        "distribution": {
            "victor": _HP_SHARED_IDS + ["J18", "J19", "S20"],
            "grace": _HP_SHARED_IDS + ["S12", "S13", "J12"],
            "ravi": _HP_SHARED_IDS + ["S14", "S15", "J13", "J17"],
            "mei": _HP_SHARED_IDS + ["S16", "S17", "J14"],
            "nadia": _HP_SHARED_IDS + ["S18", "J15", "J16", "S19"],
        },
        "validation": _haiku(["victor", "grace", "ravi", "mei", "nadia"], 1.0, True),
    }
)

# N-agent variants of v1: shared items to everyone, uniques redealt with a fixed
# seed (scripts/make_scenario.py --base hiring-panel-v1 --agents N --seed 1).
HIRING_PANEL_VARIANTS: list[Scenario] = [
    scenario_gen.redistribute(HIRING_PANEL_V1, n, seed=1) for n in (3, 7, 9)
]

SAMPLE_SCENARIOS: list[Scenario] = [
    HIRING_PANEL_V1,
    *HIRING_PANEL_VARIANTS,
    INCIDENT_REVIEW_V1,
    VENDOR_SELECTION_V1,
    HIRING_WEAK_PROFILE_V1,
    HIRING_ADVERSARIAL_V1,
    HIRING_PANEL_FLAT,
    HIRING_PANEL_FLAT_V2,
    HIRING_PANEL_NULL,
    *PAPER_SCENARIOS,
]

SAMPLES_BY_ID: dict[str, Scenario] = {s.id: s for s in SAMPLE_SCENARIOS}


def ensure_samples(store: Store) -> int:
    """Upsert samples that are missing or whose stored body differs from the code.

    Samples are code-owned: a stored row with a sample's id is refreshed whenever
    its content no longer matches the code definition. Non-sample ids are never
    touched. Returns the number of rows inserted or updated.
    """
    existing = {s.id: s for s in store.list_scenarios()}
    changed = 0
    for sample in SAMPLE_SCENARIOS:
        stored = existing.get(sample.id)
        if stored is None or stored.model_dump() != sample.model_dump():
            store.upsert_scenario(sample)
            changed += 1
    return changed

"""Reconstructed Stasser & Titus (1985) student-election materials."""

from __future__ import annotations

from app.models import AgentPersona, Candidate, Fact, Scenario, ScenarioSource

_CANDIDATES = [
    Candidate(id="a", name="Candidate A", blurb="A student-body presidential candidate."),
    Candidate(id="b", name="Candidate B", blurb="A student-body presidential candidate."),
    Candidate(id="c", name="Candidate C", blurb="A student-body presidential candidate."),
]
_AGENTS = [
    AgentPersona(
        id="jordan",
        name="Jordan",
        role="student senator",
        style="direct and policy-focused",
    ),
    AgentPersona(
        id="casey",
        name="Casey",
        role="newspaper editor",
        style="skeptical and detail-oriented",
    ),
    AgentPersona(
        id="riley",
        name="Riley",
        role="residence-hall representative",
        style="practical and attentive to student services",
    ),
    AgentPersona(
        id="morgan",
        name="Morgan",
        role="club coordinator",
        style="collaborative and community-minded",
    ),
]


def _fact(candidate: str, item_id: str, valence: str, text: str, keywords: list[str]) -> Fact:
    return Fact(
        id=item_id,
        candidate_id=candidate,
        valence=valence,  # type: ignore[arg-type]
        weight=1,
        text=text,
        memo_text=text,
        keywords=keywords,
    )


def _candidate_facts(candidate: str, rows: list[tuple[str, str, str, list[str]]]) -> list[Fact]:
    return [
        _fact(candidate, item_id, valence, text, keywords)
        for item_id, valence, text, keywords in rows
    ]


_A = _candidate_facts(
    "a",
    [
        (
            "A_P1",
            "pro",
            "Organized a successful campus voter-registration drive last spring.",
            ["campus", "voter-registration", "drive"],
        ),
        (
            "A_P2",
            "pro",
            "Secured funding for a student mental-health listening center.",
            ["funding", "mental-health", "listening"],
        ),
        (
            "A_P3",
            "pro",
            "Negotiated extended library hours during final examinations.",
            ["negotiated", "library", "examinations"],
        ),
        (
            "A_P4",
            "pro",
            "Built a cross-club coalition for the annual service project.",
            ["cross-club", "coalition", "service"],
        ),
        (
            "A_P5",
            "pro",
            "Published a transparent budget for the student activities council.",
            ["transparent", "budget", "activities"],
        ),
        (
            "A_P6",
            "pro",
            "Recruited volunteers for a campus accessibility audit.",
            ["recruited", "volunteers", "accessibility"],
        ),
        (
            "A_P7",
            "pro",
            "Presented a detailed proposal for safer evening transportation.",
            ["detailed", "safer", "transportation"],
        ),
        (
            "A_P8",
            "pro",
            "Resolved a dispute between two student organizations through mediation.",
            ["resolved", "dispute", "mediation"],
        ),
        ("A_N1", "neutral", "Is a junior majoring in history.", ["junior", "majoring", "history"]),
        (
            "A_N2",
            "neutral",
            "Lives in an apartment near the south campus gate.",
            ["apartment", "south", "gate"],
        ),
        (
            "A_N3",
            "neutral",
            "Has worked part-time at the campus bookstore.",
            ["worked", "part-time", "bookstore"],
        ),
        (
            "A_N4",
            "neutral",
            "Plays midfield on a recreational intramural team.",
            ["midfield", "recreational", "intramural"],
        ),
        (
            "A_C1",
            "con",
            "Missed three of the last eight senate meetings.",
            ["missed", "senate", "meetings"],
        ),
        (
            "A_C2",
            "con",
            "Withdrew a residence-fee proposal after little preparation.",
            ["withdrew", "residence-fee", "preparation"],
        ),
        (
            "A_C3",
            "con",
            "Received a warning for using campaign posters in a restricted hallway.",
            ["warning", "campaign", "restricted"],
        ),
        (
            "A_C4",
            "con",
            "Interrupted a public forum while another candidate was answering.",
            ["interrupted", "public", "forum"],
        ),
    ],
)
_B = _candidate_facts(
    "b",
    [
        (
            "B_P1",
            "pro",
            "Coordinated a food-bank collection that filled twelve donation crates.",
            ["coordinated", "food-bank", "donation"],
        ),
        (
            "B_P2",
            "pro",
            "Expanded tutoring access for students in introductory courses.",
            ["expanded", "tutoring", "introductory"],
        ),
        (
            "B_P3",
            "pro",
            "Won unanimous support for a student-club equipment grant.",
            ["unanimous", "support", "equipment"],
        ),
        (
            "B_P4",
            "pro",
            "Maintained a weekly newsletter about campus policy changes.",
            ["maintained", "weekly", "newsletter"],
        ),
        (
            "B_N1",
            "neutral",
            "Is a senior studying environmental science.",
            ["senior", "studying", "environmental"],
        ),
        (
            "B_N2",
            "neutral",
            "Commutes from a neighborhood east of campus.",
            ["commutes", "neighborhood", "east"],
        ),
        (
            "B_N3",
            "neutral",
            "Volunteers at the university radio station.",
            ["volunteers", "university", "radio"],
        ),
        (
            "B_N4",
            "neutral",
            "Keeps a collection of local history postcards.",
            ["keeps", "collection", "postcards"],
        ),
        (
            "B_N5",
            "neutral",
            "Shares a house with two classmates.",
            ["shares", "house", "classmates"],
        ),
        (
            "B_N6",
            "neutral",
            "Prefers tea before morning lectures.",
            ["prefers", "morning", "lectures"],
        ),
        (
            "B_N7",
            "neutral",
            "Completed a summer internship with a city planner.",
            ["completed", "summer", "internship"],
        ),
        (
            "B_N8",
            "neutral",
            "Attends a weekly seminar on urban design.",
            ["attends", "weekly", "urban"],
        ),
        (
            "B_C1",
            "con",
            "Left a committee report unfinished at the end of term.",
            ["left", "committee", "unfinished"],
        ),
        (
            "B_C2",
            "con",
            "Cancelled a debate appearance on the morning of the event.",
            ["cancelled", "debate", "appearance"],
        ),
        (
            "B_C3",
            "con",
            "Dismissed questions about commuter students during an interview.",
            ["dismissed", "questions", "commuter"],
        ),
        (
            "B_C4",
            "con",
            "Used an outdated enrollment figure in a campaign flyer.",
            ["outdated", "enrollment", "flyer"],
        ),
    ],
)
_C = _candidate_facts(
    "c",
    [
        (
            "C_P1",
            "pro",
            "Launched a peer-mentoring program for first-year students.",
            ["launched", "peer-mentoring", "first-year"],
        ),
        (
            "C_P2",
            "pro",
            "Won a regional award for a student-led arts festival.",
            ["regional", "award", "arts"],
        ),
        (
            "C_P3",
            "pro",
            "Installed refill stations in three residence buildings.",
            ["installed", "refill", "residence"],
        ),
        (
            "C_P4",
            "pro",
            "Hosted a public workshop on renters' rights.",
            ["hosted", "workshop", "renters"],
        ),
        (
            "C_N1",
            "neutral",
            "Is a sophomore in the chemistry program.",
            ["sophomore", "chemistry", "program"],
        ),
        (
            "C_N2",
            "neutral",
            "Drives an older hatchback to weekend work.",
            ["drives", "older", "hatchback"],
        ),
        ("C_N3", "neutral", "Keeps notes in a blue spiral notebook.", ["notes", "blue", "spiral"]),
        (
            "C_N4",
            "neutral",
            "Has a younger sibling at the same university.",
            ["younger", "sibling", "university"],
        ),
        (
            "C_N5",
            "neutral",
            "Enjoys cooking meals with housemates.",
            ["enjoys", "cooking", "housemates"],
        ),
        (
            "C_N6",
            "neutral",
            "Takes the early bus on laboratory days.",
            ["takes", "early", "laboratory"],
        ),
        (
            "C_N7",
            "neutral",
            "Works weekends at a neighborhood bakery.",
            ["works", "weekends", "bakery"],
        ),
        (
            "C_N8",
            "neutral",
            "Reads the student newspaper over lunch.",
            ["reads", "newspaper", "lunch"],
        ),
        (
            "C_C1",
            "con",
            "Forgot to reserve a room for a student committee meeting.",
            ["forgot", "reserve", "committee"],
        ),
        (
            "C_C2",
            "con",
            "Made an inaccurate claim about the cost of campus housing.",
            ["inaccurate", "claim", "housing"],
        ),
        (
            "C_C3",
            "con",
            "Avoided a question about how to fund the arts festival.",
            ["avoided", "fund", "festival"],
        ),
        (
            "C_C4",
            "con",
            "Arrived late to a public debate after the opening remarks.",
            ["arrived", "late", "debate"],
        ),
    ],
)

_FACTS = _A + _B + _C
_SHARED_1985 = [
    fact.id
    for fact in _FACTS
    if fact.id
    not in {
        "A_P1",
        "A_P2",
        "A_P3",
        "A_P4",
        "A_P5",
        "A_P6",
        "A_P7",
        "A_P8",
        "B_C1",
        "B_C2",
        "B_C3",
        "B_C4",
    }
]

_SOURCE_HIDDEN = ScenarioSource(
    kind="paper",
    paper="Stasser & Titus (1985), JPSP 48(6)",
    doi_or_url="https://doi.org/10.1037/0022-3514.48.6.1467",
    fidelity="reconstructed",
    notes=(
        "Item wording reconstructed because the paper does not print the original items. "
        "Design uses 3 candidates, 4 panel members, 48 total items, with A 8 pro/4 neutral/4 con, "
        "B 4 pro/8 neutral/4 con, and C 4 pro/8 neutral/4 con; all weights are 1. "
        "A's 8 positives are distributed 2-per-member by our choice; C fully shared is our assumption. "
        "Human results approx.: shared condition ≈67% of groups chose A versus ≈24% in the "
        "unshared/consensus hidden-profile condition; approx., from the user-supplied summary "
        "of the paper; verify against Table 2 of the paper."
    ),
)
_SOURCE_SHARED = _SOURCE_HIDDEN.model_copy(
    update={
        "notes": (
            "Item wording reconstructed because the paper does not print the original items. "
            "Design uses 3 candidates, 4 panel members, 48 total items, with A 8 pro/4 neutral/4 con, "
            "B 4 pro/8 neutral/4 con, and C 4 pro/8 neutral/4 con; all weights are 1. "
            "Every item is shared in this variant. Human results approx.: shared condition ≈67% "
            "of groups chose A versus ≈24% in the unshared/consensus hidden-profile condition; "
            "approx., from the user-supplied summary of the paper; verify against Table 2 of the paper."
        )
    }
)


def _scenario(
    scenario_id: str, title: str, distribution: dict[str, list[str]], source: ScenarioSource
) -> Scenario:
    return Scenario(
        id=scenario_id,
        title=title,
        brief="The student body is choosing a president from three candidates; weigh the panel's evidence.",
        is_sample=True,
        candidates=_CANDIDATES,
        facts=_FACTS,
        agents=_AGENTS,
        distribution=distribution,
        source=source,
    )


STASSER_1985_HIDDEN = _scenario(
    "stasser-1985-hidden",
    "Stasser & Titus 1985 — hidden profile",
    {
        agent.id: _SHARED_1985
        + [
            f"A_P{i}"
            for i in range(1, 9)
            if i in range(2 * _AGENTS.index(agent) + 1, 2 * _AGENTS.index(agent) + 3)
        ]
        + [f"B_C{_AGENTS.index(agent) + 1}"]
        for agent in _AGENTS
    },
    _SOURCE_HIDDEN,
)
STASSER_1985_SHARED = _scenario(
    "stasser-1985-shared",
    "Stasser & Titus 1985 — shared information condition",
    {agent.id: [fact.id for fact in _FACTS] for agent in _AGENTS},
    _SOURCE_SHARED,
)

STASSER_1985_SCENARIOS = [STASSER_1985_HIDDEN, STASSER_1985_SHARED]

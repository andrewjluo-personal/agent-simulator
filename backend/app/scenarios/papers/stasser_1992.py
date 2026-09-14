"""Reconstructed Stasser & Stewart (1992) homicide materials."""

from __future__ import annotations

from app.models import AgentPersona, Candidate, Fact, Scenario, ScenarioSource

_CANDIDATES = [
    Candidate(id="eddie", name="Eddie Sullivan", blurb="Suspect in the homicide case."),
    Candidate(id="billy", name="Billy Prentice", blurb="Suspect in the homicide case."),
    Candidate(id="mickey", name="Mickey Malone", blurb="Suspect in the homicide case."),
]
_AGENTS = [
    AgentPersona(
        id="detective-1", name="Detective 1", role="homicide detective", style="timeline-focused"
    ),
    AgentPersona(
        id="detective-2",
        name="Detective 2",
        role="homicide detective",
        style="physical-evidence focused",
    ),
    AgentPersona(
        id="detective-3", name="Detective 3", role="homicide detective", style="interview-focused"
    ),
]


def _fact(item_id: str, candidate: str, valence: str, text: str, keywords: list[str]) -> Fact:
    return Fact(
        id=item_id,
        candidate_id=candidate,
        valence=valence,  # type: ignore[arg-type]
        weight=1,
        text=text,
        memo_text=text,
        keywords=keywords,
    )


_SHARED: list[Fact] = [
    _fact(
        "S1",
        "eddie",
        "neutral",
        "The victim's watch stopped at 10:40 near the riverside warehouse.",
        ["victim", "watch", "riverside"],
    ),
    _fact(
        "S2",
        "billy",
        "neutral",
        "A streetlamp outside the warehouse had been out since Monday.",
        ["streetlamp", "warehouse", "monday"],
    ),
    _fact(
        "S3",
        "mickey",
        "neutral",
        "The coroner placed the estimated time of death between ten and eleven.",
        ["coroner", "estimated", "death"],
    ),
    _fact(
        "S4",
        "eddie",
        "neutral",
        "Rain left shallow footprints along the loading-dock entrance.",
        ["rain", "shallow", "footprints"],
    ),
    _fact(
        "S5",
        "billy",
        "neutral",
        "A delivery ledger recorded three trucks at the warehouse that evening.",
        ["delivery", "ledger", "trucks"],
    ),
    _fact(
        "S6",
        "mickey",
        "neutral",
        "The victim had arranged to meet someone about a disputed invoice.",
        ["arranged", "disputed", "invoice"],
    ),
    _fact(
        "S7",
        "eddie",
        "neutral",
        "The warehouse key was kept in a cabinet beside the office door.",
        ["warehouse", "cabinet", "office"],
    ),
    _fact(
        "S8",
        "billy",
        "neutral",
        "A neighbor heard a vehicle leave before the rain began.",
        ["neighbor", "vehicle", "rain"],
    ),
    _fact(
        "S9",
        "mickey",
        "neutral",
        "The victim's coat contained a receipt from a late diner.",
        ["victim", "receipt", "diner"],
    ),
    _fact(
        "S10",
        "eddie",
        "neutral",
        "The alley camera recorded movement but not a usable face.",
        ["alley", "camera", "face"],
    ),
    _fact(
        "S11",
        "billy",
        "neutral",
        "The office clock ran four minutes fast according to the manager.",
        ["office", "clock", "manager"],
    ),
    _fact(
        "S12",
        "mickey",
        "neutral",
        "A torn envelope was found beside the warehouse telephone.",
        ["torn", "envelope", "telephone"],
    ),
    _fact(
        "S13",
        "eddie",
        "neutral",
        "The victim had recently changed the lock on the rear gate.",
        ["changed", "lock", "rear"],
    ),
    _fact(
        "S14",
        "billy",
        "pro",
        "Billy's truck was seen near the riverside road that night.",
        ["billy", "truck", "riverside"],
    ),
    _fact(
        "S15",
        "billy",
        "pro",
        "Billy had argued with the victim about the unpaid invoice.",
        ["billy", "argued", "unpaid"],
    ),
    _fact(
        "S16",
        "billy",
        "pro",
        "Billy's fingerprint was found on the warehouse telephone.",
        ["billy", "fingerprint", "telephone"],
    ),
    _fact(
        "S17",
        "mickey",
        "pro",
        "Mickey had borrowed a jacket matching the one described by a witness.",
        ["mickey", "borrowed", "jacket"],
    ),
    _fact(
        "S18",
        "eddie",
        "con",
        "Eddie's alibi placed him away from the warehouse at the likely time.",
        ["eddie", "alibi", "warehouse"],
    ),
]
_HIDDEN: list[Fact] = [
    _fact(
        "H1",
        "eddie",
        "pro",
        "A toll record placed Eddie's car at the warehouse exit minutes after 10:40.",
        ["toll", "eddie", "exit"],
    ),
    _fact(
        "H2",
        "eddie",
        "pro",
        "Eddie's glove carried the victim's distinctive machine-oil residue.",
        ["eddie", "glove", "machine-oil"],
    ),
    _fact(
        "H3",
        "eddie",
        "pro",
        "A bartender recalled Eddie asking whether the warehouse cameras worked.",
        ["bartender", "eddie", "cameras"],
    ),
    _fact(
        "H4",
        "billy",
        "con",
        "Billy was photographed at a late diner during the estimated death window.",
        ["billy", "photographed", "diner"],
    ),
    _fact(
        "H5",
        "billy",
        "con",
        "Billy's phone connected to a tower several miles from the warehouse.",
        ["billy", "phone", "tower"],
    ),
    _fact(
        "H6",
        "mickey",
        "con",
        "Mickey's ferry ticket showed he had left town before the meeting.",
        ["mickey", "ferry", "ticket"],
    ),
]
_FACTS = _SHARED + _HIDDEN
_DISTRIBUTION = {
    "detective-1": [f.id for f in _SHARED] + ["H1", "H4"],
    "detective-2": [f.id for f in _SHARED] + ["H2", "H5"],
    "detective-3": [f.id for f in _SHARED] + ["H3", "H6"],
}


def _source() -> ScenarioSource:
    return ScenarioSource(
        kind="paper",
        paper="Stasser & Stewart (1992), JPSP 63(3)",
        doi_or_url="https://doi.org/10.1037/0022-3514.63.3.426",
        fidelity="reconstructed",
        notes=(
            "Clue text and the shared/unshared structure were reconstructed. "
            "Design uses 3 suspects, 3 detectives, 24 clues, 18 shared clues and 6 critical "
            "unshared clues, including 13 neutral, 3 pro-Billy, 1 pro-Mickey and 1 con-Eddie "
            "shared clues, with 2 hidden clues per detective and all weights 1. "
            "The paper's manipulation is the solve-versus-judge framing. Human results approx.: "
            "solve groups found the correct suspect ≈67% of the time versus ≈35% for judge groups, "
            "approx.; verify against the paper."
        ),
    )


def _scenario(scenario_id: str, title: str, brief: str) -> Scenario:
    return Scenario(
        id=scenario_id,
        title=title,
        brief=brief,
        is_sample=True,
        candidates=_CANDIDATES,
        facts=_FACTS,
        agents=_AGENTS,
        distribution=_DISTRIBUTION,
        source=_source(),
    )


STASSER_1992_SOLVE = _scenario(
    "stasser-1992-solve",
    "Stasser & Stewart 1992 — homicide mystery (solve)",
    "There is a correct answer — solve the case; the evidence identifies the guilty party.",
)
STASSER_1992_JUDGE = _scenario(
    "stasser-1992-judge",
    "Stasser & Stewart 1992 — homicide mystery (judge)",
    "Reach a judgment about who is most likely responsible; weigh opinions.",
)

STASSER_1992_SCENARIOS = [STASSER_1992_SOLVE, STASSER_1992_JUDGE]

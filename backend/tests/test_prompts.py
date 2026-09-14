from __future__ import annotations

from app import prompts
from app.models import RunConfig, Turn
from app.paradigms import get_paradigm
from app.samples import SAMPLES_BY_ID

SCENARIO = SAMPLES_BY_ID["hiring-panel-v1"]
CFG = RunConfig(seed=7, fact_style="labelled")
DANA = next(a for a in SCENARIO.agents if a.id == "dana")
HAND = SCENARIO.distribution["dana"]
PARADIGM = get_paradigm("free_discussion")

HEARD = [
    Turn(
        seq=0,
        round=0,
        agent_id="marcus",
        sentences=["Sally aced the debug.", "John was polished."],
        cited=["S13", "J1"],
        hallucinated=[],
        lean="sally",
        confidence=0.7,
    ),
    Turn(
        seq=1,
        round=0,
        agent_id="priya",
        sentences=["Her postmortems were adopted."],
        cited=["S3"],
        hallucinated=[],
        lean="sally",
        confidence=0.6,
    ),
]

LABELLED_FACT_LINES = (
    "[J1] (about John) John answered every behavioural question in the panel round without pausing and kept each answer under two minutes.\n"
    "[J2] (about John) John has eight years of professional Go, which is the team's primary backend language.\n"
    "[J3] (about John) John's CV lists him as team lead for six engineers at his current employer.\n"
    "[J4] (about John) John's current employer is a payments company most of the panel has heard of.\n"
    "[J5] (about John) John submitted the take-home within a day; the code follows standard Go project layout.\n"
    "[J6] (about John) John used payments vocabulary (settlement, chargeback, reconciliation) correctly throughout the loop.\n"
    "[J7] (about John) John is available to start in two weeks.\n"
    "[J8] (about John) John holds a current AWS Solutions Architect certification.\n"
    "[J9] (about John) John's take-home README omits setup and run instructions.\n"
    "[J10] (about John) In the closing round John asked about title and compensation and did not ask about the product.\n"
    "[J11] (about John) John's compensation ask is at the top of the posted band.\n"
    "[S1] (about Sally) Sally's written design sample is organised into numbered sections with a stated assumptions list.\n"
    "[S2] (about Sally) Sally has six years of backend work in Python and Java on data platforms.\n"
    "[S3] (about Sally) Sally maintains an open-source Postgres migration tool with a few hundred GitHub stars.\n"
    "[S4] (about Sally) In the closing round Sally asked about the on-call rotation and the team's last three incidents.\n"
    "[S5] (about Sally) Sally has not written Go professionally; the team's services are in Go.\n"
    "[S6] (about Sally) Sally paused for several seconds before two panel answers and asked to restart one of them.\n"
    "[S7] (about Sally) Sally's most recent role lasted 14 months.\n"
    "[S8] (about Sally) Sally has had no direct reports and no formal lead title.\n"
    "[S9] (about Sally) Sally asked to work in an editor rather than on the whiteboard for the coding round.\n"
    "[S10] (about Sally) Sally submitted the take-home about an hour before the deadline.\n"
    "[S11] (about Sally) Sally's background is in logistics data platforms rather than payments.\n"
    "[S12] (about Sally) At her last company Sally was the named lead on a ledger migration that moved 2B rows with no recorded downtime.\n"
    "[S14] (about Sally) Sally's design answer covered the double-spend case and proposed idempotency keys before the interviewer raised it.\n"
    "[J16] (about John) Asked about an outage on his service, John said it was not his; the public post-mortem lists him as owner.\n"
    "[J17] (about John) John's former manager says he has met every delivery date they set together."
)

LABELLED_TRANSCRIPT = (
    "TRANSCRIPT SO FAR (what the panel has actually heard):\n"
    "Round 1 — Marcus: Sally aced the debug. John was polished.  [cited: S13, J1]\n"
    "Round 1 — Priya: Her postmortems were adopted.  [cited: S3]\n"
    "\n"
    "FACTS ALREADY MENTIONED BY ANYONE: S13, J1, S3"
)


def test_labelled_fact_lines_snapshot() -> None:
    assert prompts._fact_lines(SCENARIO, HAND) == LABELLED_FACT_LINES


def test_labelled_transcript_snapshot() -> None:
    assert prompts.transcript_block(SCENARIO, HEARD, CFG) == LABELLED_TRANSCRIPT


def test_labelled_schema_has_items_referenced() -> None:
    sp = prompts.system_prompt(SCENARIO, CFG, DANA, HAND, PARADIGM)
    assert '"items_referenced": string[]' in sp


def test_memo_prompt_has_no_labels() -> None:
    cfg = RunConfig(seed=7, fact_style="memo")
    sp = prompts.system_prompt(SCENARIO, cfg, DANA, HAND, PARADIGM)
    tm = prompts.turn_message(SCENARIO, cfg, 1, HEARD, PARADIGM, cfg.rounds)
    for text in (sp, tm):
        for banned in (
            "[S",
            "[J",
            "weight",
            "valence",
            "pro,",
            "con,",
            "items_referenced",
            "FACTS ALREADY MENTIONED",
            "[cited:",
        ):
            assert banned not in text, f"{banned!r} found"
    assert "Your notes on Sally:" in sp
    assert "Your notes on John:" in sp


def test_memo_shuffle_deterministic_per_agent() -> None:
    cfg = RunConfig(seed=7, fact_style="memo")
    tom = next(a for a in SCENARIO.agents if a.id == "tom")
    marcus = next(a for a in SCENARIO.agents if a.id == "marcus")
    a = prompts._memo_lines(SCENARIO, cfg, tom, SCENARIO.distribution["tom"])
    assert a == prompts._memo_lines(SCENARIO, cfg, tom, SCENARIO.distribution["tom"])
    b = prompts._memo_lines(SCENARIO, cfg, marcus, SCENARIO.distribution["tom"])
    assert a != b  # same hand, different agent -> different order


def test_consensus_line() -> None:
    cfg = RunConfig(seed=7, fact_style="memo")
    assert "consensus" not in prompts.system_prompt(SCENARIO, cfg, DANA, HAND, PARADIGM)
    consensus = SCENARIO.model_copy(update={"decision_rule": "consensus"})
    sp = prompts.system_prompt(consensus, cfg, DANA, HAND, PARADIGM)
    assert "The panel is expected to reach a consensus recommendation." in sp


def test_visibility_statement_injected() -> None:
    sp = prompts.system_prompt(SCENARIO, CFG, DANA, HAND, PARADIGM)
    assert PARADIGM.visibility_statement() in sp


def test_vote_message_private_wording() -> None:
    vm = prompts.vote_message(SCENARIO, CFG, 0, HEARD, "dana", total=CFG.rounds, final=False)
    assert "private recommendation; no other panelist will see it" in vm
    assert "Which candidate do you recommend?" in vm
    assert "Based on everything you hold" not in vm

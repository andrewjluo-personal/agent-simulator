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
        cited=["S4", "J1"],
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
    "[S8] (about Sally) Sally maintains a small open-source Postgres migration tool with a few hundred stars.\n"
    "[S9] (about Sally) Sally's written design sample was clear and well-structured.\n"
    "[S10] (about Sally) Sally was visibly nervous in the panel round and rambled through two answers before recovering.\n"
    "[S11] (about Sally) Sally has never written Go, which is our primary backend language.\n"
    "[S12] (about Sally) Sally's most recent tenure was only 14 months.\n"
    "[S13] (about Sally) Sally declined to use the whiteboard and asked to work in an editor instead.\n"
    "[S14] (about Sally) Sally has no formal management experience and no direct reports.\n"
    "[J1] (about John) John gave a polished, confident panel performance and answered every behavioural question crisply.\n"
    "[J2] (about John) John has eight years of Go, our primary backend language.\n"
    "[J3] (about John) John led a team of six engineers at his last company.\n"
    "[J4] (about John) John comes from a top-tier, brand-name employer that everyone on the panel recognises.\n"
    "[J5] (about John) John's take-home was submitted fast and the code was clean and idiomatic.\n"
    "[J6] (about John) John already knows the fintech domain and used our vocabulary correctly throughout.\n"
    "[J7] (about John) John is available to start immediately.\n"
    "[S1] (about Sally) Sally single-handedly designed and shipped the ledger migration at her last company, moving 2B rows with zero downtime.\n"
    "[S5] (about Sally) Sally's system design answer correctly anticipated the double-spend failure mode and proposed idempotency keys before being prompted.\n"
    "[J9] (about John) John's take-home is near-identical to a public blog post solution, down to variable names and an unusual comment.\n"
    "[J13] (about John) In the closing round John asked only about title and compensation and no questions about the product or users."
)

LABELLED_TRANSCRIPT = (
    "TRANSCRIPT SO FAR (what the panel has actually heard):\n"
    "Round 1 — Marcus: Sally aced the debug. John was polished.  [cited: S4, J1]\n"
    "Round 1 — Priya: Her postmortems were adopted.  [cited: S3]\n"
    "\n"
    "FACTS ALREADY MENTIONED BY ANYONE: S4, J1, S3"
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

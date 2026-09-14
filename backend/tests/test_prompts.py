from __future__ import annotations

from app import prompts
from app.models import RunConfig, Turn
from app.paradigms import get_paradigm
from app.samples import HIRING_PANEL_V1

SCENARIO = HIRING_PANEL_V1
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


def test_default_cfg_matches_explicit_defaults() -> None:
    implicit = RunConfig(seed=7, fact_style="memo")
    explicit = RunConfig(
        seed=7,
        fact_style="memo",
        prompt_style="default",
        transcript_visibility="full",
    )
    for a, b in (
        (
            prompts.system_prompt(SCENARIO, implicit, DANA, HAND, PARADIGM),
            prompts.system_prompt(SCENARIO, explicit, DANA, HAND, PARADIGM),
        ),
        (
            prompts.turn_message(SCENARIO, implicit, 1, HEARD, PARADIGM, 3),
            prompts.turn_message(SCENARIO, explicit, 1, HEARD, PARADIGM, 3),
        ),
        (
            prompts.vote_message(SCENARIO, implicit, 0, HEARD, "dana", total=3, final=False),
            prompts.vote_message(SCENARIO, explicit, 0, HEARD, "dana", total=3, final=False),
        ),
    ):
        assert a == b
    sp = prompts.system_prompt(SCENARIO, implicit, DANA, HAND, PARADIGM)
    assert "RULES" in sp
    assert "state evidence" in sp


def test_naive_prompt_shape() -> None:
    cfg = RunConfig(seed=7, prompt_style="naive")
    sp = prompts.system_prompt(SCENARIO, cfg, DANA, HAND, PARADIGM)
    assert "Here is some information available to you:" in sp
    assert "RULES" not in sp
    assert "Never invent evidence" not in sp
    assert "items_referenced" not in sp
    # memo notes are used even when fact_style is labelled
    cfg_labelled = RunConfig(seed=7, prompt_style="naive", fact_style="labelled")
    sp_labelled = prompts.system_prompt(SCENARIO, cfg_labelled, DANA, HAND, PARADIGM)
    assert "Your notes on Sally:" in sp_labelled
    assert "[S13]" not in sp_labelled


def test_naive_variant_lines() -> None:
    nr = RunConfig(seed=7, prompt_style="naive_no_repeat")
    sp = prompts.system_prompt(SCENARIO, nr, DANA, HAND, PARADIGM)
    assert (
        "Do not repeat points another panelist has already made; add something new "
        "or stay brief." in sp
    )
    nc = RunConfig(seed=7, prompt_style="naive_consensus")
    sp = prompts.system_prompt(SCENARIO, nc, DANA, HAND, PARADIGM)
    assert (
        "The panel's goal is to reach a consensus recommendation that the whole "
        "panel can sign." in sp
    )


def test_naive_visibility_sentence_only_when_not_full() -> None:
    full = RunConfig(seed=7, prompt_style="naive", transcript_visibility="full")
    sp = prompts.system_prompt(SCENARIO, full, DANA, HAND, PARADIGM)
    assert "You will not see" not in sp
    assert "most recent round" not in sp
    none = RunConfig(seed=7, prompt_style="naive", transcript_visibility="none")
    sp = prompts.system_prompt(SCENARIO, none, DANA, HAND, PARADIGM)
    assert "You will not see what the other panelists say" in sp


def _round_turns() -> list[Turn]:
    turns = []
    seq = 0
    for r in range(3):
        for agent in ("a1", "a2"):
            turns.append(
                Turn(
                    seq=seq,
                    round=r,
                    agent_id=agent,
                    sentences=[f"round {r} point from {agent}"],
                    cited=[],
                    hallucinated=[],
                    lean="sally",
                    confidence=0.5,
                )
            )
            seq += 1
    return turns


def test_visible_turns_last_round() -> None:
    turns = _round_turns()
    cfg = RunConfig(transcript_visibility="last_round")
    seen = prompts.visible_turns(cfg, turns, 2, ballot=False)
    assert {t.round for t in seen} == {1, 2}
    seen = prompts.visible_turns(cfg, turns, 1, ballot=True)
    assert {t.round for t in seen} == {1}


def test_visible_turns_none() -> None:
    cfg = RunConfig(transcript_visibility="none")
    assert prompts.visible_turns(cfg, _round_turns(), 2, ballot=False) == []
    assert prompts.visible_turns(cfg, _round_turns(), 2, ballot=True) == []


def test_vote_message_visibility_none() -> None:
    cfg = RunConfig(transcript_visibility="none")
    heard = [
        Turn(
            seq=0,
            round=0,
            agent_id="dana",
            sentences=["I hold a decisive note."],
            cited=["S12"],
            hallucinated=[],
            lean="sally",
            confidence=0.6,
        )
    ]
    vm = prompts.vote_message(SCENARIO, cfg, 0, heard, "dana", total=3, final=False)
    assert "hidden in this run" in vm
    assert "Nothing has been said yet" not in vm
    assert "I hold a decisive note." in vm  # own statements still listed
    tm = prompts.turn_message(SCENARIO, cfg, 0, heard, PARADIGM, 3)
    assert "hidden in this run" in tm
    assert "I hold a decisive note." not in tm


def test_candidate_order_random_varies_by_seed() -> None:
    orders = set()
    for s in range(20):
        cfg = RunConfig(candidate_order="random", seed=s)
        ids = tuple(c.id for c in prompts.ordered_candidates(SCENARIO, cfg))
        orders.add(ids)
        msg = prompts.alone_vote_message(SCENARIO, cfg)
        assert f'"vote": "{ids[0]}|' in msg
    assert orders == {("john", "sally"), ("sally", "john")}


def test_candidate_order_fixed_is_unchanged() -> None:
    cfg = RunConfig(seed=7, fact_style="labelled", candidate_order="fixed")
    sp = prompts.system_prompt(SCENARIO, cfg, DANA, HAND, PARADIGM)
    assert sp.index("- john (John)") < sp.index("- sally (Sally)")
    assert prompts.alone_vote_message(SCENARIO, cfg) == prompts.alone_vote_message(SCENARIO)


def test_resolve_candidate_order_balanced() -> None:
    orders0 = [
        prompts.resolve_candidate_order(SCENARIO, RunConfig(seed=0), a) for a in SCENARIO.agents
    ]
    assert orders0.count("fixed") == 3 and orders0.count("reversed") == 2
    orders1 = [
        prompts.resolve_candidate_order(SCENARIO, RunConfig(seed=1), a) for a in SCENARIO.agents
    ]
    assert orders1.count("fixed") == 2 and orders1.count("reversed") == 3
    assert all(a != b for a, b in zip(orders0, orders1))
    assert prompts.resolve_candidate_order(SCENARIO, RunConfig(seed=0), None) == "fixed"
    assert prompts.resolve_candidate_order(SCENARIO, RunConfig(seed=1), None) == "reversed"


def test_alone_vote_options_match_system_order() -> None:
    cfg = RunConfig(candidate_order="balanced", seed=1)
    agent = next(
        a
        for a in SCENARIO.agents
        if prompts.resolve_candidate_order(SCENARIO, cfg, a) == "reversed"
    )
    first_id = prompts._candidate_lines(SCENARIO, cfg, agent).splitlines()[0].split(" ")[1]
    assert first_id == "sally"
    msg = prompts.alone_vote_message(SCENARIO, cfg, agent)
    assert f'"vote": "{first_id}|' in msg


def test_candidate_order_reversed_reverses_lines_and_options() -> None:
    cfg = RunConfig(candidate_order="reversed", seed=3)
    lines = prompts._candidate_lines(SCENARIO, cfg, DANA).splitlines()
    assert lines[0].startswith("- sally") and lines[1].startswith("- john")
    assert prompts._lean_options(SCENARIO, cfg, DANA) == "sally|john|undecided"
    assert '"vote": "sally|john"' in prompts.alone_vote_message(SCENARIO, cfg, DANA)

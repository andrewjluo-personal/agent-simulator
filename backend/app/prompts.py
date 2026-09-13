"""Prompt templates. Pure functions of (scenario, config, agent, hand, heard)."""

from __future__ import annotations

from random import Random

from .models import AgentPersona, RunConfig, Scenario, Turn
from .paradigms import ParadigmSpec
from .truth import UNDECIDED


def _candidate_lines(scenario: Scenario) -> str:
    return "\n".join(f"- {c.id} ({c.name}): {c.blurb}" for c in scenario.candidates)


def _lean_options(scenario: Scenario) -> str:
    return "|".join([c.id for c in scenario.candidates] + [UNDECIDED])


def _fact_lines(scenario: Scenario, hand_fact_ids: list[str]) -> str:
    lines = []
    for fact_id in hand_fact_ids:
        fact = scenario.fact(fact_id)
        name = scenario.fact(fact_id).candidate_id
        display = next((c.name for c in scenario.candidates if c.id == name), name)
        lines.append(f"[{fact.id}] (about {display}) {fact.text}")
    return "\n".join(lines)


def _memo_lines(
    scenario: Scenario, cfg: RunConfig, agent: AgentPersona, hand_fact_ids: list[str]
) -> str:
    """Human-study style notes: one paragraph per candidate, no ids or labels."""
    held = [scenario.fact(fid) for fid in hand_fact_ids]
    blocks = []
    for candidate in scenario.candidates:
        group = [f for f in held if f.candidate_id == candidate.id]
        if not group:
            continue
        Random(f"{cfg.seed}:{agent.id}:{candidate.id}").shuffle(group)
        joined = " ".join(f.memo_text or f.text for f in group)
        blocks.append(f"Your notes on {candidate.name}: {joined}")
    return "\n\n".join(blocks)


def system_prompt(
    scenario: Scenario,
    cfg: RunConfig,
    agent: AgentPersona,
    hand_fact_ids: list[str],
    paradigm: ParadigmSpec,
) -> str:
    extra = paradigm.system_rules(cfg)
    extra_block = f"\n{extra}" if extra else ""
    labelled = cfg.fact_style == "labelled"
    notes = (
        _fact_lines(scenario, hand_fact_ids)
        if labelled
        else _memo_lines(scenario, cfg, agent, hand_fact_ids)
    )
    consensus_line = (
        " The panel is expected to reach a consensus recommendation."
        if scenario.decision_rule == "consensus"
        else ""
    )
    labelled_rule = (
        "\n- Every fact you state in a turn must appear in items_referenced by its id."
        if labelled
        else ""
    )
    items_field = '"items_referenced": string[], ' if labelled else ""
    schema = (
        f'{{"sentences": string[], {items_field}"current_lean": '
        f'"{_lean_options(scenario)}", "confidence": 0..1}}'
    )
    return f"""You are {agent.name}, {agent.role} on the panel. Style: {agent.style}.
The panel has {len(scenario.agents)} interviewers and must recommend exactly one candidate:
{_candidate_lines(scenario)}

{scenario.brief}{consensus_line}
You each attended different parts of the interview loop and took your own notes. The
panel will discuss and then each of you will give a private recommendation.
{paradigm.visibility_statement()}

YOUR NOTES:
{notes}

RULES
- Only assert things that are in your own notes or that another panelist has said. Never
  invent evidence. If you want to reason about something you do not hold, ask, do not assert.
- Speak in at most {cfg.sentences_per_turn} sentences, each under 40 words. Be concrete:
  state evidence, not vibes. Do not summarise the whole discussion.{labelled_rule}{extra_block}

Run nonce: {cfg.seed}

Respond with JSON only:
{schema}"""


def _agent_name(scenario: Scenario, agent_id: str) -> str:
    return next((a.name for a in scenario.agents if a.id == agent_id), agent_id)


def transcript_block(scenario: Scenario, heard_turns: list[Turn], cfg: RunConfig) -> str:
    if heard_turns:
        if cfg.fact_style == "labelled":
            transcript = "\n".join(
                f"Round {t.round + 1} — {_agent_name(scenario, t.agent_id)}: "
                f"{' '.join(t.sentences)}  [cited: {', '.join(t.cited)}]"
                for t in heard_turns
            )
        else:
            transcript = "\n".join(
                f"Round {t.round + 1} — {_agent_name(scenario, t.agent_id)}: "
                f"{' '.join(t.sentences)}"
                for t in heard_turns
            )
    else:
        transcript = "Nothing has been said yet."
    header = f"TRANSCRIPT SO FAR (what the panel has actually heard):\n{transcript}"
    if cfg.fact_style != "labelled":
        return header
    mentioned: list[str] = []
    for t in heard_turns:
        for fact_id in t.cited:
            if fact_id not in mentioned:
                mentioned.append(fact_id)
    return f"""{header}

FACTS ALREADY MENTIONED BY ANYONE: {", ".join(mentioned) if mentioned else "none"}"""


def turn_message(
    scenario: Scenario,
    cfg: RunConfig,
    round_idx: int,
    heard_turns: list[Turn],
    paradigm: ParadigmSpec,
    total: int,
) -> str:
    instruction = paradigm.round_instruction(round_idx, cfg)
    instruction_block = f"\n{instruction}" if instruction else ""
    return f"""Round {round_idx + 1} of {total}. You speak now.

{transcript_block(scenario, heard_turns, cfg)}{instruction_block}

Your turn. JSON only."""


def vote_message(
    scenario: Scenario,
    cfg: RunConfig,
    round_idx: int,
    heard_turns: list[Turn],
    agent_id: str,
    *,
    total: int,
    final: bool,
) -> str:
    own = [t for t in heard_turns if t.agent_id == agent_id]
    own_lines = (
        "\n".join(f"Round {t.round + 1}: {' '.join(t.sentences)}" for t in own)
        or "You have not spoken yet."
    )
    last_lean = own[-1].lean if own else UNDECIDED
    lean_name = next((c.name for c in scenario.candidates if c.id == last_lean), last_lean)
    return f"""Round {round_idx + 1} of {total} is over. This is a private recommendation; no other panelist will see it. Consider your own notes and what you heard.

{transcript_block(scenario, heard_turns, cfg)}

YOUR OWN STATEMENTS SO FAR:
{own_lines}
Your last stated lean: {lean_name}.

Vote consistently with what you said unless something you heard changed your mind;
if you changed your mind, say what changed it in "reason".
Which candidate do you recommend? Give one sentence of reasoning.
JSON only: {{"vote": candidate id or "undecided", "confidence": 0..1, "reason": string}}"""


def alone_vote_message(scenario: Scenario) -> str:
    options = "|".join(c.id for c in scenario.candidates)
    return f"""You have not spoken to any other panelist. Based only on your own notes,
which candidate do you recommend? You must pick one.
JSON only: {{"vote": "{options}", "confidence": 0..1, "reason": string}}"""

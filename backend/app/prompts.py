"""Prompt templates. Pure functions of (scenario, config, agent, hand, heard)."""

from __future__ import annotations

from random import Random

from .models import AgentPersona, Candidate, RunConfig, Scenario, Turn
from .paradigms import ParadigmSpec
from .truth import UNDECIDED


def ordered_candidates(scenario: Scenario, cfg: RunConfig | None) -> list[Candidate]:
    cands = list(scenario.candidates)
    if cfg is not None and cfg.candidate_order == "reversed":
        cands.reverse()
    elif cfg is not None and cfg.candidate_order == "random":
        Random(f"{cfg.seed}:candidate_order").shuffle(cands)
    return cands


def _candidate_lines(scenario: Scenario, cfg: RunConfig | None) -> str:
    return "\n".join(f"- {c.id} ({c.name}): {c.blurb}" for c in ordered_candidates(scenario, cfg))


def _lean_options(scenario: Scenario, cfg: RunConfig | None) -> str:
    return "|".join([c.id for c in ordered_candidates(scenario, cfg)] + [UNDECIDED])


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
    for candidate in ordered_candidates(scenario, cfg):
        group = [f for f in held if f.candidate_id == candidate.id]
        if not group:
            continue
        Random(f"{cfg.seed}:{agent.id}:{candidate.id}").shuffle(group)
        joined = " ".join(f.memo_text or f.text for f in group)
        blocks.append(f"Your notes on {candidate.name}: {joined}")
    return "\n\n".join(blocks)


def visibility_statement(cfg: RunConfig, paradigm: ParadigmSpec) -> str:
    if cfg.transcript_visibility == "last_round":
        return (
            "Before each turn you will see only the most recent round of discussion; "
            "each ballot shows only the round just finished."
        )
    if cfg.transcript_visibility == "none":
        return (
            "You will not see what the other panelists say; you only have your own "
            "notes and your own statements."
        )
    return paradigm.visibility_statement()


_NAIVE_EXTRA_LINE = {
    "naive_no_repeat": (
        "Do not repeat points another panelist has already made; add something new or stay brief."
    ),
    "naive_consensus": (
        "The panel's goal is to reach a consensus recommendation that the whole panel can sign."
    ),
}


def _naive_system_prompt(
    scenario: Scenario,
    cfg: RunConfig,
    agent: AgentPersona,
    hand_fact_ids: list[str],
    paradigm: ParadigmSpec,
) -> str:
    """HiddenBench-style naive prompt: memo notes, no RULES, no labelled ids."""
    notes = _memo_lines(scenario, cfg, agent, hand_fact_ids)
    schema = (
        f'{{"sentences": string[], "current_lean": '
        f'"{_lean_options(scenario, cfg)}", "confidence": 0..1}}'
    )
    vis = "" if cfg.transcript_visibility == "full" else f"\n{visibility_statement(cfg, paradigm)}"
    concise = "Keep your response concise, just one or two sentences."
    extra = _NAIVE_EXTRA_LINE.get(cfg.prompt_style)
    if extra:
        concise = f"{concise}\n{extra}"
    return f"""You are {agent.name}, {agent.role} on the panel. Style: {agent.style}.
The panel has {len(scenario.agents)} interviewers and must recommend exactly one candidate:
{_candidate_lines(scenario, cfg)}

{scenario.brief}
The panel will discuss and then each of you will give a private recommendation.{vis}

Here is some information available to you:
{notes}

{concise}

Run nonce: {cfg.seed}

Respond with JSON only:
{schema}"""


def visible_turns(
    cfg: RunConfig, heard_turns: list[Turn], round_idx: int, *, ballot: bool
) -> list[Turn]:
    """The slice of the transcript the agent may see under cfg.transcript_visibility."""
    if cfg.transcript_visibility == "none":
        return []
    if cfg.transcript_visibility == "last_round":
        if ballot:
            return [t for t in heard_turns if t.round == round_idx]
        return [t for t in heard_turns if t.round >= round_idx - 1]
    return heard_turns


def system_prompt(
    scenario: Scenario,
    cfg: RunConfig,
    agent: AgentPersona,
    hand_fact_ids: list[str],
    paradigm: ParadigmSpec,
) -> str:
    if cfg.prompt_style != "default":
        return _naive_system_prompt(scenario, cfg, agent, hand_fact_ids, paradigm)
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
        f'"{_lean_options(scenario, cfg)}", "confidence": 0..1}}'
    )
    return f"""You are {agent.name}, {agent.role} on the panel. Style: {agent.style}.
The panel has {len(scenario.agents)} interviewers and must recommend exactly one candidate:
{_candidate_lines(scenario, cfg)}

{scenario.brief}{consensus_line}
You each attended different parts of the interview loop and took your own notes. The
panel will discuss and then each of you will give a private recommendation.
{visibility_statement(cfg, paradigm)}

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
    if cfg.transcript_visibility == "none":
        return "TRANSCRIPT: hidden in this run (you see only your own notes and statements)."
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
    heard = visible_turns(cfg, heard_turns, round_idx, ballot=False)
    return f"""Round {round_idx + 1} of {total}. You speak now.

{transcript_block(scenario, heard, cfg)}{instruction_block}

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
    heard = visible_turns(cfg, heard_turns, round_idx, ballot=True)
    return f"""Round {round_idx + 1} of {total} is over. This is a private recommendation; no other panelist will see it. Consider your own notes and what you heard.

{transcript_block(scenario, heard, cfg)}

YOUR OWN STATEMENTS SO FAR:
{own_lines}
Your last stated lean: {lean_name}.

Vote consistently with what you said unless something you heard changed your mind;
if you changed your mind, say what changed it in "reason".
Which candidate do you recommend? Give one sentence of reasoning.
JSON only: {{"vote": candidate id or "undecided", "confidence": 0..1, "reason": string}}"""


def alone_vote_message(scenario: Scenario, cfg: RunConfig | None = None) -> str:
    options = "|".join(c.id for c in ordered_candidates(scenario, cfg))
    return f"""You have not spoken to any other panelist. Based only on your own notes,
which candidate do you recommend? You must pick one.
Keep "reason" to one sentence.
JSON only: {{"vote": "{options}", "confidence": 0..1, "reason": string}}"""

"""Prompt templates. Pure functions of (scenario, config, agent, hand, heard)."""

from __future__ import annotations

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
        lines.append(f"[{fact.id}] (about {display}, {fact.valence}, weight {fact.weight}) {fact.text}")
    return "\n".join(lines)


def system_prompt(
    scenario: Scenario,
    cfg: RunConfig,
    agent: AgentPersona,
    hand_fact_ids: list[str],
    paradigm: ParadigmSpec,
) -> str:
    extra = paradigm.system_rules(cfg)
    extra_block = f"\n{extra}" if extra else ""
    return f"""You are {agent.name}, {agent.role} on the panel. Style: {agent.style}.
The panel has {len(scenario.agents)} interviewers and must recommend exactly one candidate:
{_candidate_lines(scenario)}

{scenario.brief}

EVIDENCE YOU PERSONALLY HOLD — you attended different parts of the loop, so other
panelists saw things you did not, and you saw things they did not:
{_fact_lines(scenario, hand_fact_ids)}

RULES
- You may only assert facts from the list above. Never invent evidence. If you want
  to reason about something you do not hold, say so as a question, not a fact.
- Every fact you state in a turn must appear in items_referenced by its id.
- Speak in at most {cfg.sentences_per_turn} sentences, each under 40 words. Be concrete:
  state evidence, not vibes. Do not summarise the whole discussion.
- Other panelists cannot see your evidence list. If a fact of yours has not appeared
  in the transcript, they do not know it.{extra_block}

Run nonce: {cfg.seed}

Respond with JSON only:
{{"sentences": string[], "items_referenced": string[], "current_lean": "{_lean_options(scenario)}", "confidence": 0..1}}"""


def _agent_name(scenario: Scenario, agent_id: str) -> str:
    return next((a.name for a in scenario.agents if a.id == agent_id), agent_id)


def turn_message(
    scenario: Scenario,
    cfg: RunConfig,
    round_idx: int,
    heard_turns: list[Turn],
    paradigm: ParadigmSpec,
) -> str:
    if heard_turns:
        transcript = "\n".join(
            f"Round {t.round + 1} — {_agent_name(scenario, t.agent_id)}: "
            f"{' '.join(t.sentences)}  [cited: {', '.join(t.cited)}]"
            for t in heard_turns
        )
    else:
        transcript = "Nothing has been said yet. You speak first."
    mentioned: list[str] = []
    for t in heard_turns:
        for fact_id in t.cited:
            if fact_id not in mentioned:
                mentioned.append(fact_id)
    instruction = paradigm.round_instruction(round_idx, cfg)
    instruction_block = f"\n{instruction}" if instruction else ""
    return f"""Round {round_idx + 1} of {cfg.rounds}. You speak now.

TRANSCRIPT SO FAR (what the panel has actually heard):
{transcript}

FACTS ALREADY MENTIONED BY ANYONE: {', '.join(mentioned) if mentioned else 'none'}{instruction_block}

Your turn. JSON only."""


def vote_message(round_idx: int, cfg: RunConfig, final: bool) -> str:
    reason = "\nGive one sentence of reasoning." if final else ""
    return f"""Round {round_idx + 1} is over. This is a PRIVATE ballot — no other panelist will see it.
Based on everything you hold plus everything you have heard, which candidate do you recommend?{reason}
JSON only: {{"vote": candidate id or "undecided", "confidence": 0..1, "reason": string}}"""

"""Discussion paradigms (protocol registry). Adding one = one new ParadigmSpec."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from .models import AgentPersona, RunConfig

if TYPE_CHECKING:
    from .models import RunState
    from .validate import ValidatedTurn

MODERATOR_ID = "moderator"
MODERATOR = AgentPersona(
    id=MODERATOR_ID,
    name="Moderator",
    role="non-voting facilitator",
    style="brief, neutral",
)


@dataclass(frozen=True)
class ParadigmSpec:
    id: str
    label: str
    description: str

    def system_rules(self, cfg: RunConfig) -> str:
        """Extra RULES bullets for the system prompt."""
        return ""

    def visibility_statement(self) -> str:
        """One sentence telling the agent what of the discussion it will see."""
        return "You will see the full discussion so far before each turn and before each ballot."

    def round_instruction(self, round_idx: int, cfg: RunConfig) -> str | None:
        """Appended to the per-turn user message."""
        return None

    def opinions_allowed(self, round_idx: int) -> bool:
        return True

    def opinions_allowed_for(self, round_idx: int, cfg: RunConfig) -> bool:
        return self.opinions_allowed(round_idx)

    def phase_for(
        self, round_idx: int, cfg: RunConfig
    ) -> Literal["exchange", "decide"] | None:
        return None

    def visible_context(self, run: RunState, agent_id: str, round_idx: int) -> str | None:
        return None

    def extra_participants(self) -> list[AgentPersona]:
        return []

    def turn_addendum(self, run: RunState, agent_id: str, round_idx: int) -> str | None:
        return None

    def parse_turn(
        self,
        raw: dict[str, Any] | None,
        hand: set[str],
        common_ground: set[str],
        candidate_ids: set[str],
        cfg: RunConfig,
        round_idx: int,
        inferred_cited: list[str] | None = None,
    ) -> ValidatedTurn:
        from .validate import validate_turn

        return validate_turn(
            raw,
            hand,
            common_ground,
            candidate_ids,
            cfg.sentences_per_turn,
            self.opinions_allowed_for(round_idx, cfg),
            inferred_cited=inferred_cited,
        )

    def response_format(self) -> str | None:
        return None

    @property
    def output_format(self) -> str:
        return "chat"

FREE_DISCUSSION = ParadigmSpec(
    id="free_discussion",
    label="Free discussion",
    description="Agents speak their mind from round 0; the hidden-profile failure mode is expected.",
)

SHARE_FIRST_INSTRUCTION = (
    "This is the information-pooling round. State evidence from your own notes only "
    "— prefer facts nobody has mentioned yet. Do not give an opinion or recommendation."
)


@dataclass(frozen=True)
class ShareFirst(ParadigmSpec):
    def round_instruction(self, round_idx: int, cfg: RunConfig) -> str | None:
        return SHARE_FIRST_INSTRUCTION if round_idx == 0 else None

    def opinions_allowed(self, round_idx: int) -> bool:
        return round_idx != 0


@dataclass(frozen=True)
class ExchangeThenDecide(ParadigmSpec):
    def exchange_rounds(self, cfg: RunConfig) -> int:
        return (cfg.rounds + 1) // 2

    def phase_for(
        self, round_idx: int, cfg: RunConfig
    ) -> Literal["exchange", "decide"]:
        return "exchange" if round_idx < self.exchange_rounds(cfg) else "decide"

    def opinions_allowed_for(self, round_idx: int, cfg: RunConfig) -> bool:
        return self.phase_for(round_idx, cfg) == "decide"

    def round_instruction(self, round_idx: int, cfg: RunConfig) -> str | None:
        if self.phase_for(round_idx, cfg) == "exchange":
            return (
                "This is an information-exchange round. State facts from your own notes "
                "that have not been mentioned yet. No opinions, no recommendations."
            )
        return None

    def turn_addendum(self, run: RunState, agent_id: str, round_idx: int) -> str | None:
        if self.phase_for(round_idx, run.config) == "exchange":
            heard = {fact_id for turn in run.turns for fact_id in turn.cited}
            unmentioned = [fact_id for fact_id in run.scenario.distribution[agent_id] if fact_id not in heard]
            if unmentioned:
                return f"Your facts not yet mentioned by anyone: {', '.join(unmentioned)}"
            return "All your facts have been mentioned."
        if round_idx == self.exchange_rounds(run.config):
            return "— Discussion phase begins — you may now argue and state a recommendation."
        return None


@dataclass(frozen=True)
class ElicitationModerator(ParadigmSpec):
    def extra_participants(self) -> list[AgentPersona]:
        return [MODERATOR]


@dataclass(frozen=True)
class MessageBoard(ParadigmSpec):
    def system_rules(self, cfg: RunConfig) -> str:
        return (
            '- Post fact ids plus a one-line note to the shared board. Use JSON shape '
            '{"fact_ids": string[], "note": string, "current_lean": candidate id or '
            '"undecided", "confidence": 0..1}.'
        )

    def response_format(self) -> str | None:
        return (
            '{"fact_ids": string[], "note": string, "current_lean": '
            'candidate id or "undecided", "confidence": 0..1}'
        )

    @property
    def output_format(self) -> str:
        return "board"

    def visible_context(self, run: RunState, agent_id: str, round_idx: int) -> str:
        posted: list[str] = []
        latest: dict[str, str] = {}
        latest_lean: dict[str, str] = {}
        agents = {agent.id: agent for agent in run.scenario.agents}
        for turn in run.turns:
            if turn.agent_id not in agents:
                continue
            for fact_id in turn.cited:
                if fact_id not in posted:
                    posted.append(fact_id)
            note = turn.sentences[0] if turn.sentences else "(no note)"
            latest[turn.agent_id] = re.split(r"(?<=[.!?])\s+", note, maxsplit=1)[0]
            latest_lean[turn.agent_id] = turn.lean
        if not posted:
            return "The board is empty. You post first."
        fact_lines = []
        for fact_id in posted:
            turn = next(t for t in run.turns if fact_id in t.cited)
            fact_lines.append(
                f"[{fact_id}] {run.scenario.fact(fact_id).text} — posted by "
                f"{agents[turn.agent_id].name} (R{turn.round + 1})"
            )
        note_lines = [
            f"{agents[agent_id].name}: {latest[agent_id]} · lean {latest_lean[agent_id]}"
            for agent_id in agents
            if agent_id in latest
        ]
        return "\n".join(fact_lines + ["LATEST NOTES:"] + note_lines)

    def parse_turn(
        self,
        raw: dict[str, Any] | None,
        hand: set[str],
        common_ground: set[str],
        candidate_ids: set[str],
        cfg: RunConfig,
        round_idx: int,
        inferred_cited: list[str] | None = None,
    ) -> ValidatedTurn:
        from .validate import validate_board

        return validate_board(raw, hand, candidate_ids, self.opinions_allowed_for(round_idx, cfg))


EXCHANGE_THEN_DECIDE = ExchangeThenDecide(
    id="exchange_then_decide",
    label="Exchange, then decide",
    description=(
        "First ceil(rounds/2) rounds are evidence-only exchange — each agent is told "
        "which of its own facts are still unmentioned; remaining rounds are free discussion."
    ),
)

ELICITATION_MODERATOR = ElicitationModerator(
    id="elicitation_moderator",
    label="Elicitation moderator",
    description=(
        "A non-voting moderator speaks first each round, asking a named agent to share "
        "unmentioned evidence or summarising the disagreement."
    ),
)

MESSAGE_BOARD = MessageBoard(
    id="message_board",
    label="Message board",
    description=(
        "No prose transcript: agents post fact ids plus a one-line note to a shared board; "
        "facts are shown to others verbatim from the scenario, opinions are one line."
    ),
)


SHARE_FIRST = ShareFirst(
    id="share_first",
    label="Share first",
    description="Round 0 is evidence-only (no opinions); later rounds are free discussion.",
)

PARADIGMS: dict[str, ParadigmSpec] = {
    p.id: p
    for p in (
        FREE_DISCUSSION,
        SHARE_FIRST,
        EXCHANGE_THEN_DECIDE,
        ELICITATION_MODERATOR,
        MESSAGE_BOARD,
    )
}


def get_paradigm(paradigm_id: str) -> ParadigmSpec:
    return PARADIGMS[paradigm_id]

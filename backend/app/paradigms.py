"""Discussion paradigms (protocol registry). Adding one = one new ParadigmSpec."""

from __future__ import annotations

from dataclasses import dataclass

from .models import RunConfig


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


SHARE_FIRST = ShareFirst(
    id="share_first",
    label="Share first",
    description="Round 0 is evidence-only (no opinions); later rounds are free discussion.",
)

PARADIGMS: dict[str, ParadigmSpec] = {p.id: p for p in (FREE_DISCUSSION, SHARE_FIRST)}


def get_paradigm(paradigm_id: str) -> ParadigmSpec:
    return PARADIGMS[paradigm_id]

"""Wire models. Every API payload serializes with model_dump(by_alias=True) so the
JSON matches frontend/src/types.ts (camelCase) exactly."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


Valence = Literal["pro", "con", "neutral"]
Paradigm = Literal["free_discussion", "share_first"]
TurnOrder = Literal["clockwise", "random"]
CandidateOrder = Literal["fixed", "reversed", "random"]
TieBreak = Literal["none", "runoff", "chair"]
FactStyle = Literal["memo", "labelled"]
PromptStyle = Literal["default", "naive", "naive_no_repeat", "naive_consensus"]
TranscriptVisibility = Literal["full", "last_round", "none"]
DecisionRule = Literal["majority", "consensus"]
RunStatus = Literal["queued", "running", "done", "error"]
LlmProvider = Literal["anthropic", "fake"]


class Candidate(Model):
    id: str
    name: str
    blurb: str


class Fact(Model):
    id: str
    candidate_id: str
    valence: Valence
    weight: int = Field(default=1, ge=1)
    text: str
    memo_text: str | None = None
    keywords: list[str] = []


class AgentPersona(Model):
    id: str
    name: str
    role: str
    style: str


class ValidationResult(Model):
    alone_wrong_rate: dict[str, float]  # agentId -> rate picking the wrong (shared-only) candidate
    pooled_right_rate: float
    trials: int
    date: str  # ISO date
    passed: bool
    free_discussion_rate: float | None = None  # mean(metrics.correct) over free_discussion runs
    free_discussion_runs: int = 0


class ScenarioSource(Model):
    kind: Literal["sample", "paper", "custom"]
    paper: str | None = None
    doi_or_url: str | None = None
    fidelity: Literal["verbatim", "reconstructed", "inspired", "modified"] | None = None
    notes: str | None = None


class Scenario(Model):
    id: str
    title: str
    brief: str
    is_sample: bool = False
    candidates: list[Candidate]
    facts: list[Fact]
    agents: list[AgentPersona]
    distribution: dict[str, list[str]]
    decision_rule: DecisionRule = "majority"
    validation: dict[str, ValidationResult] | None = None  # keyed by model
    source: ScenarioSource = ScenarioSource(kind="sample")
    parent_id: str | None = None
    created_at: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Scenario:
        candidate_ids = [c.id for c in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate ids must be unique")
        candidate_set = set(candidate_ids)
        fact_ids = {f.id for f in self.facts}
        if len(fact_ids) != len(self.facts):
            raise ValueError("fact ids must be unique")
        for fact in self.facts:
            if fact.candidate_id not in candidate_set:
                raise ValueError(f"fact {fact.id} references unknown candidate {fact.candidate_id}")
        agent_ids = {a.id for a in self.agents}
        if set(self.distribution) != agent_ids:
            raise ValueError("every agent must appear in distribution and vice versa")
        for agent_id, held in self.distribution.items():
            unknown = set(held) - fact_ids
            if unknown:
                raise ValueError(f"agent {agent_id} holds unknown facts {sorted(unknown)}")
        return self

    def fact(self, fact_id: str) -> Fact:
        for f in self.facts:
            if f.id == fact_id:
                return f
        raise KeyError(fact_id)


class RunConfig(Model):
    scenario_id: str = "hiring-panel-flat-v2"
    paradigm: Paradigm = "free_discussion"
    rounds: int = Field(default=3, ge=1, le=15)
    sentences_per_turn: int = Field(default=2, ge=1, le=5)
    turn_order: TurnOrder = "clockwise"
    candidate_order: CandidateOrder = "fixed"
    tie_break: TieBreak = "runoff"
    fact_style: FactStyle = "memo"
    prompt_style: PromptStyle = "default"
    transcript_visibility: TranscriptVisibility = "full"
    model: str = "claude-haiku-4-5"
    seed: int = 0


class AgentLean(Model):
    agent_id: str
    scores: dict[str, int]
    verdict: str


class ScenarioAnalysis(Model):
    agent_leans: list[AgentLean]
    pooled_scores: dict[str, int]
    pooled_verdict: str
    shared_only_verdict: str
    margin: int
    total_weight: int
    decisive_fact_ids: list[str]
    hidden_decisive_fact_ids: list[str]
    flip_k: int
    is_hidden_profile: bool
    validation: ValidationResult | None


class ValidationJob(Model):
    id: str
    scenario_id: str
    model: str
    status: RunStatus
    trials: int
    discussion_runs: int
    batch_id: str | None = None
    result: ValidationResult | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class TurnOut(Model):
    """Raw model output for a discussion turn, pre-validation."""

    sentences: list[str]
    items_referenced: list[str] = []
    current_lean: str
    confidence: float


class VoteOut(Model):
    vote: str
    confidence: float
    reason: str = ""


class Turn(Model):
    seq: int
    round: int
    agent_id: str
    sentences: list[str]
    cited: list[str]
    hallucinated: list[str]
    lean: str
    confidence: float
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    heard_before: list[str] = []


class Vote(Model):
    round: int
    agent_id: str
    choice: str
    confidence: float
    reason: str | None = None
    said_lean: str = "undecided"  # latest public turn lean at ballot time


class FirstSurfaced(Model):
    seq: int
    round: int
    agent_id: str


class MentionCounts(Model):
    shared: int = 0
    unique: int = 0


class TokenTotals(Model):
    input: int = 0
    output: int = 0


class Metrics(Model):
    correct: bool
    correct_candidate_id: str
    majority_candidate_id: str
    final_tally: dict[str, int]
    decisive_surfaced: float
    decisive_total: int
    decisive_surfaced_count: int
    agreement: float
    hallucination_count: int
    vote_trajectory: list[dict[str, int]]
    first_surfaced: dict[str, FirstSurfaced] = {}
    unspoken_decisive: list[str] = []
    holders: dict[str, list[str]] = {}
    mentions: MentionCounts = MentionCounts()
    vote_rounds: list[
        int
    ] = []  # round index per entry of the *_by_round arrays; -1 = pre-discussion
    agreement_by_round: list[float] = []
    accuracy_by_round: list[float] = []
    tokens_total: TokenTotals = TokenTotals()
    llm_calls: int = 0
    latency_total_ms: int = 0


class RunState(Model):
    id: str
    scenario_id: str
    scenario: Scenario
    config: RunConfig
    status: RunStatus
    current_round: int = 0
    is_demo: bool = False
    batch_id: str | None = None
    llm_provider: LlmProvider
    error: str | None = None
    metrics: Metrics | None = None
    engine_version: str = ""
    turns: list[Turn] = []
    votes: list[Vote] = []
    created_at: str = ""


class RunSummary(Model):
    id: str
    scenario_id: str
    config: RunConfig
    status: RunStatus
    current_round: int
    is_demo: bool
    batch_id: str | None = None
    llm_provider: LlmProvider
    error: str | None = None
    metrics: Metrics | None = None
    engine_version: str = ""
    created_at: str


class BatchState(Model):
    id: str
    runs: list[RunSummary]


class DemoSnapshot(Model):
    scenario: Scenario
    runs: list[RunSummary]
    engine_version: str
    auto_run_on_load: bool = True


def summary(run: RunState) -> RunSummary:
    return RunSummary(**run.model_dump(exclude={"turns", "votes", "scenario"}))

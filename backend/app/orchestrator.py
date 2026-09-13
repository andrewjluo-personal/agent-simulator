"""Simulation orchestrator. One queue job = one round; every step is idempotent
so at-least-once delivery is safe."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from random import Random
from typing import Any

from . import prompts, truth, validate
from .llm import LLMClient, LLMRequest, LLMResponse
from .models import Metrics, RunConfig, RunState, Turn, Vote
from .paradigms import get_paradigm
from .scenario import load_scenario
from .store import Store
from .telemetry import emit


def new_run(
    store: Store,
    cfg: RunConfig,
    *,
    provider: str,
    is_demo: bool = False,
    batch_id: str | None = None,
) -> RunState:
    scenario = load_scenario(store, cfg.scenario_id)
    return RunState(
        id=str(uuid.uuid4()),
        scenario_id=cfg.scenario_id,
        scenario=scenario,
        config=cfg,
        status="queued",
        is_demo=is_demo,
        batch_id=batch_id,
        llm_provider=provider,  # type: ignore[arg-type]
        created_at=datetime.now(UTC).isoformat(),
    )


def turn_order(run: RunState, round_idx: int) -> list[str]:
    order = [a.id for a in run.scenario.agents]
    if run.config.turn_order == "random":
        Random(run.config.seed * 1000 + round_idx).shuffle(order)
    return order


def _meta(
    run: RunState, kind: str, agent_id: str, round_idx: int, hand: list[str]
) -> dict[str, Any]:
    scenario = run.scenario
    heard = sorted({f for t in run.turns for f in t.cited})
    return {
        "kind": kind,
        "seed": run.config.seed,
        "run_nonce": run.id,
        "agent_id": agent_id,
        "round": round_idx,
        "hand": hand,
        "shared": sorted(truth.shared_fact_ids(scenario) & set(hand)),
        "heard": heard,
        "candidates": [c.id for c in scenario.candidates],
        "sentences_per_turn": run.config.sentences_per_turn,
        "share_first_round": not get_paradigm(run.config.paradigm).opinions_allowed(round_idx),
        "fact_candidate": {f.id: f.candidate_id for f in scenario.facts},
        "fact_signed_weight": {
            f.id: f.weight if f.valence == "pro" else -f.weight for f in scenario.facts
        },
    }


async def _call(
    client: LLMClient, run: RunState, system: str, user: str, meta: dict[str, Any]
) -> LLMResponse:
    return await client.complete(
        LLMRequest(system=system, user=user, model=run.config.model, meta=meta)
    )


async def run_round(store: Store, client: LLMClient, run_id: str, round_idx: int) -> RunState:
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(f"unknown run {run_id}")
    if run.status in ("done", "error") or round_idx < run.current_round:
        return run
    if run.status == "queued":
        store.set_status(run_id, "running")
        run.status = "running"

    cfg = run.config
    scenario = run.scenario
    spec = get_paradigm(cfg.paradigm)
    agent_ids = [a.id for a in scenario.agents]
    n_agents = len(agent_ids)
    candidate_ids = {c.id for c in scenario.candidates}

    try:
        if round_idx == 0:
            # Pre-discussion private ballot: each agent votes on its own hand alone.
            pre = store.get_run(run_id) or run
            if not any(v.round == -1 for v in pre.votes):
                await collect_votes(store, client, pre, -1)
                run = store.get_run(run_id) or run
        for position, agent_id in enumerate(turn_order(run, round_idx)):
            seq = round_idx * n_agents + position
            if store.turn_exists(run_id, seq):
                continue
            run = store.get_run(run_id) or run
            heard_turns = run.turns
            common_ground = {f for t in heard_turns for f in t.cited}
            hand = list(scenario.distribution[agent_id])
            agent = next(a for a in scenario.agents if a.id == agent_id)
            system = prompts.system_prompt(scenario, cfg, agent, hand, spec)
            user = prompts.turn_message(
                scenario, cfg, round_idx, heard_turns, spec, total_rounds(run)
            )
            meta = _meta(run, "turn", agent_id, round_idx, hand)
            try:
                resp = await _call(client, run, system, user, meta)
                raw = validate.parse_json_object(resp.text)
                vt = validate.validate_turn(
                    raw,
                    hand=set(hand),
                    common_ground=common_ground,
                    candidate_ids=candidate_ids,
                    sentences_per_turn=cfg.sentences_per_turn,
                    opinions_allowed=spec.opinions_allowed(round_idx),
                )
                turn = Turn(
                    seq=seq,
                    round=round_idx,
                    agent_id=agent_id,
                    sentences=vt.sentences,
                    cited=vt.cited,
                    hallucinated=vt.hallucinated,
                    lean=vt.lean,
                    confidence=vt.confidence,
                    latency_ms=resp.latency_ms,
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                )
            except Exception as exc:  # noqa: BLE001 - one silent panelist beats a dead run
                emit(
                    "warning",
                    "agent.turn_failed",
                    runId=run_id,
                    round=round_idx,
                    agentId=agent_id,
                    reason=str(exc),
                )
                turn = Turn(
                    seq=seq,
                    round=round_idx,
                    agent_id=agent_id,
                    sentences=[],
                    cited=[],
                    hallucinated=[],
                    lean=truth.UNDECIDED,
                    confidence=0.0,
                )
            store.insert_turn(run_id, turn)
            emit(
                "info",
                "agent.turn",
                runId=run_id,
                round=round_idx,
                agentId=agent_id,
                cited=len(turn.cited),
                hallucinated=len(turn.hallucinated),
            )

        run = store.get_run(run_id) or run
        await collect_votes(store, client, run, round_idx)
        store.set_status(run_id, "running", current_round=round_idx + 1)

        fresh = store.get_run(run_id) or run
        if round_idx + 1 >= total_rounds(fresh):
            store.finish_run(run_id, compute_metrics(fresh))
    except Exception as exc:
        store.set_status(run_id, "error", error=str(exc))
        raise
    result = store.get_run(run_id)
    assert result is not None
    return result


async def _vote_once(
    store: Store, client: LLMClient, run: RunState, agent_id: str, round_idx: int
) -> None:
    cfg = run.config
    scenario = run.scenario
    spec = get_paradigm(cfg.paradigm)
    candidate_ids = {c.id for c in scenario.candidates}
    hand = list(scenario.distribution[agent_id])
    agent = next(a for a in scenario.agents if a.id == agent_id)
    system = prompts.system_prompt(scenario, cfg, agent, hand, spec)
    if round_idx < 0:
        user = prompts.alone_vote_message(scenario)
        said_lean = truth.UNDECIDED
    else:
        user = prompts.vote_message(
            scenario,
            cfg,
            round_idx,
            run.turns,
            agent_id,
            final=round_idx == total_rounds(run) - 1,
            total=total_rounds(run),
        )
        own_turns = [t for t in run.turns if t.agent_id == agent_id]
        said_lean = max(own_turns, key=lambda t: t.seq).lean if own_turns else truth.UNDECIDED
    meta = _meta(run, "vote", agent_id, round_idx, hand)
    meta["alone"] = round_idx < 0
    resp = await _call(client, run, system, user, meta)
    raw = validate.parse_json_object(resp.text)
    choice, confidence, reason = validate.validate_vote(raw, candidate_ids)
    store.insert_vote(
        run.id,
        Vote(
            round=round_idx,
            agent_id=agent_id,
            choice=choice,
            confidence=confidence,
            reason=reason or None,
            said_lean=said_lean,
        ),
    )


async def collect_votes(store: Store, client: LLMClient, run: RunState, round_idx: int) -> None:
    async def guarded(agent_id: str) -> None:
        try:
            await _vote_once(store, client, run, agent_id, round_idx)
        except Exception as exc:  # noqa: BLE001 - a missing ballot beats a dead run
            emit(
                "warning",
                "agent.vote_failed",
                runId=run.id,
                round=round_idx,
                agentId=agent_id,
                reason=str(exc),
            )

    await asyncio.gather(*(guarded(a.id) for a in run.scenario.agents))


def total_rounds(run: RunState) -> int:
    """cfg.rounds, plus a runoff round when tie_break == 'runoff' and the final
    scheduled ballot tied. Only decidable once that round's votes exist."""
    cfg = run.config
    if cfg.tie_break != "runoff":
        return cfg.rounds
    final_choices = [v.choice for v in run.votes if v.round == cfg.rounds - 1]
    if final_choices and truth._majority(final_choices) == truth.UNDECIDED:
        return cfg.rounds + 1
    return cfg.rounds


def compute_metrics(run: RunState) -> Metrics:
    scenario = run.scenario
    correct_candidate_id = truth.pooled_verdict(scenario)
    last_round = max((v.round for v in run.votes), default=-1)
    final_votes = [v for v in run.votes if v.round == last_round]
    final_tally: dict[str, int] = {}
    for v in final_votes:
        final_tally[v.choice] = final_tally.get(v.choice, 0) + 1
    chair_id = scenario.agents[0].id if scenario.agents else None
    chair_choice = (
        next((v.choice for v in final_votes if v.agent_id == chair_id), None)
        if run.config.tie_break == "chair"
        else None
    )
    majority = truth.majority((v.choice for v in final_votes), chair_choice=chair_choice)
    decisive = truth.decisive_fact_ids(scenario)
    surfaced = decisive & {f for t in run.turns for f in t.cited}
    n_agents = len(scenario.agents)
    # plurality count among decided candidates, even on a tie (2-2 of 4 -> 0.5)
    decided_counts = [n for cid, n in final_tally.items() if cid != truth.UNDECIDED]
    majority_voters = max(decided_counts, default=0)
    trajectory_rounds = sorted({v.round for v in run.votes})
    vote_trajectory: list[dict[str, int]] = []
    for r in trajectory_rounds:
        tally: dict[str, int] = {}
        for v in run.votes:
            if v.round == r:
                tally[v.choice] = tally.get(v.choice, 0) + 1
        vote_trajectory.append(tally)
    return Metrics(
        correct=majority == correct_candidate_id and majority != truth.UNDECIDED,
        correct_candidate_id=correct_candidate_id,
        majority_candidate_id=majority,
        final_tally=final_tally,
        decisive_surfaced=(len(surfaced) / len(decisive)) if decisive else 0.0,
        decisive_total=len(decisive),
        decisive_surfaced_count=len(surfaced),
        agreement=majority_voters / n_agents if n_agents else 0.0,
        hallucination_count=sum(len(t.hallucinated) for t in run.turns),
        vote_trajectory=vote_trajectory,
        vote_trajectory_rounds=trajectory_rounds,
    )


async def run_to_completion(store: Store, client: LLMClient, run_id: str) -> RunState:
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(f"unknown run {run_id}")
    while run.status in ("queued", "running") and run.current_round < total_rounds(run):
        run = await run_round(store, client, run_id, run.current_round)
    return run

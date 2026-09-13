# Hidden Profile — implementation plan

> Status: plan only. Assumes PR #1 (scaffold: Vite/React frontend, FastAPI-on-Vercel backend, Neon, Vercel
> Queues push callback, JSON telemetry) is merged into `main` — it is, at `3f62f01`. Every path below is
> relative to the repo root and either exists today or is created by this plan.

## 1. Concept and hypothesis

A panel of N LLM agents must recommend one of two job candidates, A or B. The evidence is split: **shared**
facts are in every agent's prompt, **unique** facts are in exactly one. The split is engineered so that the
shared pool alone points clearly at B, while the union of all evidence points clearly at A — Stasser &
Titus's *hidden profile* (1985). Humans famously fail this: discussion is dominated by what everyone already
knows, unique facts never surface, and the group confidently picks the wrong candidate. The tool lets a
reviewer watch a panel of LLM agents run the same gauntlet and then *tune the conditions* — number of agents,
number of discussion rounds, sentences per turn, how information is distributed, and which structural
interventions are enabled — and see when the failure appears and when it disappears.

**Hypothesis under test:** more rounds buy *agreement* faster than they buy *accuracy*. Concretely, P(group
picks A) rises slowly and sub-linearly with rounds R while vote agreement rises fast, so the modal outcome at
small R is rapid, confident consensus on B. The headline chart is **rounds vs. P(correct)** plotted against
**rounds vs. agreement** on the same axis; the gap between the curves is the finding. Secondary claim: a
cheap structural intervention (one forced info-pooling round) moves accuracy more than doubling R does.

This is not a psychology demo dressed up. It is the context-distribution problem in multi-agent LLM
orchestration: subagents hold partial context, a narrow channel (a summary, a tool result, a turn budget)
connects them, and the orchestrator's job is to get the decisive minority information across that channel.
The simulator doubles as an eval harness for orchestration designs — the "interventions" are exactly the
design choices an orchestrator author makes.

## 2. Data model

### 2.1 Neon DDL — `backend/app/db.py` (extend `SCHEMA`)

`greetings` stays (the scaffold's health path uses it). New tables:

```sql
create table if not exists scenarios (
    id           text primary key,             -- 'hiring-panel-v1'
    title        text not null,
    brief        text not null,
    facts        jsonb not null,               -- Fact[]; see docs/scenario.json
    created_at   timestamptz not null default now()
);

create table if not exists runs (
    id             uuid primary key,
    scenario_id    text not null references scenarios(id),
    config         jsonb not null,             -- RunConfig, verbatim
    distribution   jsonb not null,             -- {agentIdx: fact_id[]}, resolved from preset or grid
    status         text not null,              -- queued|running|done|error
    current_round  int  not null default 0,
    error          text,
    is_demo        boolean not null default false,
    demo_label     text,                       -- 'baseline', 'sweep-r5', ... ; null for user runs
    sweep_id       uuid,                       -- groups runs produced by one sweep request
    metrics        jsonb,                      -- Metrics, written once at status=done
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);
create index if not exists runs_demo_idx  on runs (is_demo, demo_label);
create index if not exists runs_sweep_idx on runs (sweep_id);

create table if not exists turns (
    run_id        uuid not null references runs(id) on delete cascade,
    seq           int  not null,               -- global order: round * n_agents + agent_idx
    round         int  not null,
    agent_idx     int  not null,
    sentences     jsonb not null,              -- string[] (already truncated to S)
    cited         jsonb not null,              -- fact_id[] accepted (agent actually holds them)
    hallucinated  jsonb not null,              -- fact_id[] rejected (not in the agent's slice)
    lean          text not null,               -- A|B|undecided  (in-transcript lean, not the private vote)
    confidence    real not null,
    latency_ms    int,
    input_tokens  int,
    output_tokens int,
    primary key (run_id, seq)                  -- idempotency: at-least-once delivery is a no-op
);

create table if not exists votes (
    run_id      uuid not null references runs(id) on delete cascade,
    round       int  not null,                 -- 0 = pre-discussion vote (if enabled)
    agent_idx   int  not null,
    choice      text not null,                 -- A|B|undecided
    confidence  real not null,
    reason      text,                          -- one sentence; only on the final round
    primary key (run_id, round, agent_idx)
);
```

Cached demo runs are *not* a separate store: they are ordinary rows with `is_demo = true`, written by
`backend/scripts/seed_demo.py`. Same read path, zero extra code (§8).

### 2.2 Pydantic — `backend/app/models.py` (new)

```python
Candidate = Literal["A", "B"]
Lean      = Literal["A", "B", "undecided"]
Preset    = Literal["full_information", "hidden_profile", "random_split", "siloed_by_domain", "adversarial", "manual"]

class Fact(BaseModel):
    id: str; candidate: Candidate; valence: Literal["pro", "con"]
    weight: int = Field(ge=1, le=3); domain: str; text: str

class Scenario(BaseModel):
    id: str; title: str; brief: str; facts: list[Fact]

class Interventions(BaseModel):
    pooling_round: bool = False        # round 0 is "state facts only, no opinions"
    pre_vote: bool = False             # private vote before any discussion
    domain_roles: bool = False         # persona says "you own <domain>"
    devils_advocate: bool = False      # agent 0 must argue against the majority lean
    moderator_probe: bool = False      # appended each round: "anything not yet mentioned?"

class RunConfig(BaseModel):
    scenario_id: str = "hiring-panel-v1"
    n_agents: int = Field(4, ge=2, le=8)
    rounds: int = Field(3, ge=1, le=10)
    sentences_per_turn: int = Field(2, ge=1, le=4)
    randomize_order: bool = False
    preset: Preset = "hidden_profile"
    redundancy_k: int = 1              # random_split only
    interventions: Interventions = Interventions()
    seed: int = 0
    model: str = "claude-haiku-4-5"

class TurnOut(BaseModel):            # the model's structured output, pre-validation
    sentences: list[str]; items_referenced: list[str]; current_lean: Lean
    confidence: float = Field(ge=0, le=1)
```

### 2.3 TypeScript — `frontend/src/types.ts` (new)

Mirror of the above plus the read model the UI polls:

```ts
export type Turn = { seq: number; round: number; agentIdx: number; sentences: string[];
                     cited: string[]; hallucinated: string[]; lean: Lean; confidence: number }
export type Vote = { round: number; agentIdx: number; choice: Lean; confidence: number; reason?: string }
export type RunState = {
  id: string; status: 'queued'|'running'|'done'|'error'; currentRound: number
  config: RunConfig; distribution: Record<number, string[]>
  turns: Turn[]; votes: Vote[]; metrics?: Metrics; error?: string
}
```

## 3. The bundled scenario (`docs/scenario.json`)

28 facts, 14 per candidate, weights 1–3, tagged with one of four domains (`technical`, `leadership`,
`references`, `interview`) so the *siloed* preset has something to slice on at N=4. Score of a candidate =
Σ(weight of pros) − Σ(weight of cons) over the facts in scope. The full text is in
[`docs/scenario.json`](./scenario.json); the arithmetic:

**Candidate A (Alex Rivera)** — strong but the strength is invisible to any one person.

| id | val | w | holder(s) | gist |
|----|-----|---|-----------|------|
| A1 | pro | 3 | agent 0 | shipped 2B-row ledger migration, zero downtime |
| A2 | pro | 3 | agent 1 | four mentees promoted, two now lead teams |
| A3 | pro | 2 | agent 2 | authored the postmortem process the org adopted |
| A4 | pro | 3 | agent 3 | found a silent data-loss race in 20 min in the debugging round |
| A5 | pro | 2 | agent 0 | anticipated double-spend, proposed idempotency keys unprompted |
| A6 | pro | 2 | agent 1 | back-channel: "first person I'd hire for an ambiguous problem" |
| A7 | pro | 2 | agent 2 | 40% infra cost reduction, documented and repeatable |
| A8 | pro | 1 | **shared** | maintains a small OSS migration tool |
| A9 | pro | 1 | **shared** | clear written design sample |
| A10 | con | 2 | **shared** | nervous in the panel, rambled |
| A11 | con | 2 | **shared** | has never written Go, our primary language |
| A12 | con | 1 | **shared** | 14-month last tenure |
| A13 | con | 1 | **shared** | declined the whiteboard |
| A14 | con | 1 | **shared** | no formal management experience |

**Candidate B (Brooke Chen)** — every visible signal is good; every disqualifying one is private.

| id | val | w | holder(s) | gist |
|----|-----|---|-----------|------|
| B1 | pro | 3 | **shared** | polished, confident panel performance |
| B2 | pro | 2 | **shared** | eight years of Go |
| B3 | pro | 2 | **shared** | led a team of six |
| B4 | pro | 2 | **shared** | brand-name employer |
| B5 | pro | 2 | **shared** | fast, clean take-home |
| B6 | pro | 1 | **shared** | knows the fintech domain |
| B7 | pro | 1 | **shared** | available immediately |
| B8 | con | 3 | agent 3 | 3 of 6 reports left, two named Brooke in exit interviews |
| B9 | con | 3 | agent 0 | take-home near-identical to a public blog post |
| B10 | con | 2 | agent 1 | talked over the QA engineer twice |
| B11 | con | 2 | agent 2 | "led the migration" was one of twelve contributors |
| B12 | con | 2 | agent 3 | refused to discuss an outage they owned |
| B13 | con | 1 | agent 0 | asked only about title and comp |
| B14 | con | 1 | agent 1 | third role in four years, all abrupt exits |

**Arithmetic (verified in `docs/scenario.json` against these tables):**

- Pooled: A = (3+3+2+3+2+2+2+1+1) − (2+2+1+1+1) = 19 − 7 = **+12**. B = 13 − 14 = **−1**. → **A wins by 13.**
- Shared only: A = (1+1) − 7 = **−5**. B = 13 − 0 = **+13**. → **B wins by 18.**

So the 14 shared facts constitute a coherent, confident case for B, and every one of the 14 unique facts
pushes toward A. The unique set splits 7 A-pros / 7 B-cons so the failure is not a single smoking gun a lucky
agent can drop on turn 1 — the group has to surface *several* to flip.

**Decisive-fact set** (used by the surfacing metric): the minimum-cardinality set of unique facts that flips
the shared-only verdict when added to it. Each surfaced unique fact closes the gap by its weight (an A-pro raises
A, a B-con lowers B), the shared gap is 18 in B's favour, and the unique weights are
(3,3,3,3,3,2,2,2,2,2,2,1,1 — summing to 31, hence the pooled +13 for A). Taking the heaviest first:
five (A1, A2, A4, B8, B9) close 15 and leave B ahead, six close 17 and still leave B ahead, seven close 19 and
flip it. The scenario therefore requires **7 of 14** unique facts to surface — computed at runtime from the
weights, not hard-coded, so it stays correct under manual grids and other presets.

### Presets (all resolve to the same `distribution: {agentIdx: fact_id[]}` shape)

| preset | rule |
|---|---|
| `full_information` | every agent holds all 28 facts — the control; should pick A ~always |
| `hidden_profile` | the table above; uniques round-robin to agents for N ≠ 4 |
| `random_split` | shared set kept, each unique fact to `k` random agents (seeded) |
| `siloed_by_domain` | agent *i* holds every fact in domain *i*; no shared set |
| `adversarial` | as `hidden_profile`, but agent 0's slice is shared facts minus all B-cons |
| `manual` | the checkbox grid, sent verbatim |

## 4. Agent prompt design

`backend/app/prompts.py`. All templates are pure functions of `(scenario, config, agent_idx, slice, heard)`
so they are unit-testable without an API key.

### System prompt

```
You are {name}, one of {n} interviewers on a hiring panel. {role_line}

The panel must recommend exactly one candidate: A ({a_name}) or B ({b_name}).
{brief}

EVIDENCE YOU PERSONALLY HOLD — you attended different parts of the loop, so other
panelists saw things you did not, and you saw things they did not:
{numbered fact list: "[A1] (about A, weight 3) Alex single-handedly designed ..."}

RULES
- You may only assert facts from the list above. Never invent evidence. If you want
  to reason about something you do not hold, say so as a question, not a fact.
- Every fact you state in this turn must appear in items_referenced by its id.
- Speak in at most {S} sentences, each under 40 words. Be concrete: state evidence,
  not vibes. Do not summarise the whole discussion.
- Other panelists cannot see your evidence list. If a fact of yours has not appeared
  in the transcript, they do not know it.

Respond with JSON only:
{"sentences": string[], "items_referenced": string[], "current_lean": "A"|"B"|"undecided", "confidence": 0..1}
```

`role_line` is empty unless `domain_roles` (→ "You are the panel's {domain} interviewer; you own that area.")
or `devils_advocate` for agent 0 (→ "Your assigned role is devil's advocate: argue against whichever
candidate the panel currently favours, using evidence.").

### Per-turn user message

```
Round {r} of {R}. You speak now.

TRANSCRIPT SO FAR (what the panel has actually heard):
{for each prior turn: "Round 2 — Dana: <sentences>  [cited: B8, A2]"}
(empty: "Nothing has been said yet. You speak first.")

FACTS ALREADY MENTIONED BY ANYONE: {ids or "none"}
{moderator_probe: "Moderator: before you speak — is there anything in your own notes that
 nobody has raised yet? If so, raise it now."}
{pooling_round and r == 0: "This is the information-pooling round. State evidence only.
 Do not give an opinion or a recommendation yet."}

Your turn. JSON only.
```

The "heard so far" log is the only channel between agents — this is what makes rounds meaningful and what
makes the sim a model of orchestration context-passing. It is reconstructed from `turns` rows, so a requeued
job rebuilds identical context.

### Validation / truncation (`backend/app/validate.py`)

1. Parse JSON; on failure retry once with `"Your last reply was not valid JSON. Reply with JSON only."`;
   on second failure record an empty turn with `lean = "undecided"` and log `agent.parse_failed`.
2. `sentences = sentences[:S]`, each clipped to 40 words at a word boundary.
3. Partition `items_referenced` into `cited` (ids in the agent's slice) and `hallucinated` (everything else,
   including well-formed-but-not-held ids). Hallucinated ids are dropped from the "heard" log — an agent
   cannot leak a fact it does not hold — and surfaced in the UI with a red badge plus a per-run counter.
4. Clamp `confidence` to [0,1]; coerce an unknown `current_lean` to `"undecided"`.

### Private vote prompt (after every round)

Same system prompt, fresh user message, **not** appended to the transcript and never shown to peers:

```
Round {r} is over. This is a PRIVATE ballot — no other panelist will see it.
Based on everything you hold plus everything you have heard, which candidate do you recommend?
{final round: "Give one sentence of reasoning."}
JSON only: {"choice": "A"|"B"|"undecided", "confidence": 0..1, "reason": string}
```

Private voting is the design point that lets the convergence curve be measured without the measurement
itself creating conformity pressure.

### Eager-sharer risk

An LLM told "here are 18 facts, discuss" will often dump all of them in turn 1 and trivially solve the
scenario — the failure mode that would make the whole demo vacuous. Counters, in order of effect:

- **`sentences_per_turn` (default 2, hard truncation server-side).** The dominant knob: two sentences at
  ≤40 words cannot carry eight facts, and truncation is enforced after generation so prompt compliance is not
  required.
- **Enough facts that the slice does not fit.** Each agent holds 17–18 facts; there is no turn budget at
  which dumping everything is cheap.
- **"Be concrete… do not summarise the whole discussion"** discourages list-recitation.
- **Weight is in the prompt but salience is not** — nothing tells an agent its unique facts are rare, which is
  precisely the human failure (people do not know what others don't know).
- The **pooling-round intervention is exactly the escape hatch**, which is why it is an intervention and not
  the default: the demo's point is that you must design for it.

If Haiku still dumps in pilot testing, the next lever is `sentences_per_turn = 1` as the default, then a
"mention at most 2 new fact ids per turn" rule enforced by truncating `cited` and re-clipping the sentences.

## 5. Orchestrator

**Queue job boundary: one job per round.** A whole run at N=8, R=10 is 80 sequential model calls (~2–4 s
each) — far past the 60 s `maxDuration` in `backend/vercel.json`. One job per *turn* would triple queue
round-trips and make ordering the orchestrator's problem. A round is N calls ≈ 8–30 s at N≤8, fits comfortably
under the cap with the vote calls issued concurrently, and gives the UI a natural progress unit. Each round job
enqueues the next one; the run advances by chaining.

Topic `simulation` / consumer `simulation-worker`, registered in `backend/vercel.json` alongside the existing
`greetings` trigger. Since Vercel dispatches queue triggers to the resolved entrypoint path, the callback
reuses the scaffold's `TRIGGER_PATH = "/fastapi"` dispatch in `backend/app/main.py`, branching on
`payload["kind"]`.

```python
# backend/app/orchestrator.py
async def run_round(run_id: UUID, round_idx: int, token: str | None) -> None:
    run = db.get_run(run_id)
    if run.status in ("done", "error") or round_idx < run.current_round:
        return                                   # at-least-once delivery → replay is a no-op
    cfg, scen = run.config, db.get_scenario(run.config.scenario_id)

    if round_idx == 0 and cfg.interventions.pre_vote:
        await collect_votes(run, round_idx=0)    # round 0 = pre-discussion ballot

    order = list(range(cfg.n_agents))
    if cfg.randomize_order:
        Random(cfg.seed * 1000 + round_idx).shuffle(order)

    for agent_idx in order:
        seq = round_idx * cfg.n_agents + agent_idx
        if db.turn_exists(run_id, seq):          # partial-round retry resumes mid-round
            continue
        heard = db.transcript(run_id)            # rebuilt from rows, so retries are deterministic in context
        raw, telemetry = await anthropic.turn(cfg, scen, run.distribution[agent_idx], heard, agent_idx)
        turn = validate(raw, slice=run.distribution[agent_idx], s=cfg.sentences_per_turn)
        db.insert_turn(run_id, seq, turn, telemetry)   # INSERT ... ON CONFLICT DO NOTHING
        emit("info", "agent.turn", runId=..., round=..., agentIdx=...,
             latencyMs=..., inputTokens=..., outputTokens=...,
             cited=len(turn.cited), hallucinated=len(turn.hallucinated))

    await collect_votes(run, round_idx + 1)      # N concurrent calls, gathered
    db.set_current_round(run_id, round_idx + 1)

    if round_idx + 1 < cfg.rounds:
        await queues.send("simulation",
                          {"kind": "round", "runId": str(run_id), "round": round_idx + 1},
                          idempotency_key=f"run-{run_id}-round-{round_idx + 1}", token=token)
    else:
        db.finish_run(run_id, metrics=compute_metrics(run_id))
```

**Idempotency.** Three layers: the queue idempotency key `run-{id}-round-{r}` suppresses duplicate publishes;
the `turns` primary key `(run_id, seq)` and `votes` PK `(run_id, round, agent_idx)` make duplicate writes
no-ops; the `current_round` guard makes a re-delivered whole round a cheap early return. Cost of a duplicate
delivery is at worst one wasted model call for an in-flight turn.

**Retries.** Model calls: 3 attempts, exponential backoff with jitter, on 429/5xx/timeout. If a single turn
still fails, insert a placeholder turn (`sentences: []`, `lean: "undecided"`) and continue — one silent
panelist is a better demo than a dead run. If the *round job* throws, the message is not acknowledged and
Vercel redelivers; after `deliveryCount > 3` the handler acknowledges and sets `runs.status = 'error'` with
the message, which the UI renders inline.

**Sweeps.** `POST /api/sweeps` writes one `runs` row per (R, replicate) cell — default R ∈ {1,2,3,5,8} × 3
seeds = 15 runs — all sharing a `sweep_id`, and publishes each run's round-0 job immediately. They execute
concurrently across function invocations; the sweep chart reads whatever is `done` and shows the rest as
pending. No coordinator job, so there is nothing to time out.

**Model client** (`backend/app/anthropic_client.py`): `anthropic>=0.40` added to `backend/pyproject.toml`,
`ANTHROPIC_API_KEY` from backend env only (never returned by any route), `temperature = 1.0` with the seed
folded into the system prompt as a run nonce (the Anthropic API has no seed parameter — "seeded" here means
reproducible *distribution and turn order*, not reproducible text; §11).

## 6. API surface and frontend data flow

`backend/app/main.py`, alongside the scaffold's routes:

| route | purpose |
|---|---|
| `GET /api/scenario` | the bundled scenario (facts, domains, brief) |
| `POST /api/distribution/preview` | body `RunConfig` → `{distribution, sharedOnlyVerdict, pooledVerdict, isHiddenProfile, decisiveFactCount}`; pure, no DB write — powers the live badge above the grid |
| `POST /api/runs` | create a run, publish the round-0 job, return `{runId}` |
| `GET /api/runs/{id}?since_seq=N` | run state; turns with `seq > N` only |
| `GET /api/runs/{id}/metrics` | per-round metric series |
| `GET /api/demo` | `[{label, runId, config, caption}]` — the guided tour manifest |
| `POST /api/sweeps` | create a sweep; returns `{sweepId, runIds}` |
| `GET /api/sweeps/{id}` | per-R aggregates for the headline chart |

**Polling, not SSE.** The process that writes turns is a *different* Vercel function invocation from the one
holding any browser connection, so an SSE endpoint would have to tail Postgres anyway — all the complexity of
streaming with none of the benefit, plus a long-lived connection burning `maxDuration`. The frontend polls
`GET /api/runs/{id}?since_seq=` every 1.5 s while `status !== 'done'`, appends the delta, and renders each new
turn with a client-side typewriter effect (~25 ms/char). Perceived streaming, one trivial route, and replay of
a cached run uses the identical code path with the timer driving the cursor instead of the network.

Frontend state lives in one `useRun()` hook (`frontend/src/hooks/useRun.ts`) holding `RunState` + a
`revealedSeq` cursor; components are pure functions of that. No state library — it is one reducer.

## 7. Frontend components

All under `frontend/src/components/`, added to the existing Vite app; `frontend/src/api.ts` gains the calls
above next to `getHealth`.

| component | responsibility |
|---|---|
| `ControlPanel.tsx` | N, R, S sliders, preset select, randomize-order and intervention toggles, seed, model; shows estimated calls `N×(R+1)` and rough cost/runtime; "Run live" / "Replay demo" buttons |
| `DistributionGrid.tsx` | agents × facts checkbox matrix. Pre-run: editable (preset fills it, editing switches preset to `manual`), with the live **shared-only verdict vs. pooled verdict** badge from `/api/distribution/preview`. During the run: same grid becomes the **coverage heatmap** — a cell fills when its fact is spoken, hue by round index |
| `Transcript.tsx` | streaming utterances, avatar/colour per agent, each cited fact chipped as shared (grey) or unique (amber, the ones that matter), hallucinated citations struck through in red with a tooltip |
| `VoteTrajectory.tsx` | per-round private-vote chart: stacked A/B/undecided bars + an accuracy line; plus the "if they voted now" bar at the top of the right rail |
| `SweepChart.tsx` | the headline: x = rounds, y = P(correct) and agreement as two lines with per-point replicate dots |
| `GuidedTour.tsx` | three cards — *Baseline fails* → *More rounds barely help* → *One pooling round fixes it* — each loading a cached demo run with a one-sentence caption |
| `FactInspector.tsx` | click a fact id anywhere → full text, weight, holders, whether/when it was spoken |

**Charting: hand-rolled SVG, no library.** Three chart types are needed — stacked bars, two line series, a
heatmap — and the heatmap is a CSS grid regardless. Recharts would add ~500 kB to a Vite bundle for two
`<polyline>` elements, and the scaffold's only deps are React and ReactDOM; keeping it that way is also the
honest answer to "did you scope aggressively?". Budget: ~80 lines in `frontend/src/components/charts.tsx`.

## 8. Demo mode and caching

**Why:** the deployed prototype must work for a reviewer with zero setup, zero keys, and possibly a rate-limited
backend. A live-only demo that shows a spinner and then a 429 fails the assignment outright.

**Generation.** `backend/scripts/seed_demo.py` runs the orchestrator in-process (no queue) against the real
API and writes rows with `is_demo = true`: (1) `baseline` — hidden profile, N=4, R=3, S=2, no interventions;
(2) `sweep` — R ∈ {1,2,3,5,8} × 3 seeds; (3) `pooling` — baseline + pooling round; (4) `control` — full
information. ~25 runs, ≈500 model calls, a few dollars on Haiku, run once before the demo and re-runnable.
It also writes `frontend/src/demo/cachedRuns.json` (same JSON as `GET /api/runs/{id}` returns).

**Replay.** The default landing state fetches `GET /api/demo`, loads the `baseline` run, and plays it through
the same typewriter cursor as a live run — the reviewer sees the discussion unfold rather than a wall of text,
with a speed control and a "jump to end" button. Charts render from the cached metrics immediately.

**Fallbacks, in order.** (1) Live run fails or the backend 5xx/429s → banner "Live run unavailable, showing a
cached run from {date}" and the equivalent cached run loads; the reviewer loses nothing because the cached
configuration matches what they asked for whenever one exists. (2) Backend entirely unreachable → the frontend
falls back to the bundled `cachedRuns.json`, so the deployed page is still a complete demo with the API down.
(3) `ANTHROPIC_API_KEY` unset → `POST /api/runs` returns 503 with `{"reason": "demo_only"}` and the UI hides
"Run live" instead of offering a button that fails.

## 9. Metrics

Let *U* = unique facts (held by exactly one agent), *D* = the decisive set (§3, computed as the minimum-weight
set of uniques that flips the shared-only verdict), *S(r)* = fact ids validly cited in rounds ≤ *r*,
*v<sub>i</sub>(r)* = agent *i*'s private vote after round *r*, *N* = agent count.

- **Unique surfacing** `U(r) = |S(r) ∩ U| / |U|`
- **Decisive surfacing** `D(r) = |S(r) ∩ D| / |D|` — the one that should predict accuracy
- **Redundancy of discussion** `R(r) = (# citations of shared facts) / (total citations)` in rounds ≤ *r*;
  the classic finding is that this stays high
- **Fraction correct** `C(r) = |{i : v_i(r) = A}| / N`
- **Group verdict** = plurality of `v_i(R)`, ties → `undecided`; **run is correct** iff it equals A
- **Agreement** `1 − H(r)/log 3` where *H* is Shannon entropy over {A, B, undecided} of the round-*r* votes —
  1.0 is unanimity regardless of which way
- **Mean confidence** `(1/N) Σ conf_i(r)`; **overconfidence** = mean confidence among agents voting B
- **P(correct | R)** = (# correct runs) / (# runs) over the sweep replicates at that R, with a Wilson 95%
  interval (n = 3–5, so the interval is the honest presentation)
- **Hallucinated-citation rate** = rejected ids / total ids proposed, per run — a hygiene metric for the
  transcript and a real finding if it rises with transcript length

Accuracy and agreement are always plotted as separate series precisely so that "fast consensus on the wrong
answer" — high agreement, low accuracy — is visible at a glance.

## 10. Build plan

MVP cut line after Phase 3. Phase 1 alone is demoable end-to-end (real agents, real transcript, real verdict).

| # | phase | work | est |
|---|---|---|---|
| 1 | **Vertical slice** | scenario JSON + loader, `models.py`, `prompts.py`, `validate.py`, synchronous `POST /api/runs/sync` (no queue), bare transcript + verdict in the UI | 35 min |
| 2 | **Persistence + async** | DDL in `db.py`, queue topic + round-chaining orchestrator, `GET /api/runs/{id}?since_seq=`, polling hook, typewriter transcript | 30 min |
| 3 | **The point** | private votes, distribution grid + preview verdict badge, coverage heatmap, vote-trajectory chart, presets | 35 min |
| — | **— MVP cut line —** | *a reviewer can watch the failure happen and see why* | **~1h40** |
| 4 | **Sweep** | `POST /api/sweeps`, aggregate route, headline rounds-vs-P(correct) chart | 25 min |
| 5 | **Demo cache** | `seed_demo.py`, `GET /api/demo`, replay path, bundled-JSON fallback | 25 min |
| 6 | **Interventions** | pooling round, pre-vote, moderator probe (ranked below) + guided tour cards | 25 min |
| 7 | **Polish** | fact inspector, hallucination badges, cost/runtime estimates, README + rationale doc | 30 min |

**Intervention ranking** (build in this order; each is ~5–10 min once the toggle plumbing from Phase 6 exists):
1. **Structured pooling round** — biggest expected effect, cleanest story, directly maps to an orchestrator
   design ("make subagents dump context before they argue").
2. **Moderator probe** — near-zero cost, one appended line, and tests whether a *prompt* can substitute for
   *structure*. The expected answer is "only partly", which is the interesting result.
3. **Pre-discussion private vote** — anchors agents to their own evidence before conformity sets in; also
   gives the vote chart an *r*=0 baseline point for free.
4. **Domain roles / ownership** — makes unique facts feel like the holder's job to raise.
5. **Devil's advocate** — most likely to be theatre rather than information transfer; last.

Deployment is free — both Vercel projects already auto-deploy from `main`; only `ANTHROPIC_API_KEY` needs
adding to `agent-simulator-api`'s env, and the `simulation` topic to `backend/vercel.json`.

## 11. Risks and mitigations

| risk | mitigation |
|---|---|
| **Vercel 60 s function cap** | round-scoped jobs (§5): N≤8 sequential turns + N concurrent votes ≈ 30 s worst case. If pilot timings exceed ~40 s, split at half-rounds — the `(run_id, seq)` resume logic already supports it without changes. |
| **Cost / rate limits** | Haiku for panelists; a run is `N×(R+1)` calls (default 4×4 = 16, ≈1 k output tokens); the UI shows the call count before you run; sweeps capped at 25 runs; demo replay is the default so idle reviewers cost nothing. |
| **Non-determinism** | the Anthropic API has no seed, so the seed fixes distribution, turn order, and sweep composition only. Never claim a single run is reproducible: report 3–5 replicates per cell with Wilson intervals, and make the sweep, not a single transcript, the evidence. |
| **Agents trivially solve it** (eager sharing) | §4: hard truncation at S sentences, slices too large to dump, no salience cue. If they still solve it at S=2, drop the default to S=1 and cap new fact ids per turn — and if they *still* solve it, that is itself a publishable result for the write-up, contrasted against the human baseline. |
| **Agents fail it for the wrong reason** (can't do arithmetic) | the final vote prompt asks for a recommendation, not a score; the control preset (`full_information`) is the guard — if agents don't pick A with everything in front of them, the failure is reasoning capacity, not information distribution, and the whole sweep is uninterpretable. Run the control first, every time. |
| **Hallucinated facts** | validated against the holder's slice, dropped from the heard-log, flagged in the UI, counted as a metric. A fact an agent doesn't hold can never propagate. |
| **Unlucky live demo** | cached runs are the default view; live is opt-in with cached fallback (§8). |
| **Neon cold start / connection limits** | psycopg3 over Neon's *pooled* URL (already the scaffold's convention in `backend/.env.example`); every handler opens and closes one short-lived connection. |
| **Scope creep** | MVP cut line is explicit and after Phase 3; Phases 4–7 are independently droppable and each leaves the app working. |

## 12. Rationale hooks

- **The non-obvious move is measuring agreement and accuracy separately.** Everyone building multi-agent
  systems measures convergence and treats it as progress. This sim shows convergence rising *faster* than
  accuracy — the group gets confident and wrong before it can get right — which is exactly the failure signature
  you cannot see if you only log "did the agents agree?".
- **This is an orchestration eval, not a psychology toy.** Subagents with partial context and a narrow
  channel between them *are* the hidden profile setup. Every knob here is an orchestrator design decision:
  turn budget = context-window rationing, pooling round = forced context sync, shared log = the blackboard.
- **The key design tension is the turn budget.** Give agents unlimited tokens and they dump everything, the
  paradigm collapses, and you learn nothing; make the channel too narrow and nothing ever transfers. The
  interesting regime is narrow-but-not-hopeless, which is why `sentences_per_turn` is the first knob and is
  enforced by truncation rather than by asking politely.
- **Private voting is what makes the measurement honest.** Public votes would let the measurement itself
  create conformity; the convergence curve would then be an artefact of the instrument.
- **Cheap structure beats expensive compute.** The predicted headline is that one pooling round outperforms
  tripling the number of rounds — i.e. you should spend your orchestration budget on protocol design, not on
  more agent-turns. That is a directly transferable recommendation.
- **Self-containment is a design constraint, not packaging.** Caching seeded runs in Postgres and bundling a
  JSON fallback means the deployed page demonstrates the idea with the model API down — and the same cache is
  what makes the multi-run sweep affordable at all.
- **Validated citations turn a vibes demo into an instrument.** Because every claim is checked against the
  speaker's slice, "was this fact surfaced?" is a measurable event, which is what makes the coverage heatmap
  and every metric in §9 possible.
- **Extensions worth naming:** heterogeneous models per seat (does one strong agent rescue a weak panel, or
  just dominate it?); an adversarial seat that withholds; a budget-constrained moderator that must choose
  which agent to query next; and replacing the free-form transcript with a structured shared scratchpad to
  measure how much of the effect is the channel format rather than the information split.

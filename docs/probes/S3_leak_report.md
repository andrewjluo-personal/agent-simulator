# S3 — source of the null-pool candidate prior (leak #2)

Model `claude-haiku-4-5`, naive prompt, memo fact style, one seed per sample. All
Anthropic calls via workload identity (`backend/app/anthropic_auth.py`, no API key).
Probe: `backend/scripts/probe/leak_null.py`; gate: `backend/scripts/gate_null.py`.
Total spend ≈ $0.82 across all runs below.

## 0. Two different "hiring-panel-null" pools

The S2 Sally result (alone 107/120, pooled 10/10) was measured on the 31-item JSON
pool `backend/scripts/probe/pools/hiring-panel-null.json` ("S2 pool"). The in-code
`HIRING_PANEL_NULL` in `app/samples.py` is a different object: 64 twin items, every
item present once per candidate with pronouns swapped ("twin pool"). They leak in
opposite directions for different reasons, so they are reported separately.

## 1. Conditions 1–4 (10 samples/cell, alone cells 10 per agent; ≈ $0.20)

### Twin pool (original brief + blurbs)

| condition | pooled | alone (5 agents) |
|---|---|---|
| blurb_only (empty hands) | John 10/10 | John 25/25 (5/agent) |
| pooled_base / alone_base | John 10/10 | John 50/50 |
| items_swapped (items re-attributed) | John 10/10 | — |

Every ballot reason quotes the blurb:

> "Eight years of Go experience with direct payments team leadership is more aligned
> with the senior backend role on a payments team than Sally's six years of Python/Java
> on data platforms." (blurb_only, pooled)

Source: the brief ("senior backend role on a payments team") matched John's blurb
("Go … team lead at a payments company") and not Sally's. Items cancel by construction,
so the blurb/brief asymmetry is the whole signal → John 100%.

### S2 31-item pool

| condition | pooled | alone |
|---|---|---|
| pooled_base / alone_base | Sally 9/10 | Sally 45/50 (dana 5/5) |
| items_swapped (items → other candidate) | **John 8/10** | **John 39/50** |
| full_mirror (items + blurbs swapped) | John 7/10 | — |

The vote follows the items, not the names. The S2 pool is not a null: Sally's
"incident review / runbook / owns the worst service" items and John's "no tests /
couldn't explain concurrency" items are weighted far more heavily holistically than
the per-item neutral ratings implied.

> "John's inability to explain his concurrency choices and incomplete take-home
> documentation are red flags for a senior role, while Sally demonstrates thoughtful
> design practices …" (S2 pool, alone priya with tom's persona)

## 2. Conditions 5–7

### 5. Persona swap — S2 pool (5 samples per agent × persona, ≈ $0.18 incl. 6–7)

All 25 cells (each agent's hand under each other persona and a neutral "You are a
panelist" persona): Sally 4/5 or 5/5 in every cell; worst case priya←omar Sally 3/5.
Persona text carries no measurable prior; dana's earlier 11/24 is not reproduced here.

### 6. Candidate order reversed (Sally listed first), 10 samples/cell (≈ $0.11 twin)

| pool | pooled | dana | marcus | priya | tom | omar |
|---|---|---|---|---|---|---|
| twin (original blurbs) | J6/S4 | J6/S4 | J3/S7 | J2/S8 | J2/S8 | S10 |
| S2 | S10 | S9/J1 | S10 | S10 | S9/J1 | S10 |

On the twin pool, reversing order moves John 100% → Sally 4–10/10: a strong
**position** effect competing with the blurb prior. On the S2 pool the item content
dominates either way.

### 7. Neutral names (Candidate A/B, neutral pronouns), 10 samples/cell

| pool | blurb_only | pooled | alone cells |
|---|---|---|---|
| twin (A = ex-John, listed first) | A 10/10 | A 10/10 | A 10/10 in all five |
| S2 (B = ex-Sally's items) | A 10/10 | **B 10/10** | B 48/50 (dana A2/B8) |

Twin: A wins everywhere, but A is both the blurb-favoured and the first-listed
candidate, so names alone are not separated here (resolved in §3). S2: with no names
the vote still goes to whoever holds Sally's items → item content, not gender/name.

## 3. Fix and re-measurement (twin pool)

Fix (commit `1e2bb4e`): identical blurbs ("Seven years of backend engineering;
currently a senior engineer on a platform team") and a domain-neutral brief for
`HIRING_PANEL_NULL` only; `RunConfig.candidate_order` knob (`fixed|reversed|random`)
threaded through `prompts.ordered_candidates` (fixed output byte-identical).

### 3a. Symmetric blurbs, fixed John-first order (10 samples/cell, ≈ $0.12)

| condition | pooled | dana | marcus | priya | tom | omar |
|---|---|---|---|---|---|---|
| pooled_base (John first) | John 10/10 | | | | | |
| cand_order (Sally first) | Sally 9/10 | S10 | S9/U1 | S10 | S8/J1/U1 | S10 |
| neutral_names (A first) | A 10/10 | A10 | A7/U3 | A10 | A7/U3 | A8/U2 |

With blurbs symmetric, the residual prior is almost entirely **position: the
first-listed candidate wins ~95%**, regardless of name. The reasons confabulate a
difference between identical hands and assign the favourable reading to the first
candidate:

> John first: "John's closing questions focused on on-call and incidents … while
> Sally's closing questions focused solely on compensation." (pooled_base)
>
> Sally first: "Sally's closing questions focused on technical concerns (on-call,
> incidents) versus John's focus on compensation." (cand_order, alone omar)
>
> Neutral names, empty hands: "Both candidates appear identical … so I'm selecting
> cand_a arbitrarily." (neutral_names blurb_only)

### 3b. `gate_null.py`, `--order random` (10 samples × 2 seeds; ≈ $0.10) — FAIL

pooled Sally 0.85 [0.64,0.95]; dana/marcus/priya/tom 0.65; omar 0.70. Cause: the
per-seed shuffle happened to list Sally first in 13/20 seeds; the vote tracked order.
A random shuffle at n=20 does not counterbalance position.

### 3c. `gate_null.py`, `--order balanced` (default; even samples fixed, odd reversed), 10 × 2 seeds; ≈ $0.10 — PASS

```
[naive order=balanced] target=sally band=[0.35,0.65]
  pooled   n=20  sally_rate=0.65 [0.43,0.82]  by_order=fixed={john:7,sally:3} reversed={sally:10} ok
  dana     n=20  sally_rate=0.50 [0.30,0.70]  by_order=fixed={john:10}         reversed={sally:10} ok
  marcus   n=20  sally_rate=0.50 [0.30,0.70]  by_order=fixed={john:8,undecided:2} reversed={sally:10} ok
  priya    n=20  sally_rate=0.55 [0.34,0.74]  by_order=fixed={john:9,sally:1}  reversed={sally:10} ok
  tom      n=20  sally_rate=0.45 [0.26,0.66]  by_order=fixed={sally:1,john:8,undecided:1} reversed={sally:8,undecided:2} ok
  omar     n=20  sally_rate=0.50 [0.30,0.70]  by_order=fixed={john:10}         reversed={sally:10} ok
  -> PASS
```

Alone and pooled are all within 35–65% Sally. The `by_order` column shows the
position prior is not removed, only cancelled: under fixed order the first-listed
candidate still wins 8–10/10. Pooled at 0.65 sits on the band edge.

## 4. Conclusions

1. **Twin pool leak = brief/blurb domain mismatch** (John 100%). Fixed by symmetric
   blurbs + neutral brief.
2. **Residual = candidate position**, ~95% first-listed with identical hands; names /
   gender and persona text contribute nothing measurable once blurbs are symmetric.
   Runs must counterbalance order (`candidate_order` knob; gate uses `balanced`).
   A single fixed order is a ~±45pt bias on any close scenario.
3. **S2 31-item pool is not a null** (item content leak, Sally ~90%, flips with the
   items). It should not be used as a control; re-selection needs a whole-hand
   (holistic) check, not per-item ratings. Left unchanged, documented here.
4. `gate_null.py hiring-panel-null` (naive prompt, balanced order, 10 × 2 seeds)
   is the required null gate alongside `gate_pool.py`.

Not changed: `hiring-panel-flat-v2` items, `Scenario.source`, paper scenarios,
frontend, production seeding.

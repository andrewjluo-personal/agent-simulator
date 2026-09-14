# S4 — `hiring-panel-flat-v3`: a type-balanced hidden profile for Haiku

Model `claude-haiku-4-5`, memo fact style, single-agent ballots via `scripts/gate_pool.py`
(v3) and `scripts/gate_null.py` (v3 twin null), seeds 0–7, one sample per seed (n = 8 per
cell). Raw outputs: `docs/probes/data/s4/`. Total spend ≈ $0.85 across 9 runs (8 kept).

Verdict: **naive prompt PASSES the certificate; default prompt FAILS on one agent
(priya 6/8 = 75% < 80%)**. The v3 twin null is position-balanced at the agent level but the
pooled reviewer keeps a residual Sally lean (75–88%) that is *not* position.

## 1. Design

Rules from the brief: symmetric brief/blurbs (S3's `HIRING_PANEL_NULL` ones, verbatim);
shared set has the SAME type×sign histogram for John and Sally (John leads only by
strength/weight); every unique is Sally-positive and of a type in which John already holds
shared pros. 35 items, 28 shared + 7 unique, 5 agents, same personas as flat-v2.

Shared histogram (identical for both candidates): credential 2 pro / 1 con, behavioural
3/1, rigour 2/1, teamwork 1/1, communication 1/1. Truth scores: shared John 7 / Sally 1;
pooled John 7 / Sally 15; every agent hand → John (7 vs 3 or 5).

| id | cand | type | sign | w | owner(s) | memo |
|---|---|---|---|---|---|---|
| VJ1 | john | credential | pro | 1 | shared | Seven years of backend work, five on high-throughput services. |
| VJ2 | john | credential | pro | 1 | shared | Holds a current cloud architecture certification. |
| VJ3 | john | behavioural | pro | 2 | shared | Led a production outage response; service restored in under twenty minutes. |
| VJ4 | john | behavioural | pro | 2 | shared | Volunteered to own the least popular service and halved its page rate in a quarter. |
| VJ5 | john | behavioural | pro | 1 | shared | Has run his team's weekly incident review for the past year. |
| VJ6 | john | rigour | pro | 2 | shared | Found the planted bug and added a regression test before fixing it. |
| VJ7 | john | rigour | pro | 1 | shared | Design answer called out idempotency of retries unprompted. |
| VJ8 | john | teamwork | pro | 1 | shared | Two mentees promoted within two years. |
| VJ9 | john | communication | pro | 1 | shared | Answered every behavioural question concisely and directly. |
| VJ10 | john | credential | con | 1 | shared | One of his last three roles lasted under eighteen months. |
| VJ11 | john | behavioural | con | 1 | shared | Missed one sprint deadline last year when a library he owned shipped late. |
| VJ12 | john | rigour | con | 1 | shared | Take-home README omits setup instructions. |
| VJ13 | john | teamwork | con | 1 | shared | Started answering before one interviewer finished the question. |
| VJ14 | john | communication | con | 1 | shared | Closing questions were about title and compensation only. |
| VS1 | sally | credential | pro | 1 | shared | Seven years of backend work on internal platform services. |
| VS2 | sally | credential | pro | 1 | shared | Completed an online distributed-systems course last year. |
| VS3 | sally | behavioural | pro | 1 | shared | Took part in two cross-team incident reviews. |
| VS4 | sally | behavioural | pro | 1 | shared | Picked up maintenance of a small internal service when its owner left. |
| VS5 | sally | behavioural | pro | 1 | shared | Attends her team's weekly incident review. |
| VS6 | sally | rigour | pro | 1 | shared | Found the planted bug in the debugging round within the allotted time. |
| VS7 | sally | rigour | pro | 1 | shared | Design answer included a short section on logging and metrics. |
| VS8 | sally | teamwork | pro | 1 | shared | Reviews new hires' first pull requests on her team. |
| VS9 | sally | communication | pro | 1 | shared | Design sample is organised into numbered sections. |
| VS10 | sally | credential | con | 2 | shared | Most recent tenure was fourteen months. |
| VS11 | sally | behavioural | con | 1 | shared | Take-home submitted a day late without warning the recruiter. |
| VS12 | sally | rigour | con | 2 | shared | One take-home edge-case test fails; flagged as known in her notes. |
| VS13 | sally | teamwork | con | 1 | shared | Reference: sat on a blocking bug for a week before telling anyone. |
| VS14 | sally | communication | con | 2 | shared | Paused before two panel answers and restarted one. |
| VU1 | sally | behavioural | pro | 2 | dana | Rolled back a bad deploy within ten minutes using a runbook she wrote. |
| VU2 | sally | rigour | pro | 2 | marcus | Also located a race condition causing silent data loss that was not part of the exercise. |
| VU3 | sally | rigour | pro | 2 | priya | Her take-home included a load-test script and results for the hot path. |
| VU4 | sally | behavioural | pro | 2 | tom | Named lead on a two-billion-row ledger migration with no recorded downtime. |
| VU5 | sally | teamwork | pro | 2 | omar | Brokered an API contract between two teams blocked on each other for a month. |
| VU6 | sally | behavioural | pro | 2 | dana | Lowest repeat-page rate on her team; wrote the post-mortem template. |
| VU7 | sally | rigour | pro | 2 | omar | Spotted a single point of failure in the reference architecture the interviewer had missed. |

Tests: `test_flat_v3_shared_type_sign_balance`, `test_flat_v3_uniques_type_matched_by_john_shared_pros`,
`test_flat_v3_null_mirrors_every_v3_item` (`backend/tests/test_samples.py`).

## 2. Candidate order: a prior larger than name

`RunConfig.candidate_order` now has three values. `fixed` (default, byte-identical to before),
`random` (S3's seeded shuffle), and `alternate` (even seed → scenario order, odd → reversed),
so 8 seeds give exactly 4 John-first / 4 Sally-first per cell. The seeded `random` shuffle
puts Sally first on 6 of seeds 0–7, which is why it was replaced for the gate.

The v3 twin null (every v3 item once per candidate, pronouns swapped, all neutral) makes the
position effect plain (Sally votes out of 8, Wilson 95% CI):

| order | prompt | cells | in [0.35, 0.65]? |
|---|---|---|---|
| random (6/8 Sally-first) | naive | pooled 8/8 [0.68,1.00]; dana 7/8 [0.53,0.98]; marcus 6/8 [0.41,0.93]; priya 7/8 [0.53,0.98]; tom 5/8 [0.31,0.86]; omar 7/8 [0.53,0.98] | FAIL |
| random | default | pooled 7/8 [0.53,0.98]; dana 7/8 [0.53,0.98]; marcus 6/8 [0.41,0.93]; priya 7/8 [0.53,0.98]; tom 6/8 [0.41,0.93]; omar 7/8 [0.53,0.98] | FAIL |
| fixed (John first) | naive | pooled 5/8 [0.31,0.86]; dana 2/8 [0.07,0.59]; marcus 0/8 [0.00,0.32]; priya 6/8 [0.41,0.93]; tom 1/8 [0.02,0.47]; omar 6/8 [0.41,0.93] | FAIL |
| fixed | default | pooled 1/8 [0.02,0.47]; dana 0/8 [0.00,0.32]; marcus 0/8 [0.00,0.32]; priya 4/8 [0.22,0.78]; tom 0/8 [0.00,0.32]; omar 2/8 [0.07,0.59] | FAIL |
| alternate (4/4) | naive | pooled 7/8 [0.53,0.98]; dana 5/8 [0.31,0.86]; marcus 4/8 [0.22,0.78]; priya 6/8 [0.41,0.93]; tom 6/8 [0.41,0.93]; omar 6/8 [0.41,0.93] | pooled/priya/tom/omar FAIL |
| alternate | default | pooled 6/8 [0.41,0.93]; dana 4/8 [0.22,0.78]; marcus 4/8 [0.22,0.78]; priya 6/8 [0.41,0.93]; tom 5/8 [0.31,0.86]; omar 3/8 [0.14,0.69] | pooled/priya FAIL |

Reading: on identical evidence, single agents vote the first-listed candidate almost 1:1
(fixed → John 0–2/8; alternate → dana/marcus exactly 4/8 with even seeds John, odd Sally).
Once balanced, the agent cells sit at 3–6/8 (mostly inside the band) — but the **pooled
reviewer still votes Sally 6–7/8 with John listed first on 3 of the 4 John-first seeds**.
That residual (~+25 pt Sally with 70 items in hand) is not position and not the items'
valence; it is left for S3's null work (candidate: recency of the trailing memo block, or a
persona effect in the pooled reviewer prompt). The v3 null therefore does **not** meet the
35–65% band at the pooled level, and priya/tom/omar naive cells are at the top edge.

## 3. Gate iterations (v3, John listed first on even seeds under `alternate`)

Certificate: pooled reviewer → Sally ≥ 80%; each agent alone → John ≥ 80%.
"(a/b)" = John votes on John-first / Sally-first seeds.

| iteration | prompt | pooled→Sally | alone→John per agent (Wilson 95% CI) | result |
|---|---|---|---|---|
| it1 — 8 uniques incl. 3 John-con (VU6–8), order=random | naive | 8/8 [0.68,1.00] | dana 8/8 [0.68,1.00]; marcus 7/8 [0.53,0.98]; priya 7/8 [0.53,0.98]; tom 6/8 [0.41,0.93]; omar 1/8 [0.02,0.47] | FAIL |
| it1 | default | 8/8 [0.68,1.00] | dana 8/8; marcus 2/8 [0.07,0.59]; priya 5/8 [0.31,0.86]; tom 4/8 [0.22,0.78]; omar 1/8 [0.02,0.47] | FAIL |
| it2 — 7 Sally-pro uniques (marcus/tom two each), sharper VS11/VS13, order=random | naive | 8/8 | dana 8/8; marcus 7/8; priya 8/8; tom 7/8; omar 8/8 | PASS |
| it2 | default | 8/8 | dana 8/8; marcus 6/8 [0.41,0.93]; priya 6/8 [0.41,0.93]; tom 8/8; omar 7/8 | FAIL |
| it2 re-gated with order=alternate | naive | 8/8 | dana 8/8; marcus 5/8 [0.31,0.86]; priya 8/8; tom 6/8 [0.41,0.93]; omar 8/8 | FAIL |
| it2 (alternate) | default | 8/8 | dana 7/8; marcus 7/8; priya 6/8 [0.41,0.93]; tom 7/8; omar 7/8 | FAIL |
| **it3 (final)** — uniques re-dealt: dana VU1+VU6, marcus VU2, priya VU3, tom VU4, omar VU5+VU7; order=alternate | naive | 8/8 [0.68,1.00] | dana 8/8 (4/4); marcus 7/8 [0.53,0.98] (3/4); priya 8/8 (4/4); tom 8/8 (4/4); omar 8/8 (4/4) | **PASS** |
| it3 (final) | default | 8/8 [0.68,1.00] | dana 7/8 [0.53,0.98] (4/3); marcus 7/8 [0.53,0.98] (3/4); **priya 6/8 [0.41,0.93] (4/2)**; tom 8/8 (4/4); omar 7/8 [0.53,0.98] (4/3) | **FAIL (priya)** |

Position share of the pass: on John-first seeds every agent is 3–4/4 John in both prompts;
on Sally-first seeds 2–4/4. Of the 6 alone→Sally ballots in it3, 5 are on Sally-first
seeds — so roughly the whole gap to 100% is order, not evidence.

What moved between iterations:
- it1 → it2: the three John-con uniques ("no tests", "couldn't explain concurrency",
  "deflected outage ownership") flipped marcus/tom/omar wholesale regardless of the rest of
  the hand; omar's "four mentees vs John's two" invited a direct count. Removed; uniques are
  now Sally-pro only and non-comparable.
- it2 → it3: marcus and tom each held two strong uniques (race condition + post-mortem
  template; migration + SPOF), which Haiku fused into a "pattern". Re-dealt so the second
  unique goes to the two most John-stable agents (dana, omar).

Cost: it1 $0.09, it2 $0.09, it2-alt $0.09, it3 $0.09; nulls $0.12 + $0.11 + $0.11 (+ a
mis-seeded alternate null run, $0.11, discarded — `gate_null` originally spaced seeds by
1000 so parity never flipped; fixed to `s * samples + j`). WIF smoke call negligible.

## 4. Ballot-reason excerpts (it3, default prompt)

- pooled, seed 0 → **sally**: "Sally demonstrated stronger production impact (ledger
  migration, race condition discovery, incident prevention) and systems thinking despite
  some execution gaps; John showed solid technical skills but one tenure under 18 months and
  deadline miss raise consistency concerns."
- dana, seed 0 → **john**: "John's track record of owning unpopular work, mentoring two
  promotions, leading incident reviews, and five years on high-throughput services
  demonstrates proven senior-level impact; Sally's late submission, week-long bug delay, and
  fourteen-month tenure raise execution and communication concerns."
- tom, seed 0 → **john**: "John's production incident response (under 20 minutes), proactive
  regression testing, and demonstrated ownership of unpopular work outweigh Sally's
  concerning communication lapses (late submission, week-long bug silence) and tenure
  instability."
- priya, seed 1 (Sally first) → **sally** (the failing cell): "Sally shows stronger team
  integration (attends incident reviews, mentors new hires, picked up maintenance work) and
  proactive learning, though the late take-home submission and blocked bug concern me."
- priya, seed 7 (Sally first) → **sally**: "Sally demonstrated stronger ownership patterns
  (picked up orphaned service, reviews new hire PRs, attends incident reviews) and submitted
  a more complete take-home with load-testing, despite the late submission."

Priya's misses read Sally's *weak* shared pros (attends, reviews, picked up) as a teamwork
pattern when she is listed first, and treat Sally's sharper cons as "concerns" rather than
disqualifiers. It is the type-balance working as intended — the pattern is available to both
candidates — plus position.

## 5. Status

- `HIRING_PANEL_FLAT_V3` validation badge records the it3 default-prompt run:
  `passed: false`, pooledRightRate 1.0, aloneWrongRate dana .875 / marcus .875 / priya .75 /
  tom 1.0 / omar .875, trials 8. Naive-prompt run passes; only the default run is stored
  because the badge holds one result per model.
- Failed invariants: (1) default-prompt alone→John for priya (75%); (2) v3 twin null pooled
  cell 75–88% Sally under balanced order.
- Not changed: frontend default scenario, `Scenario.source`, `backend/app/scenarios/papers/`,
  prod seeding.

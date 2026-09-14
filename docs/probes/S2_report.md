# S2 — Ablations: does the Haiku panel's failure to reproduce Stasser depend on prompt, transcript, model, size?

Status: **rescoped to a ~10-minute sweep** at the user's request. P4 (prompt) ran at full n=20;
P5, P6 and P8 ran at n=5 each; the remaining cells (P4 no-repeat / consensus, P5 last_round,
P6 sonnet-default, P8 n3/n7 and n5-r15) were **not run**. All numbers below are from runs in
`docs/probes/data/*.jsonl` (seeds 0..n-1, scenario `hiring-panel-flat`, 5 agents / 3 rounds
unless noted, `RUN_MODE`-independent: the orchestrator is driven directly against a
`MemoryStore`). Recorded-run cost ≈ $1.94 (+ ~30 baseline calls).

Reproduce a cell: `cd backend && .venv/bin/python scripts/probe_free_discussion.py --scenario
hiring-panel-flat --prompt-style naive --transcript-visibility none --runs 5 --cell P5/none
--out ../docs/probes/data/s2_P5.jsonl`; table: `scripts/summarize_probe.py ../docs/probes/data/*.jsonl`.

Columns: *correct* = final majority is the pooled-correct candidate (Sally); *uniques cited* =
fraction of the 14 unique items spoken at least once; *% final≠spoken* = share of runs whose
final majority disagrees with the verdict of {shared items ∪ every item actually spoken}
(the "spoken-evidence tally"); *echo rN* = mean fraction of a turn's word 4-grams already used
by a different agent earlier; *pooled right* = single reviewer holding all 39 items, same
prompt/model (10 samples; 5 for Sonnet); *alone wrong* = each agent voting on its own hand.

| cell | n | correct | Wilson 95% CI | uniques cited | decisive surfaced | % final≠spoken | echo r1 | echo r2 | echo r3 | pooled right | alone wrong | est. cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P4/default (state-evidence rules) | 20 | 0.75 | [0.53, 0.89] | 0.62 | 0.57 | 0.80 | 0.02 | 0.11 | 0.37 | 0.40 | 1.00 | $0.54 |
| P4/naive | 20 | 0.95 | [0.76, 0.99] | 0.50 | 0.46 | 0.95 | 0.05 | 0.28 | 0.51 | 1.00 | 1.00 | $0.58 |
| P4/naive_no_repeat | 0 | not run | | | | | | | | | | |
| P4/naive_consensus | 0 | not run | | | | | | | | | | |
| P5/none (parallel monologue, naive) | 5 | 0.20 | [0.04, 0.62] | 0.49 | 0.46 | 0.20 | 0.03 | 0.11 | 0.13 | — | — | $0.08 |
| P5/last_round | 0 | not run | | | | | | | | | | |
| P6/sonnet-naive (claude-sonnet-4-5) | 5 | 1.00 | [0.57, 1.00] | 0.55 | 0.54 | 1.00 | 0.01 | 0.02 | 0.07 | 1.00 | — | $0.36 |
| P8/n5-r1 (naive, 1 round) | 5 | 0.40 | [0.12, 0.77] | 0.35 | 0.29 | 0.40 | 0.07 | — | — | — | — | $0.03 |
| P8/n9-r3 (naive, 9 agents via `redistribute`) | 5 | 1.00 | [0.57, 1.00] | 0.39 | 0.33 | 1.00 | 0.13 | 0.42 | 0.67 | — | — | $0.35 |
| P8/n3, n7, n5-r15 | 0 | not run | | | | | | | | | | |

Spoken-evidence verdict was **John in 56 of 60 runs** (undecided in 4, Sally in 0): in no run did
the items actually spoken add up to Sally, yet the panel voted Sally in 46/60.

## Per-cell notes

**P4 prompt.** Both prompts fail Stasser in the same direction: alone votes are 5/5 John under
both, and the discussion moves the group to Sally against the spoken tally. The naive prompt
is *more* pooled-correct (0.95 vs 0.75). The pooled-single-reviewer baseline moves with it:
default 0.40 → naive 1.00. So under the naive prompt the panel does exactly what one reviewer
with everything would do, even though only half the uniques were ever spoken; under the default
prompt the group (0.75) *beats* the pooled reviewer (0.40). Echo rises across rounds under
both prompts (naive r3 = 0.51): agents increasingly restate each other. Pre-discussion ballot
under the naive prompt was not always 5/5 John (11/20 runs 5-0, 5 runs 4-1, 4 runs 3-2) — the
naive system prompt already leaks some Sally-leaning even alone (the alone baseline was 5/5 John
on a separate sample, so this is noise around a ~0.85 John rate, not a contradiction).

**P5 transcript visibility.** Removing the transcript (each turn and ballot sees only own notes
and own statements) is the only tested condition that keeps the panel on the shared-evidence
side: 1/5 Sally, final John 4-1 in 3 runs. Uniques-cited is unchanged (0.49) — the agents *say*
the same things, they just don't hear each other — so the flip is carried by hearing, not by
speaking. Echo stays flat (0.13 at r3). This is the strongest evidence in the sweep that the
discussion channel, not private reweighting, is the mechanism. n=5 only.

**P6 model.** Sonnet 4.5 (naive) is 5/5 Sally with near-zero echo (r3 = 0.07) and a 1.00 pooled
baseline. Same failure to reproduce Stasser, without the verbatim repetition Haiku shows — so
4-gram echo is not necessary for the flip. No non-Anthropic key in env; no third model run.

**P8 size / rounds.** One round only (n5-r1): 2/5 Sally, i.e. the flip needs ≥2 rounds to
propagate. Nine agents, three rounds (n9-r3): 5/5 Sally with the *lowest* uniques-cited (0.39)
and the *highest* echo (0.67 at r3). Direction vs HiddenBench ("worse with size"): here size did
not hurt pooled-correctness on n=5 runs; it lowered coverage and raised echo but the group still
converged on Sally. n3, n7 and the 15-round cell were not run.

**P9 calibration** (`scripts/calibrate_items.py --samples 5`, Haiku rating each item 1–5 alone):
`hiring-panel-v1` unique mean 3.64 vs shared 2.17, gap **+1.46 → FAIL** (uniques are rated as far
weightier items — the v1 pool bakes in a novelty premium at the item level). `hiring-panel-flat`
unique 2.24 vs shared 2.29, gap **−0.05 → PASS**. Raw per-item tables in
`docs/probes/data/calibrate_*.txt`. The flat pool is therefore the right base for the mechanism
claim: its uniques are not intrinsically stronger, yet the group still over-weights them.

## Answer: when does the panel follow the shared-evidence tally (Stasser-like)?

In this sweep, only when it cannot hear the discussion (P5/none: 4/5 John) or has heard very
little of it (one round: 3/5 John). Every condition with ≥2 rounds of visible transcript —
naive or rules prompt, Haiku or Sonnet, 5 or 9 agents — moved the panel to the pooled-correct
candidate *against* the spoken-evidence tally (spoken verdict was John or undecided in 60/60
runs; final majority Sally in 46/60). The pooled-single-reviewer baseline tracks the prompt
(default 0.40, naive 1.00) but the group exceeds it under the default prompt, so the group
effect is not just "each agent behaves like a pooled reviewer". Hypothesis (not established
here): the flip is a hearing-side effect — a spoken unique item is weighted more than the shared
items each agent already holds, and the weighting compounds through re-statement (echo rises
0.05 → 0.51 over three rounds for Haiku), though Sonnet reaches the same outcome with almost no
verbatim echo, so restatement is a Haiku symptom rather than the necessary channel.
Discriminating test not yet run: P5/last_round (does one round of memory suffice?) and
P4/naive_no_repeat (does suppressing restatement change the outcome?). Sample sizes for P5/P6/P8
are 5; CIs are wide.

## Addendum — flat pool invalid; P5 rerun on `hiring-panel-flat-v2` + null control

**The P9 flat PASS above was a false pass.** `calibrate_items.py` compares unique-vs-shared rating
*magnitude* and discards *direction*. S1's signed `scripts/perceived_profile.py` shows Haiku reads
the pooled `hiring-panel-flat` as John, so "group Sally vs spoken-tally John" on that pool is not
evidence pooling and the novelty-premium reading in the sections above is **withdrawn** for that
pool. Everything above this line is kept as a record of the runs; use signed perceived-profile
calibration, not the magnitude gap, as the validity gate.

Rerun (naive prompt, Haiku 4.5, 5 agents / 3 rounds, 8 runs per cell, seeds 0–7, ~$1.1) on the
merged `hiring-panel-flat-v2` and on `hiring-panel-null` — a 31-item subset of flat-v2
(`backend/scripts/probe/pools/hiring-panel-null.json`) chosen so the perceived-profile pooled
tally is ≈0 (neutral rating: John +0.8 / Sally +0.8, undecided; `docs/probes/data/perceived/`).
Data: `s2v2_P5.jsonl`, `s2v2_P5null.jsonl`; table `summary_v2_P5.md`.

| cell | n | Sally | Wilson 95% CI | uniques cited | % final≠spoken | echo r1/r2/r3 | pre-vote Sally (of 40) | pooled right |
|---|---|---|---|---|---|---|---|---|
| flat-v2 / full | 8 | 1.00 | [0.68, 1.00] | 0.53 | 0.00 | 0.03 / 0.26 / 0.55 | 21 | 10/10 |
| flat-v2 / last_round | 8 | 1.00 | [0.68, 1.00] | 0.55 | 0.00 | 0.05 / 0.21 / 0.39 | 9 | — |
| flat-v2 / none | 8 | 1.00 | [0.68, 1.00] | 0.65 | 0.00 | 0.03 / 0.06 / 0.08 | 19 | — |
| null / full | 8 | 1.00 | [0.68, 1.00] | 0.41 | 0.00 | 0.04 / 0.32 / 0.56 | 36 | 10/10 |
| null / last_round | 8 | 1.00 | [0.68, 1.00] | 0.35 | 0.00 | 0.03 / 0.23 / 0.43 | 35 | — |
| null / none | 8 | 1.00 | [0.68, 1.00] | 0.52 | 0.00 | 0.02 / 0.07 / 0.08 | 36 | — |

Spoken-evidence tally was Sally in all 48 runs (no disagreement), so transcript visibility cannot be
tested for a flip here: there is nothing to flip against.

**Finding A — the null control is not null.** With item-level perceived margins ≈0 the panel still
votes Sally: alone (round-0 ballot) 107/120, pooled reviewer 10/10, final 24/24, regardless of
whether agents can hear each other. Four agents (marcus, omar, priya, tom) are Sally 24/24 alone;
dana 11/24. A candidate-level Sally prior therefore exists that no single item carries. It must live
in what item-level calibration never sees: the brief / candidate blurbs / names, or a holistic
weighting of item *types* (Sally's items are behavioural stories, John's are credentials), or the
persona lines. **Until null reads ≈50/50, flat-v2 results are not interpretable as pooling.**

**Finding B — S1's flat-v2 alone gate (John 10/10 × 5) is a seed-0 artifact.** `gate_pool.py`
builds `RunConfig(seed=0)` and the in-run round-0 ballot uses the same `system_prompt` +
`alone_vote_message`; the only differences are the seed (which sets the per-agent memo shuffle in
`_memo_lines` and the `Run nonce:` line of the naive prompt) and `max_tokens` (200 vs 600).
Round-0 Sally votes on flat-v2 by seed: **seed 0 → 1/15**, seed 1 → 3/15, seeds 2–7 → 5–9/15
(mean 0.41 over all seeds). Per agent over 24 ballots: omar 1, dana 6, marcus 10, priya 15, tom 17.
So flat-v2 passes the alone gate only under the one memo ordering the gate script happens to
sample; averaged over orderings it is roughly a coin flip, i.e. flat-v2 is *also* not a clean
hidden profile for Haiku. Fix: gate over several seeds (`--seed` sweep) and report the range.

**Leak discriminators — written, not run.** `backend/scripts/probe/leak_null.py` runs, on the null
pool with the naive prompt: (1) blurb-only ballot with empty hands, (2) items re-attributed to the
other candidate with names/blurbs unchanged (`mirror_scenario`), (3) items + blurbs swapped, (4)
each agent alone on (2). Expected reads: (1) Sally → prior is in the brief/blurbs/names; (2) still
"Sally" → attribution wording dominates; (2) flips to John with (3) still John → item-type/content
prior; (2) John but (3) Sally → name/gender prior. Not executed: the session's Anthropic calls began
returning 401 for every key mid-session (infra issue reported); ~$0.30 at 10 samples/condition.

## Not run / caveats
- Cells marked *not run* above; excerpts file was skipped for time.
- Leak discriminators (`leak_null.py`) not run — see addendum.
- No OpenAI/other key in env → no non-Anthropic model.
- `redistribute(flat, 9, seed=0)` gives one fixed deal for the n9 cell; other deals untested.
- Costs are estimated from recorded run tokens; baseline calls (~$0.10) are not itemised.

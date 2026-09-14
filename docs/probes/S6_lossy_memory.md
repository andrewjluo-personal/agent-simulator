# S6 — does lossy memory explain why Haiku groups solve HiddenBench lab-theft?

Question. HiddenBench reports post-discussion group accuracy of 0.0–0.6 on
`laboratory-theft-deduction` (GPT-4.1 0.1, Gemini-2.5-Flash 0.0, GPT-5-medium 0.03,
Gemini-2.5-Pro 0.6). Our seeded Haiku 4.5 demos were 10/10. The paper's protocol
gives each agent only the *previous round's* messages over 15 sequential rounds;
ours shows the full transcript over 3 rounds. Hypothesis: full-transcript memory +
few items means everything gets pooled, and lossy memory would restore the failure.

Method. `scripts/s2_probe.py` (free_discussion; private pre-vote at round −1; one
sequential turn per agent per round; a private ballot after every round; balanced
candidate order; `claude-haiku-4-5` via WIF; 10 groups per cell, seeds 0–9).
`transcript_visibility=last_round` shows each agent only the previous round before
its turn and only the just-finished round before its ballot — the paper's memory
model. Cell A (full, 3 rounds, default prompt) is the seeded prod demo
configuration and is not re-spent. Group-correct is majority of final ballots;
plurality of final-round `current_lean`s is reported alongside. D and E were cut
from 15 to 8 rounds after C cost $1.82.

## Results

| cell | scenario | prompt | visibility | rounds | correct (majority) | correct (plurality of leans) | pre-discussion individual accuracy | mean uniques surfaced | fixed / reversed order | cost |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- | ---: |
| A (prod demos) | lab-theft | default | full | 3 | 10/10 | — | — | — | — | (seeded) |
| B | lab-theft | default | last_round | 3 | 9/10 | 9/10 | 0/10 all four agents | 4.0 / 4 | 5/5 / 4/5 | $0.34 |
| C | lab-theft | default | last_round | 15 | 9/10 | 9/10 | 0/10 all four agents | 4.0 / 4 | 5/5 / 4/5 | $1.82 |
| D | lab-theft | default | full | 8 | 10/10 | 10/10 | 0/10 all four agents | 4.0 / 4 | 5/5 / 5/5 | $1.42 |
| E | stasser-1985-hidden | default | last_round | 8 | 0/10 | 0/10 | 0/10 all four agents | 5.3 / 12 | 0/5 / 0/5 | $1.10 |
| C-naive | lab-theft | **naive** | last_round | 15 | **5/10** | 5/10 | 0/10 all four agents | 4.0 / 4 | 2/5 / 3/5 | $1.68 |

Total spend ≈ $6.4 (over the ≈$2 brief; the per-round ballots dominate token use at
15 rounds). Raw per-run JSONL: `docs/probes/data/s6/{B,C,D,E,C_naive}.jsonl`.

## Findings

1. **Lossy memory does not reproduce the paper's lab-theft failure.** Under the
   paper's memory protocol and round count (C) the default-prompt group is still
   9/10. Discussion length alone (D) is 10/10. Every group in every lab-theft cell
   surfaced all four unique items, and every agent voted wrong before discussion,
   so the hidden profile binds individually and is pooled collectively regardless
   of memory.
2. **Stasser's 0/10 survives lossy memory** (E). Only ~5 of 12 unique items surface
   per group. Stasser fails through pooling load (12 items across 4 agents), which
   is the mechanism the paper describes; memory is not the lever.
3. **The prompt is the lever.** Switching lab-theft to the existing HiddenBench-style
   `naive` prompt (C-naive) drops the group to 5/10 — right at Gemini-2.5-Pro's 0.6
   and no longer a departure from the paper. Same facts, same memory, same rounds,
   same model; still 4/4 items surfaced and 0/10 pre-discussion accuracy. The drop
   is an *integration* failure, not a pooling failure.

## Why the two prompts diverge

The `default` prompt (evidence RULES, ≤2 sentences of ≤40 words, a forced
`current_lean` every turn, and a ballot after every round telling the agent to
"vote consistently with what you said unless something you heard changed your
mind") is itself a pooling intervention:

- *Item-level vs conclusion-level talk.* "Only assert things in your own notes …
  state evidence, not vibes" makes each turn a restatement of concrete facts, so
  under `last_round` the previous round *is* the evidence set. Under `naive`,
  agents are free to say "I agree Alpha is cleared; Beta looks likely" — the
  conclusion propagates and the supporting fact leaves the visible window after one
  round.
- *Elimination trap.* Lab-theft's shared facts frame Alpha; the four hidden items
  clear Alpha from four angles and only jointly leave Gamma. Once Alpha is cleared,
  an agent with no visible record of *which* item pointed where defaults to the
  other salient suspect. All five wrong `naive` groups converged unanimously on
  Beta, typically after a mid-run Alpha phase; e.g. seed 0, round 10: "the janitor's
  log is decisive — we cannot recommend Lab Alpha … Lab Beta's badge access records
  …", ending at round 15 with four identical "unanimous consensus on Lab Beta"
  turns. The matching `default` group (seed 0) instead restates "Lab Gamma's
  unaccounted staff member with three badge entries … Lab Alpha's code machine
  remained secured" every round from round 5 on.
- *Commitment device.* The per-turn lean and the per-round "vote consistently"
  ballot anchor an agent who has reasoned to Gamma. `naive` has no anchor, so the
  S2 echo/conformity drift pulls each group to whichever candidate the last speaker
  endorsed — hence unanimous lock-in in *every* `naive` group, half on Gamma, half
  on Beta.
- The hiring-panel framing ("interviewers", "candidates") is probably minor; the
  RULES and lean/ballot scaffolding are the active ingredients.

## Consequence

`naive` has existed since S2 as the HiddenBench-style prompt, but every seeded demo,
the S3/S4 pool tuning and cells B–E ran under `default`. The unscaffolded prompt is
the right baseline for demonstrating the hidden-profile failure; `default` is
better understood as a structured-discussion intervention alongside `share_first`.
This PR makes `naive` the `RunConfig.prompt_style` default (live runs from the
frontend send no prompt style and therefore inherit it) and adds `models.py` to the
engine-version hash so the flip invalidates existing demos. The three bench
survivors' demos are re-seeded under `naive`. Remaining gap to the paper's 0.0–0.1
for GPT-4.1 / Gemini-Flash is consistent with model capability (no Claude model
appears in the paper); one cell with a non-Claude model through this engine would
settle model vs harness.

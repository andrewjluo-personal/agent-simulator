# Do LLM panels reproduce the hidden-profile effect?

*Research brief — agent-simulator, September 2026. Model under test: `claude-haiku-4-5` ("Haiku"). All numbers are our own measurements unless attributed to a paper.*

## 1. The question

In a **hidden-profile** task the facts favouring the best option are spread thinly across group members, while the facts favouring an inferior option are known to everyone. Stasser & Titus (1985, 1987) showed that human groups fail these tasks: discussion rehearses the shared facts and the group picks the inferior option, even though pooling everyone's notes would reveal the best one. HiddenBench (Li et al., arXiv 2505.11556) built 65 such tasks for multi-agent LLMs and found that LLM groups also fall well short of a single model that sees everything.

We wanted to know three things: does an LLM panel fail the way humans do, *why* (information structure, discussion protocol, or a prior hidden in the prompt), and what changes the outcome.

## 2. What we built

A live simulation bench that runs the papers' designs rather than summarising them:

- **Scenarios** — candidates, a fact library with per-candidate valence, and a distribution matrix saying which agent holds which fact. From this the bench derives what the shared facts imply, what each hand implies, and what the full pool implies.
- **Paper library** — the reconstructed Stasser & Titus 1985 task (3 candidates × 4 members) and HiddenBench tasks converted verbatim.
- **Run engine** with the knobs the literature argues about: discussion paradigm (`free_discussion`, `share_first`), rounds, prompt style (`naive` = the paper-style prompt, `default` = adds evidence rules and a per-turn lean), transcript memory (`full`, `last_round`), candidate order, seeds, and private pre-discussion ballots.
- **Observability** — an information-flow timeline (which fact was voiced when, by whom), per-round vote trajectories, and seeded demo runs so the bench opens on real transcripts.
- **Certification harness** — scripts that decide whether a scenario *is* a hidden profile for the model under test (§3.1).

## 3. Findings

### 3.1 A scenario has to be certified against the model, not the arithmetic

Our first hand-built pools were designed by counting facts (shared facts favour John, uniques favour Sally). Haiku did not read them that way: item *type* (behavioural stories, "wrote no tests") outweighs credentials regardless of how each item rates on its own, so a pool whose items each rate ≈0 can still vote 90% one way. Every early "group beats individuals" result on those pools had to be withdrawn.

We now certify each scenario with three gates, run under balanced candidate order over seeds:

- **G1** — every agent alone, with its full hand, picks the shared-favoured (wrong) option ≥80%.
- **G2** — a pooled reviewer holding every fact picks the correct option ≥80%.
- **G0** — the scenario's *twin null* (every fact mirrored to every candidate, symmetric blurbs) reads ≈uniform alone and pooled.

Of 25 scenarios the bench served, **only three passed G1+G2**: `stasser-1985-hidden`, `hiddenbench-laboratory-theft-deduction`, `hiddenbench-company-acquisition-decision`. The rest either were solved by agents alone (G1 fail — the whole hiring-panel family, Stasser-1992 variants, seven HiddenBench tasks) or could not be solved even with everything pooled (G2 fail). The bench hides everything that fails.

### 3.2 Candidate order is a ~95% prior on close ballots

A null pool built to be perfectly symmetric still voted one way ~95% of the time. The cause is position: whichever candidate is listed first in the prompt wins (John-first → John 10/10; Sally-first → Sally 9/10; "Candidate A"-first → A 10/10). Names, gender and persona text contributed nothing measurable; the order of the memo paragraphs carries most of it. Every result on the bench is now run with an exact even split of candidate orders and reported per order. Counterbalancing cancels the prior in aggregate but not on any single ballot.

A second leak: a brief that domain-matched one candidate's blurb gave that candidate 100% on *empty* hands. Brief and blurbs must be symmetric.

### 3.3 Stasser & Titus 1985: reproduced

The reconstructed 1985 task passes G1 (100% alone→wrong for all four members) and G2 (100% naive / 83% default pooled→correct), holds under every candidate order, and **0/10 seeded Haiku groups choose the correct candidate** (5 free discussion, 5 share-first, `naive` prompt). Only about a third to a half of the 12 decisive unique facts are ever voiced. This is the Stasser mechanism: the group fails because facts never get pooled. It also survives the paper's lossy-memory protocol (0/10 with last-round-only memory, 8 rounds).

Caveat: the twin null is marginally out of band pooled (candidate "a" 50–56%), so a small residual prior toward "a" remains, and n=10.

### 3.4 HiddenBench: the prompt, not memory, decides lab-theft

HiddenBench never tested a Claude model, and the paper reports only means over 65 tasks, so we recomputed per-task numbers from its released run data.

- **Company acquisition** — paper: Gemini-2.5-Pro/Flash 1.0, GPT-5 0.73, GPT-4.1 0.6; pre-discussion accuracy 0.3–0.5 (a weak decoy by the paper's own threshold). Our Haiku groups 9/10 correct. Consistent with the paper.
- **Laboratory theft** — paper: GPT-4.1 0.1, Gemini-Flash 0.0, GPT-5 0.03, best Gemini-Pro 0.6. Our seeded Haiku groups **10/10 correct** — a departure.

Both tasks pass G1 and G2, so the divergence is not the information structure. We tested two explanations on lab-theft, 10 groups per cell with balanced order:

| cell | prompt | memory | rounds | groups correct |
|---|---|---|---:|---:|
| seeded demos | naive | full | 3 | 10/10 |
| B | default | last round only | 3 | 9/10 |
| C | default | last round only | 15 (paper protocol) | 9/10 |
| D | default | full | 8 | 10/10 |
| **C-naive** | **naive** | **last round only** | **15 (paper protocol)** | **5/10** |

- **Memory and length are not the cause.** Under the paper's exact protocol with our `default` prompt, groups still get 9/10. In every cell every agent votes wrong before discussion, and all four unique facts surface in round 1.
- **The prompt is.** Same facts, memory, rounds and model, but the paper-style `naive` prompt drops the group to 5/10 — in line with the paper's best model (Gemini-Pro 0.6) and no longer a departure. All four facts still surface; the wrong groups converge unanimously on the *other* salient suspect after eliminating the shared one. This is an integration failure, not a pooling failure.

Why the prompts diverge: `default` tells agents to "only assert things in your own notes … state evidence, not vibes", caps turns at two sentences, forces a `current_lean` every turn, and reminds them to vote consistently with what they said. Each turn therefore restates concrete facts and each agent is anchored to its own reasoning. Under `naive`, agents pass on *conclusions* ("Alpha is cleared; Beta looks likely"); the supporting fact leaves the one-round memory window and the last speaker's endorsement carries the group.

Consequence: `default` is not a neutral prompt — it is itself a structured-discussion intervention, on a par with `share_first`. The bench now runs `naive` by default, and the three survivors' seeded demos were re-recorded under it. With full transcript memory lab-theft is still 10/10 under `naive`, so the remaining gap to the paper's 0.0–0.1 for GPT-4.1 / Gemini-Flash is most plausibly model capability (the paper has no Claude model); one cell with a non-Claude model through this engine would settle model vs harness.

### 3.5 What discussion does

On the one hand-built pool that passes G1/G2 (`hiring-panel-flat-v3`, 4 panelists), group accuracy is 50–60% and tracks how many unique facts were actually voiced (≥5 cited → correct 8/9; ≤3 → wrong 5/5) — the partial-pooling mechanism Stasser described. Earlier ablations on the invalidated pools (directional only) showed the group flip is carried by *hearing* rather than speaking, needs ≥2 rounds, and does not require shared-fact repetition.

### 3.6 Method lessons

1. Validate whole hands over seeds, not per-item ratings.
2. Ship every pool with its twin null.
3. Balance candidate order exactly; report per order; even n only.
4. Symmetric brief and blurbs.
5. Treat the prompt as an experimental factor: report which prompt style every result used.
6. Stamp runs per scenario (engine + scenario hash) so tuning one pool does not invalidate another's evidence.

## 4. Future work

**Structured paradigms (unmerged PR #10).** A CI-green implementation of `exchange_then_decide`, `elicitation_moderator` (a non-voting moderator who polls for facts not yet mentioned) and `message_board`. It was parked when its demo results turned out to be on pools that were not hidden profiles. HiddenBench's own Exchange-then-Decide improved every model it tested, so this is the first thing to rebase and re-run on the certified scenarios under `naive`.

**Prompt scaffolding as the intervention.** §3.4 shows the `default` rules/lean scaffold turns a 5/10 failure into 9/10. Decompose it — evidence-only rule, sentence cap, per-turn lean, vote-consistency reminder — to find which ingredient carries the effect, and test it on Stasser, where the failure is pooling rather than integration.

**Models.** Repeat the certificate and group runs on Sonnet and on a non-Anthropic model to separate model capability from harness effects.

**Ballot design against primacy.** Test side-by-side presentation, signed-scalar ballots, and ask-twice-in-both-orders on the twin null; adopt whichever brings per-order results nearest 50/50.

**Certify the Stasser reproduction.** Shrink the residual "a" prior, run 24+ groups per paradigm, and add the 1987 unshared-critical vs unshared-consensus manipulation.

**Fix the HiddenBench import.** Item candidate/valence tags are mis-derived in places; re-derive them from the source data and re-audit the seven tasks that failed G1.

## Appendix: bench scenarios currently served

| scenario | G1 alone→wrong | G2 pooled→correct (naive \| default) | G0 twin null | seeded Haiku groups correct (naive, 3 rounds, full memory) |
|---|---|---|---|---|
| stasser-1985-hidden | 100% ×4, both prompts | 100 \| 83 | pooled "a" 50–56% (mild fail) | 0/10 |
| hiddenbench-laboratory-theft | 83–100% | 83 \| 83 | fail (γ 61% pooled, default) | 10/10 |
| hiddenbench-company-acquisition | 83–100% | 100 \| 100 | fail (C 67 / B 61%) | 9/10 |
| hiring-panel-flat-v3 | 85–100% ×4 | 100 \| 100 | pass (0.50/0.45) | 5–6/10 |

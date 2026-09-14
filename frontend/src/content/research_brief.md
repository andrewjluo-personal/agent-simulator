# Do LLM panels reproduce the hidden-profile effect? A simulation bench and what it found

*Research brief — agent-simulator, September 2026. Model under test throughout: `claude-haiku-4-5` ("Haiku"). All numbers below are our own measurements unless attributed to a paper.*

## 1. Motivation

Stasser & Titus (1985, 1987) showed that human groups systematically fail **hidden-profile** tasks: when the facts favouring the best option are spread thinly across members while the facts favouring an inferior option are shared by everyone, discussion tends to rehearse the shared facts and the group picks the inferior option — even though pooling everyone's notes would identify the best one. Two recent lines of work asked whether LLM groups behave the same way. HiddenBench (Li et al., arXiv 2505.11556) built 65 hidden-profile tasks and reported that multi-agent LLM groups also fall well short of their own full-information ceiling (best post-discussion accuracy 0.671 for Gemini-2.5-Pro, versus 0.435–0.981 when a single model sees everything). Both literatures leave open questions we wanted to work on directly: *why* groups fail (is it the information structure, the discussion protocol, or a prior baked into the prompt?), which interventions help, and whether the effect survives careful controls.

## 2. What we built

A live, inspectable simulation bench (React + FastAPI + Postgres, Anthropic via workload-identity auth, no static keys) that runs the actual experimental designs of these papers rather than summarising them:

- **Scenario model** — candidates, a fact library with per-candidate valence, a distribution matrix (which agent holds which fact), and derived ground truth: what the shared-only view implies, what each hand implies, what the pool implies. Scenario Lab lets you fork a scenario, redistribute facts, and see designed-vs-measured lean.
- **Paper library** — Stasser & Titus 1985 (3 candidates × 4 members, hidden and shared-control variants), Stasser 1992 variants, and 10 HiddenBench tasks converted verbatim.
- **Run engine with the knobs the literature argues about** — `paradigm` (`free_discussion`, `share_first`), `rounds`, `prompt_style` (`default` with evidence rules, `naive` HiddenBench-style), `fact_style` (memo vs labelled list), `transcript_visibility` (`full`, `last_round`, `none`), `candidate_order` (fixed/reversed/random/`balanced`), planted turns, seeds, pre-discussion private ballots.
- **Observability** — an information-flow timeline showing which fact was voiced when and by whom, per-round trace metrics (coverage of unique facts, echo of shared ones), Run×N comparisons, and a seeded demo set so the bench loads with real transcripts.
- **Certification harness** — scripts that decide whether a scenario *is* a hidden profile for the model under test (Section 3.1), a twin-null generator, a candidate-order gate, and probe runners with Wilson intervals.

## 3. Findings

### 3.1 "Hidden profile" has to be certified against the model, not the arithmetic

Our first pools were designed by counting facts: shared facts favour John, uniques favour Sally, pooled margin Sally +4. Haiku did not read them that way. Asking Haiku for the *perceived* valence of each item showed `hiring-panel-flat` was actually John +1.4 pooled — not a hidden profile at all — and every early "group beats individuals" result on it had to be withdrawn. Worse, per-item valence turned out not to be additive: item *type* (behavioural stories, incident reviews, "wrote no tests") dominates credentials regardless of per-item ratings, so a pool whose items each rate ≈0 can still vote 90% one way.

We therefore adopted a three-gate certificate, run under the real prompt with balanced candidate order over seeds:

- **G1** every agent alone, with its full hand, picks the shared-favoured (wrong) option ≥80%;
- **G2** a pooled reviewer holding every fact picks the correct option ≥80%;
- **G0** the scenario's *twin null* — every fact mirrored to every candidate, symmetric blurbs — reads ≈uniform alone and pooled.

Running this on all 25 scenarios the bench served (both prompts, 6–8 samples per cell, rotated candidate order): **only three passed G1+G2** — `stasser-1985-hidden`, `hiddenbench-laboratory-theft-deduction`, `hiddenbench-company-acquisition-decision`. The entire hand-built hiring-panel family, Stasser-1992 variants and seven HiddenBench tasks failed G1: Haiku agents solve them alone (e.g. hiring-panel-v1 alone-wrong rates 12/0/38/0/50% across five agents under the naive prompt). Three others failed G2 (pooled reviewer 0–50% correct). A side finding: our HiddenBench converter mis-tags item candidate/valence in places, so static margins for those tasks are unreliable in both directions. The bench now hides everything that fails.

### 3.2 Candidate order is a ~95% prior on close ballots

The cleanest "null" we could build (64 mirrored items, neutral brief, symmetric blurbs) still voted one way ~95% of the time. The cause is position: whichever candidate is listed first wins — John-first 10/10 John, Sally-first 9/10 Sally, "Candidate A"-first 10/10 A. Names, gender and persona text contributed nothing measurable. Splitting the prompt showed the effect is carried mainly by the **order of the memo paragraphs** (memo-only reversal → ~97% for the newly-first candidate; list/ballot-option reversal alone → ~90%). Before this, every "agents alone pick John" pass in our earlier work had John listed first, so part of each pass was primacy rather than evidence.

The engine now defaults to `candidate_order="balanced"` (exact even split of orders across samples and across agents within a run, per-vote order recorded), and every result is reported split by first-listed candidate. Counterbalancing cancels the prior in aggregate; it does not remove it from any individual ballot, which matters for close calls.

We also found a second, subtler leak: a brief that domain-matched one candidate's blurb ("payments team" vs "team lead at a payments company") gave that candidate 100% on *empty* hands. Brief and blurbs must be symmetric.

### 3.3 Stasser & Titus 1985: reproduced

The reconstructed 1985 task (3 candidates, 4 members) passes G1 (100% alone→wrong for all four members, both prompts) and G2 (100% naive / 83% default pooled→correct), holds under every candidate-order rotation, and in **10 seeded Haiku groups (5 free discussion, 5 share-first) 0/10 chose the correct candidate** — the Stasser group failure. Caveat: its twin null is marginally out of band pooled (candidate "a" 50–56%, band ≤48%), so a mild label/position prior toward "a" remains and n=10; we call it a promising reproduction, not a certified one.

### 3.4 HiddenBench: one task reproduced, one not — and the difference is protocol

HiddenBench never tested a Claude model (its 15 models are GPT, Gemini, Qwen3 and Llama-4), and the paper reports only means across 65 tasks; we recomputed per-task numbers from its released run data.

- **Company acquisition** — HiddenBench groups: Gemini-2.5-Pro/Flash 1.0, GPT-5-medium 0.73, GPT-4.1 0.6 post-discussion, and pre-discussion accuracy 0.3–0.5 (above the paper's own ≤20% validity threshold, i.e. a weak decoy). Our Haiku groups 10/10 correct. **Consistent with the paper.**
- **Laboratory theft** — HiddenBench groups: GPT-4.1 0.1, Gemini-Flash 0.0, GPT-5-medium 0.03, best Gemini-Pro 0.6. Our Haiku groups **10/10 correct**. **A genuine departure.**

Both tasks pass our alone/pooled gates, so the divergence is not the information structure. The likely cause is discussion protocol: HiddenBench agents speak for 15 sequential rounds but see **only the previous round's messages**, whereas our agents keep the full transcript. With ~7 facts spread over 4 agents, one mention of each unique fact is enough for a full-transcript group to pool everything and let the G2 margin decide. A lossy-memory replication (last-round-only visibility, 15 rounds, balanced order, 10 groups) on lab-theft and Stasser is running now; results will be appended here.

### 3.5 What discussion does in our runs

From the ablation series on the hiring-panel pools (before they were invalidated as hidden profiles, so directional only): groups flipped *against* the spoken-evidence tally in 46/60 runs; the flip is carried by *hearing* (no-transcript ballots 1/5 flipped) rather than by speaking; it needs ≥2 rounds; and Sonnet-4.5 flipped with near-zero echo, so shared-fact repetition is not necessary. On the one hand-built pool that does pass G1/G2 (`hiring-panel-flat-v3`, 4 panelists, every unique a hidden Sally pro), group accuracy is 50–60% and tracks how many unique facts were actually voiced (≥5 cited → correct 8/9; ≤3 → wrong 5/5) — the partial-pooling mechanism Stasser described.

### 3.6 Method lessons

1. Validate hands, not items: whole-hand ballots over seeds are the certificate; per-item ratings are a design aid.
2. Ship every pool with its twin null; a scenario is only interpretable if the twin reads ≈uniform under the same prompt.
3. Balance candidate order exactly and report per order; even n only.
4. Symmetric brief and blurbs; no domain match to either candidate.
5. Version and stamp runs per scenario so tuning one pool does not invalidate another's evidence (engine + scenario hash, canonical JSON).

## 4. Future work

**Unmerged: structured paradigms (PR #10).** A complete, CI-green implementation of three additional discussion protocols — `exchange_then_decide` (fixed fact-exchange rounds before any decision), `elicitation_moderator` (a non-voting moderator who polls each panelist for facts not yet mentioned), and `message_board` (asynchronous posting) — with a paradigm hook layer, moderator turns, a board view and `/api/paradigms`. It was parked when the scenario-validity problems in §3.1 surfaced, because its demo results (13–14/14 decisive facts surfaced, groups converging on the designed answer) were obtained on pools that turned out not to be hidden profiles. HiddenBench's own Exchange-then-Decide intervention improved every model family it tested, so this is the first thing to rebase and re-run on the certified scenarios and on the lossy-memory protocol.

**Protocol as a variable.** Make transcript memory, round count and speaking order first-class experimental factors; replicate HiddenBench's T and N ablations on Haiku; add its Reveal-All and passive-summarisation interventions as paradigms.

**Ballot design against primacy.** Test side-by-side or topic-interleaved presentation, signed-scalar ballots, and ask-twice-in-both-orders (disagreement = undecided) on the twin null; adopt whichever brings per-order results nearest 50/50.

**Certify the Stasser reproduction.** Shrink the residual "a" prior, run 24+ groups per paradigm, and add the 1987 manipulations (unshared-critical vs unshared-consensus).

**Fix the HiddenBench import.** Re-derive item candidate/valence tags from the source data so static margins can again be used as a pre-screen, then re-audit the seven tasks that failed G1.

**Models.** Repeat the certificate and group runs on Sonnet and a non-Anthropic model to see whether position primacy and the full-transcript pooling result are Haiku-specific.

## Appendix: bench scenarios currently served

| scenario | G1 alone→wrong | G2 pooled→correct (naive \| default) | G0 twin null | Haiku groups correct |
|---|---|---|---|---|
| stasser-1985-hidden | 100% ×4, both prompts | 100 \| 83 | pooled "a" 50–56% (mild fail) | 0/10 |
| hiddenbench-laboratory-theft | 83–100% | 83 \| 83 | fail (γ 61% pooled default) | 10/10 |
| hiddenbench-company-acquisition | 83–100% | 100 \| 100 | fail (C 67 / B 61%) | 10/10 |
| hiring-panel-flat-v3 | 85–100% ×4 | 100 \| 100 (20/20) | pass (0.50/0.45) | 5–6/10 |
| hiring-panel-null-v2 (control) | — | — | in band | — |

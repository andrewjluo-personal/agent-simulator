# S1 — Why Haiku panels don't reproduce Stasser: leak hunt + gate results

Status: **re-scoped**. The planned P1 planted-turn experiment (5 cells × 30 runs) was not run,
because the leak hunt and the hidden-profile gate below show the flat pool it was to run on is
not a hidden profile *for the model*. Every number here comes from runs executed in this session
(model `claude-haiku-4-5`, memo fact style, local memory store). Total spend ≈ $0.61.

Artifacts: `backend/scripts/probe/out/perceived/*.{json,md}` (leak hunt),
`backend/scripts/probe/out/gate/*.json` (gate votes).

## 1. Leak hunt — perceived vs designed valence (`scripts/perceived_profile.py`)

Every item in `hiring-panel-flat`, its mirror, and `hiring-panel-v1`; 5 samples/item; two prompts:

- **calibrate**: `{"rating": 1..5, "direction": john|sally|neutral}`, signed toward the item's candidate.
- **neutral**: item shown *as being about candidate X*, `{"score": -2..+2}` = less/more likely to recommend X.

The calibrate prompt is **not usable for direction**: memo texts without a pronoun
("Took part in two cross-team incident reviews", "Named lead on a 2B-row ledger migration…") are
attributed to the wrong candidate roughly half the time (v1 S12/S14/S15/S16/S17 all read −3..−4 under
calibrate but +1.3..+2 under neutral). The neutral prompt names the candidate and is the reference below.

### 1a. Items whose perceived sign disagrees with design (neutral prompt)

| pool | item | designed | perceived | text |
|---|---|---|---|---|
| flat, v1 | S10 | −1 (Sally con) | **+1.0** | Take-home submitted an hour before the deadline. |
| mirror | J2 | +2 (John pro) | **−1.2** | Eight years of professional Go. (mirrored to Sally, brief still asks for Go) |
| mirror | S2 | +1 | **−1.2** | Six years of Python and Java backend work. (mirrored to John) |
| mirror | J18 | +1 | **−1.0** | Two conference talks on Go service architecture. (mirrored) |

Designed-nonzero items Haiku reads as ≈0 (|mean| < 0.5): flat J11, S1, S2, S4, G2, G3, G6; v1 J11, S1, S2, S4.
Two of the eight Sally "decisive" uniques in flat (F3, F4) are perceived at +1.0/+0.6 but S1/S2/S4 Sally
shared pros are perceived at 0, i.e. Sally's shared side is weaker than designed, not stronger.

The mirror pool is broken as a control: swapping candidate names does not swap the *brief* (the role
is a Go payments role), so "eight years of Go" attached to Sally is read as a *negative* for Sally.

### 1b. Perceived tallies vs designed (neutral prompt; per-candidate sums → winner)

| pool | tally | designed | perceived (neutral) |
|---|---|---|---|
| flat | shared | John +5 / Sally −3 → John | John +6.2 / Sally −3.0 → John |
| flat | hands (5) | all John | all John (John +5.0..+7.0 vs Sally −1.0..−4.0) |
| flat | **pooled** | John +1 / **Sally +4 → Sally** | **John +4.8 / Sally +3.4 → John** |
| mirror | pooled | John +4 / Sally +1 → John | John +3.4 / Sally −5.6 → John |
| mirror | hands (5) | all Sally | 4 Sally (margins ≤ 1.6), 1 John |
| v1 | shared | John +6 / Sally −5 → John | John +6.8 / Sally −4.0 → John |
| v1 | hands (5) | all John | all John |
| v1 | **pooled** | John 0 / **Sally +4 → Sally** | **John +0.8 / Sally +4.9 → Sally** |

**Finding L1.** `hiring-panel-flat` is not a hidden profile for Haiku: the perceived pooled margin is
John +1.4, not Sally +4. John's shared strengths (J2 "eight years of Go" +2.0, J3 lead +1.0, J4 +1.2,
J6 +1.4) outweigh eight Sally uniques that each carry ≈ +1. `hiring-panel-v1` *is* a hidden profile
for Haiku (perceived pooled Sally +4.1, every hand John).

## 2. Gate — pooled-right / alone-wrong votes (`scripts/gate_pool.py`, 10 samples each)

Gate: pooled reviewer holding all items picks the designed-correct candidate ≥ 80% AND each agent alone
picks the shared-only candidate ≥ 80%.

| pool | prompt | pooled reviewer | alone (dana/marcus/priya/tom/omar) | gate |
|---|---|---|---|---|
| flat | naive | Sally 6 / John 4 | John 10/10 × 5 | **FAIL** (pooled 0.60) |
| flat | default | John 10 | John 10/10 × 5 | **FAIL** (pooled 0.00) |
| v1 | naive | Sally 10 | Sally 10/10 ×4, omar John 10/10 | **FAIL** (alone-wrong 0.0 for 4 agents) |
| v1 | default | Sally 10 | John 10/10 × 5 | **PASS** |

**Finding G1.** Flat fails under both prompts, consistent with L1 — the omniscient reviewer does not
see Sally in it (default: 0/10). The sibling-session result "groups reach Sally 6/7 on flat while
omniscient picks Sally 3/10" therefore cannot be evidence pooling; it is drift induced by the
discussion/prompt toward Sally on a pool that, item-for-item, Haiku scores for John.

**Finding G2.** v1 under the naive prompt: pooled 10/10 Sally, but 4 of 5 agents *alone* also vote
Sally 10/10 on hands whose perceived item-sum is John +5.8 vs Sally 0..−3.4. Under the default prompt
the same hands vote John 10/10. So the naive prompt makes individuals ignore the count of shared
+1 items and follow the one or two vivid Sally uniques in their hand (S12–S17 each perceived +1.3..+2).
That is "salience beats count" (F2) reproduced with n=10 per agent, and it is not a hidden-profile
effect at all — it is the individual's weighting, present before any discussion.

## 3. Verdict on H-novelty vs H-framing vs H-leak

The three hypotheses were framed to explain why *groups* on the flat pool converge on Sally against
the spoken-evidence tally. The leak hunt shows the premise is wrong: the flat pool's designed
arithmetic does not match Haiku's item-level reading (L1), so "spoken tally favours John" was measured
in a currency Haiku does not use, and the pool was not hidden-profile for the model (G1). On that
pool no group result discriminates the hypotheses. What the data do support:

- **H-leak (prompt/wording bias), partially confirmed, but the leak is not in candidate names or memo
  position** — it is the valence coding. One shared item flips sign (S10), several designed ±1 items read
  as 0, and John's shared pros read at 2–4× their designed weight. Mirroring is itself a leak: the brief
  fixes the domain, so mirrored items change sign (J2, S2, J18).
- **H-novelty (as an individual salience effect, not a social one) is supported by G2**: with the naive
  prompt each agent alone picks Sally on the strength of 1–2 vivid uniques against a perceived-larger
  sum of small shared John items. Nothing social is needed for that; the default prompt's asymmetry/
  evidence rules suppress it.
- **H-framing: untested.** The planted-turn cells (P1 a/b vs c/c′) were not run; they should be run on a
  pool that passes both gates under both prompts. `hiring-panel-v1` passes under default only.

## 4. What the harness now provides (in this PR)

- `RunConfig.prompt_style: "default" | "naive"`; `prompts.naive_system_prompt` (HiddenBench-style,
  formerly a monkeypatch in `scripts/probe/fd_probe.py`). Default prompt unchanged.
- `orchestrator.Plant` + `plants=` on `run_round`/`run_to_completion`: planted verbatim turn, moved to
  first in its round; off by default.
- `scripts/perceived_profile.py` — signed per-item perceived valence, two prompts, perceived
  shared/hand/pooled tallies vs designed. This is the calibration step Stasser-style designs need
  before any group run.
- `scripts/gate_pool.py` — pooled-right / alone-wrong gate per prompt style.
- `scripts/probe_lib.py` — Wilson CI, odds ratio (P2), 4-gram echo (P7), spoken-evidence verdict (P3),
  mirror pool, JSONL summary — ready for `probe_free_discussion.py` / `summarize_probe.py`, which were
  not finished under the re-scope.

## 5. Recommended next step (not executed)

Build `hiring-panel-flat-v2` against the *perceived* profile: keep shared as-is (perceived John +9.2
margin), replace S10, drop/replace F3/F4 and the ≈0 G items, and add Sally uniques until the perceived
pooled margin is ≥ +8 with every hand still John under the neutral prompt; then re-run `gate_pool.py`
under both prompts. Only then run P1 (a)–(d) with `--order random`. Under the naive prompt G2 says
individuals already lean Sally on v1-style uniques, so P1 must also include the `hiring-panel-null`
bias baseline before any cell is interpreted.

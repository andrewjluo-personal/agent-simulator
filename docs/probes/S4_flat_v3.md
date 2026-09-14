# S4 — hiring-panel-flat-v3: hidden profile cut from the null-v2 bank

- Model: `claude-haiku-4-5`
- Scripts: `backend/scripts/gate_pool.py` (hidden-profile gate), `backend/scripts/gate_null.py` (twin-null band check)
- Samples: n=20 per cell (10 John-first + 10 Sally-first via balanced candidate order)
- Raw data: `docs/probes/data/s4/v3_gate_{naive,default}.json`, `docs/probes/data/s4/v3_null_{naive,default}.json`
- Total S4 spend across iterations: ≈ $3.4

## Verdict

**Hidden-profile gate PASSES on both prompts.** Pooled→Sally 20/20 on naive and default, both candidate orders; alone→John ≥0.85 for every agent on both prompts.

**Null: pooled in band (0.50 naive / 0.45 default Sally); agent cells mixed.** Naive dana 0.70, marcus 0.75, tom 0.25 and default tom 0.30 fall outside the 0.35–0.65 band, with no consistent direction across prompts. Caveat: tom's null leans John (Sally 0.25 naive / 0.30 default, i.e. John 0.75/0.70) on both prompts, so tom's alone→John 1.00 is partly bank lean rather than pure hidden-profile signal. The other three agents' alone→John (0.85–1.00) exceed their null John rates (0.25–0.55) by ≥30pp — that gap is the hidden-profile signal. The bank is S3's null-v2 paraphrased bank (#32), accepted as-is per the user.

## §1 Design

All shared items favour John: the John versions of pairs J1, J3, J5, J7, F7, F14 (F7x/F14x are the John wordings of two Sally-pro pairs) plus the Sally version of S10 (a con), plus five valence-matched filler pairs (S1, S4, J9, J10, J11) held in both versions. Every unique is a hidden Sally pro, two per panelist — dana F9,F13; marcus F11,F12; priya F1,F3; tom F2,F5 — so Sally can only win if the panel pools them in discussion.

| id | cand | sign | owner | memo |
|---|---|---|---|---|
| J1 | john | pro | shared | Answered all behavioural questions fluently and concisely. |
| J3 | john | pro | shared | Listed as team lead for six engineers. |
| J5 | john | pro | shared | Take-home submitted within a day; standard Go layout. |
| J7 | john | pro | shared | Available to start in two weeks. |
| F7x | john | pro | shared | Former director calls him reliable. |
| F14x | john | pro | shared | Wrote the developer setup docs new joiners still follow. |
| S10 | sally | con | shared | Take-home submitted twenty minutes after the deadline. |
| S1 | sally | pro | shared | Design sample is organised with numbered sections and stated assumptions. |
| S1x | john | pro | shared | Design doc has clear headings and lists trade-offs up front. |
| S4 | sally | pro | shared | Closing questions were about on-call and recent incidents. |
| S4x | john | pro | shared | Closing questions were about paging frequency and the last outage. |
| J9 | john | con | shared | Take-home README omits setup instructions. |
| J9x | sally | con | shared | Take-home README does not list build dependencies. |
| J10 | john | con | shared | Closing questions were about title and compensation only. |
| J10x | sally | con | shared | Closing questions were about promotion process and remote-work policy only. |
| J11 | john | con | shared | Compensation ask at the top of the band. |
| J11x | sally | con | shared | Compensation expectation near the top of the band. |
| F9 | sally | pro | dana | Her take-home included a load-test script and results for the hot path. |
| F13 | sally | pro | dana | Has run her team's weekly incident review for the past year. |
| F11 | sally | pro | marcus | Her design sample called out the idempotency of retries explicitly. |
| F12 | sally | pro | marcus | Reference: she volunteered to own the least popular service on the team. |
| F1 | sally | pro | priya | Took part in two cross-team incident reviews. |
| F3 | sally | pro | priya | Found the planted bug in the debugging round within the allotted time. |
| F2 | sally | pro | tom | One other team has adopted her migration tool. |
| F5 | sally | pro | tom | One mentee has since been promoted. |

Truth scores (`app.truth`): shared-only John (john 5, sally −2); pooled Sally (john 5, sally 6); each hand John (john 5, sally 0). The twin null (`hiring-panel-flat-v3-null`) draws both versions of all 20 pairs (40 facts, all neutral): every hand and pooled score 0–0 / undecided.

## §2 Gate results (`v3_gate_*.json`)

Rate = shared-verdict (John) rate for alone cells, correct-candidate (Sally) rate for pooled; CI is Wilson 95%.

### naive prompt

| cell | n | counts | rate | Wilson CI | John-first | Sally-first |
|---|---|---|---|---|---|---|
| pooled | 20 | sally 20 | 1.00 | [0.84, 1.00] | sally 10/10 | sally 10/10 |
| dana | 20 | john 17, sally 3 | 0.85 | [0.64, 0.95] | john 8, sally 2 | john 9, sally 1 |
| marcus | 20 | john 19, sally 1 | 0.95 | [0.76, 0.99] | john 9, sally 1 | john 10 |
| priya | 20 | john 17, sally 3 | 0.85 | [0.64, 0.95] | john 7, sally 3 | john 10 |
| tom | 20 | john 20 | 1.00 | [0.84, 1.00] | john 10 | john 10 |

### default prompt

| cell | n | counts | rate | Wilson CI | John-first | Sally-first |
|---|---|---|---|---|---|---|
| pooled | 20 | sally 20 | 1.00 | [0.84, 1.00] | sally 10/10 | sally 10/10 |
| dana | 20 | john 19, sally 1 | 0.95 | [0.76, 0.99] | john 10 | john 9, sally 1 |
| marcus | 20 | john 20 | 1.00 | [0.84, 1.00] | john 10 | john 10 |
| priya | 20 | john 19, sally 1 | 0.95 | [0.76, 0.99] | john 9, sally 1 | john 10 |
| tom | 20 | john 20 | 1.00 | [0.84, 1.00] | john 10 | john 10 |

## §3 Null results (`v3_null_*.json`, band 0.35–0.65 Sally)

Cells report vote counts; Sally rate shown.

### naive prompt

| cell | n | counts | Sally rate | John-first | Sally-first | in band |
|---|---|---|---|---|---|---|
| pooled | 20 | john 10, sally 10 | 0.50 | j5 s5 | j5 s5 | ✓ |
| dana | 20 | john 6, sally 14 | 0.70 | j5 s5 | j1 s9 | ✗ |
| marcus | 20 | john 5, sally 15 | 0.75 | j1 s9 | j4 s6 | ✗ |
| priya | 20 | john 10, sally 10 | 0.50 | j4 s6 | j6 s4 | ✓ |
| tom | 20 | john 15, sally 5 | 0.25 | j7 s3 | j8 s2 | ✗ |

### default prompt

| cell | n | counts | Sally rate | John-first | Sally-first | in band |
|---|---|---|---|---|---|---|
| pooled | 20 | john 11, sally 9 | 0.45 | j7 s3 | j4 s6 | ✓ |
| dana | 20 | john 9, sally 11 | 0.55 | j8 s2 | j1 s9 | ✓ |
| marcus | 20 | john 9, sally 11 | 0.55 | j7 s3 | j2 s8 | ✓ |
| priya | 20 | john 13, sally 7 | 0.35 | j9 s1 | j4 s6 | ✓ |
| tom | 20 | john 14, sally 6 | 0.30 | j8 s2 | j6 s4 | ✗ |

Pooled sits at ~0.5 both prompts (in band). Tom's hand is the one persistent lean (John 0.75 naive / 0.70 default); dana and marcus lean Sally only under naive.

## §4 Ballot-reason excerpts

Alone→John (default prompt):

- dana: "John demonstrates stronger execution discipline: took home within a day with standard layout, wrote docs still used by new joiners, and his director vouches for reliability."
- marcus: "John's design doc with upfront trade-offs, reliable reference, leadership of six engineers, and rapid take-home submission demonstrate stronger senior readiness."
- tom: "John's take-home was submitted promptly with standard layout; his design doc lists trade-offs upfront; a former director vouches for reliability."

Pooled→Sally:

- naive: "Sally demonstrates stronger operational maturity through incident leadership, cross-team collaboration, mentorship impact, and thoughtful technical decisions (idempotency awareness, load testing)."
- default: "Sally demonstrated ownership (volunteering for unpopular work, mentoring), technical depth (explicit idempotency reasoning, load-testing), and on-call readiness (incident review leadership)."

## §5 Iteration history

- **it1** — 3 hidden Sally pros + 2 hidden John cons per agent (31 items): pooled→Sally 1.00 but alone→John weak — default dana .90 marcus .80 priya .60 tom .40; naive .45–.65. FAIL: the hidden ops stories overpowered the shared credentials. (`gate_v3_it1`)
- **it2** — 2 hidden Sally pros per agent, 6 shared John pros (25 items): default PASS; naive tom .70 (John-first 5/10). (`gate_v3_it2`)
- **it3** — tom's hidden pro F10→F5 (this cut): PASS on both prompts.
- **Earlier abandoned design** — hand-written VJ/VS/VU type-balanced bank whose own twin null read pooled 0.70–0.85 Sally (`gate_v3_null_*`, `null_v3_4p`); the first null-v2 cut (20 pairs) had null pooled 0.75/0.65 John and marcus/priya 0.70–0.75 Sally (`v3_nullv2cut_null_*`).

## §6 Full discussion (3 rounds, 4 panelists)

`scripts/probe_free_discussion.py --scenario hiring-panel-flat-v3 --runs 10 --candidate-order balanced`
(seeds 0–9, 5 John-first + 5 Sally-first). Raw rows: `docs/probes/data/s4/group/v3_group_{naive,default}.jsonl`.

| prompt | final Sally | Wilson95 | John-first | Sally-first | uniques cited / run | pre-vote Sally mean |
|---|---|---|---|---|---|---|
| naive | 6/10 = 0.60 | [0.31, 0.83] | 3/5 | 3/5 | 4.3 of 8 | 0.08 |
| default | 5/10 = 0.50 | [0.24, 0.76] | 3/5 | 2/5 | 4.4 of 8 | 0.02 |

Per run, the outcome tracks how many of the 8 hidden Sally pros were voiced: runs citing ≥5 went
Sally 8/9, runs citing ≤3 went John 5/5 (4 cited: 3 Sally / 3 John). Pre-discussion ballots are
~0 % Sally (matches the alone gate), so the Sally verdicts arise only through pooling — the
scenario behaves as a hidden profile under discussion, with partial pooling limiting the group
to ~50–60 % correct. Cost ≈ $0.38 per 10-run cell.

## §7 Cost

Gate run ≈ $0.15–0.16 per 2-prompt run; null run ≈ $0.17–0.19; discussion ≈ $0.38 per 10 runs.
Session total ≈ $3.4 of the $4 budget.

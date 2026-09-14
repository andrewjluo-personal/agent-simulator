# S1 handoff brief — Stasser/hidden-profile probes on Haiku panels

Repo `andrewjluo-personal/agent-simulator`, backend `backend/` (`.venv/bin/python`, `RUN_MODE=sync`,
memory store). Model `claude-haiku-4-5`. Prior session: https://app.devin.ai/sessions/17521c248cf34260ba0844a7cda58685

## State of the code

Merged in #23 (`main`):
- `RunConfig.prompt_style: "default"|"naive"` (`prompts.naive_system_prompt`; default byte-identical).
- `orchestrator.Plant` + `run_round/run_to_completion(..., plants=())` — verbatim planted turns, speaker moved first.
- `scripts/perceived_profile.py <scenario…>` — signed perceived valence per item (calibrate prompt + neutral −2..+2 prompt); trust the neutral column only.
- `scripts/gate_pool.py <scenario> --prompt naive default` — pooled reviewer ≥80% right AND every agent alone ≥80% wrong.
- `scripts/probe_lib.py` — Wilson, odds ratio, 4-gram echo, mirror, spoken verdict, summary table.
- `HIRING_PANEL_FLAT_V2` (`hiring-panel-flat-v2`): rebuilt against perceived weights; passes gate under both prompts.
- `docs/probes/S1_report.md` — all executed numbers (leak hunt, gates, v2).

On branch `devin/1789346901-s1-null-p1` (this PR, unmerged, no LLM results):
- `HIRING_PANEL_NULL` (`hiring-panel-null`): every coherent flat-v2 item appears once per candidate with pronouns swapped, all valences neutral, 64 items, designed margin 0 everywhere. Domain-locked items excluded (`_NULL_EXCLUDE` = J2 J4 J6 S2 S5 S11 F8).
- `scripts/probe_free_discussion.py` — N seeded free-discussion runs → `runs.jsonl` (one row per run: pre-votes, votes by round, uniques cited, spoken verdict, final majority, first speaker + pre-vote, echo, tokens/cost) + `<prompt>_seed<n>.txt` transcripts. `--cell a|b|c|cprime|d` = P1 presets on flat-v2 (plant texts inside the file; `dana` speaks first in round 1).
- `scripts/summarize_probe.py DIR…` — table per cell (n, final-correct + Wilson CI, pre-vote correct, P3 disagree, uniques/decisive per run, first-speaker OR, echo r2/r3, cost).
- `gate_pool.py` fix: one seed per sample (before, all 10 samples shared seed 0 → one memo ordering; this likely explains gate 10/10 John vs in-run pre-votes 1–4/5 Sally on flat-v2).
- `tests/test_samples.py::test_null_pool_is_symmetric`; null excluded from hidden-profile tests.

## Executed findings (all numbers from runs; see S1_report.md)

1. `hiring-panel-flat` is not a hidden profile for Haiku: perceived pooled John +4.8 / Sally +3.4; pooled reviewer Sally 6/10 (naive) and 0/10 (default). So its "group 6/7 Sally beats omniscient 3/10" was not pooling.
2. Leak is valence coding (designed ≠ perceived), not prompt wording: S10 flips sign, S1/S2/S4/J11 ≈ 0, J2 reads +2. The old `calibrate.py` prompt mis-attributes pronoun-less memo items ~half the time — never use it for direction.
3. `hiring-panel-v1` holds under default (pooled Sally 10/10, alone John 10/10 ×5) but fails alone-wrong under naive (4/5 agents vote Sally alone).
4. flat-v2: perceived pooled Sally +12.0 / John +0.2, every hand John by ≥6, gate PASS both prompts (naive alone-John 10,10,10,8,10; default 10×5).
5. hiring-panel-null perceived profile (neutral prompt, 3 samples): 32 twin pairs of identical text — 24 rated equal, 7 favour John, 1 Sally; mean(John − Sally) = +0.14/item. Small raw name prior toward John. Pooled perceived John +10.3 / Sally +5.7 (calibrate prompt inflates it; neutral is the number). Cost $0.14.
6. Mirror pools (name-swap only) are semantically broken as controls because the brief fixes the Go/payments domain.
7. Cell (d) on flat-v2 was started twice but the API key returned 401 mid-run both times; results discarded, $0.34 spent on the first.

## Blocker at hand-off

Every Anthropic key available (org `ANTHROPIC_API_KEY`, and the user-pasted `sk-ant-api03-99…` bound as
`secret:session:ANTHROPIC_API_KEY_SESSION2`) returns `401 authentication_error "API key is invalid"` directly from
api.anthropic.com (`/v1/models`), from this box. Note the box's baked-in `ANTHROPIC_API_KEY` env var shadows
`env=` bindings of the same name — bind secrets under a different name (e.g. `K`) and `export ANTHROPIC_API_KEY="$K"`.
First step in a new session: `curl -s -w '%{http_code}' https://api.anthropic.com/v1/models -H "x-api-key: $K" -H "anthropic-version: 2023-06-01"` must be 200.

## Plan (parent's current directive; ~10-minute probes, 5–10 runs/cell, report each cell as it lands)

Hold P1 until the null pool reads ≈50/50. Cheapest first, all on `hiring-panel-null`:
1. Blurb-only ballot, empty hands (brief + candidate lines + names only). Sally rate = raw prompt/name prior.
2. Names/pronouns swapped (candidate John↔Sally in `candidates`, keep items) — separates name prior from item prior.
3. Item-type swap: give John the behavioural-story items and Sally the credential items.
4. Null free discussion, 8 runs naive: `probe_free_discussion.py --scenario hiring-panel-null --runs 8 --dump-dir scripts/probe/out/null`.
Then, on flat-v2 (naive, random order, 3 rounds):
5. `probe_free_discussion.py --cell d --runs 8`, then `--cell a`, `b`, `c`, `cprime`; `summarize_probe.py scripts/probe/out/p1`.
   Predictions: H-novelty → c/c′ move the room toward the planted item's candidate, a/b do little; H-framing → a/b move it;
   H-leak → all cells drift the same way as null.
6. Re-run `gate_pool.py hiring-panel-flat-v2` with the per-seed fix; compare with in-run pre-votes.
Add each cell's table + Wilson CI + P3 to `docs/probes/S1_report.md`; add 3–5 transcript excerpts per finding.

Costs observed: ~$0.04 per 3-round 5-agent run; perceived_profile ≈ $0.14 per 64-item pool at 3 samples; gate ≈ $0.05 per pool per prompt.

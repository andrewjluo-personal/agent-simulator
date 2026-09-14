# Mechanism probes

These experimental probes require `ANTHROPIC_API_KEY`.

- `.venv/bin/python scripts/probe/calibrate.py` rates each flat-pool item from
  1–5 with Haiku, using five samples per item.
- `.venv/bin/python scripts/probe/alone_probe.py` collects private ballots from
  each agent with the naive prompt.
- `LOG_LEVEL=WARNING .venv/bin/python scripts/probe/fd_probe.py 5 memo` runs
  five free-discussion trials on the flat pool with the naive prompt.
- `.venv/bin/python scripts/probe/fd_probe.py 5 mirror` runs five trials on the
  mirrored pool.
- `fd_probe.py` prints the pre-vote, per-round votes, unique facts cited,
  spoken-evidence tally verdict, final majority, and token totals. Transcripts
  are dumped to `scripts/probe/out/`.
- `fd_memo.py` runs memo-mode free discussion on `hiring-panel-v1` using the
  repository's default prompt.
- `pooled_reasons.py` samples pooled or individual-agent reasons for a
  scenario.
- `flat_pool.py` exposes the `hiring-panel-flat` sample, and `mirror_pool.py`
  swaps its candidate references for symmetry checks.

The naive prompt monkeypatches `app.prompts.system_prompt` in a
HiddenBench-style setup: it removes the asymmetry sentence and evidence rules.
Results so far are flat Sally 6/7, mirror John 4/5, and the spoken-evidence
tally disagreed with the outcome in all mirror runs.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { createBatch, getBatch, getDemo, getRun, listScenarios, resetScenario } from './api'
import { Controls, ResultsStrip, Transcript, VerdictBadges, VerdictCard, type StripRow } from './components/Panels'
import { FlowTimeline } from './components/FlowTimeline'
import { Table } from './components/Table'
import { ScenarioLab } from './components/ScenarioLab'
import { HighlightContext, useHighlightState } from './hooks/useHighlight'
import { usePlayback } from './hooks/usePlayback'
import { track } from './telemetry'
import { candidateName, sharedOnlyVerdict } from './truth'
import type { Paradigm, RunConfig, RunState, RunSummary, Scenario } from './types'

const PARADIGMS: { id: Paradigm; label: string }[] = [
  { id: 'free_discussion', label: 'Free discussion' },
  { id: 'share_first', label: 'Share facts first' },
]

const DEFAULT_SCENARIO_ID = 'stasser-1985-hidden'

function defaultConfig(scenario: Scenario): RunConfig {
  return {
    scenarioId: scenario.id,
    paradigm: 'free_discussion',
    rounds: 3,
    sentencesPerTurn: 2,
    turnOrder: 'clockwise',
    tieBreak: 'runoff',
    factStyle: 'memo',
    model: 'claude-haiku-4-5',
    seed: Math.floor(Math.random() * 10000),
  }
}

function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [recentRuns, setRecentRuns] = useState<RunSummary[]>([])
  // Full transcripts are fetched on demand (GET /api/runs/{id}) and kept here so replays are instant.
  const fullRuns = useRef(new Map<string, RunState>())
  const [apiDown, setApiDown] = useState(false)
  const [config, setConfig] = useState<RunConfig | null>(null)
  const [n, setN] = useState(10)
  const [batchRuns, setBatchRuns] = useState<Record<string, RunSummary[]>>({})
  const [busy, setBusy] = useState(false)
  const [batchError, setBatchError] = useState<string | null>(null)
  const [labOpen, setLabOpen] = useState(false)
  const pb = usePlayback()
  const highlight = useHighlightState()

  const autoRunAllowed = useRef<boolean | null>(null)
  const autoRunStarted = useRef(false)

  const loadRecent = useCallback(async (scenarioId: string): Promise<boolean> => {
    try {
      const snap = await getDemo(scenarioId)
      setScenario(snap.scenario)
      setRecentRuns(snap.runs)
      if (scenarioId === DEFAULT_SCENARIO_ID) autoRunAllowed.current = snap.autoRunOnLoad !== false
      setConfig((c) => (c ? { ...c, scenarioId: snap.scenario.id } : defaultConfig(snap.scenario)))
      setApiDown(false)
      return true
    } catch (cause) {
      track('demo.load_failed', { reason: String(cause) }, 'warning')
      return false
    }
  }, [])

  // The scenario list and the default scenario's snapshot are independent, so fetch both at once;
  // first paint only waits on the snapshot.
  useEffect(() => {
    const demo = loadRecent(DEFAULT_SCENARIO_ID)
    listScenarios()
      .then(async (list) => {
        setScenarios(list)
        if (await demo) return
        const fallback = list.find((s) => s.id !== DEFAULT_SCENARIO_ID)
        if (!fallback || !(await loadRecent(fallback.id))) setApiDown(true)
      })
      .catch(async (cause: unknown) => {
        track('scenarios.load_failed', { reason: String(cause) }, 'warning')
        if (!(await demo)) setApiDown(true)
      })
  }, [loadRecent])

  // Live-first landing: kick off a real run once the default scenario resolves —
  // once per page load (ref). The server flag and per-IP rate limit bound cost.
  useEffect(() => {
    if (!scenario || !config) return
    if (autoRunStarted.current || autoRunAllowed.current !== true) return
    autoRunStarted.current = true
    track('autorun.start', { scenarioId: scenario.id })
    void pb.startLive({ ...defaultConfig(scenario), seed: Math.floor(Math.random() * 10000) })
  }, [scenario, config, pb])

  const openRun = useCallback(
    async (id: string) => {
      const cached = fullRuns.current.get(id)
      if (cached) {
        pb.loadRun(cached, true)
        return
      }
      try {
        const full = await getRun(id)
        fullRuns.current.set(id, full)
        pb.loadRun(full, true)
      } catch (cause) {
        setBatchError(cause instanceof Error ? cause.message : String(cause))
      }
    },
    [pb],
  )

  // Warm the cache with one finished run per paradigm so the first ▶ Play is instant.
  useEffect(() => {
    for (const p of PARADIGMS) {
      const pick = recentRuns.find((r) => r.config.paradigm === p.id && r.status === 'done')
      if (!pick || fullRuns.current.has(pick.id)) continue
      getRun(pick.id)
        .then((full) => fullRuns.current.set(full.id, full))
        .catch(() => {
          /* best effort; openRun refetches */
        })
    }
  }, [recentRuns])

  // A finished live run joins the recent list — refetch so the strip + stats include it.
  useEffect(() => {
    if (pb.run && pb.run.status === 'done' && pb.run.scenarioId === scenario?.id) {
      void loadRecent(pb.run.scenarioId)
    }
  }, [pb.run?.status, pb.run?.id, pb.run?.scenarioId, scenario?.id, loadRecent])

  const selectScenario = useCallback(
    (id: string) => {
      setConfig((c) => (c ? { ...c, scenarioId: id } : defaultConfig(scenarios.find((s) => s.id === id)!)))
      pb.clear()
      void loadRecent(id).then((ok) => {
        if (!ok) setApiDown(true)
      })
    },
    [scenarios, pb, loadRecent],
  )

  const resetCurrent = useCallback(async () => {
    if (!scenario) return
    try {
      const restored = await resetScenario(scenario.id)
      setScenario(restored)
      setScenarios((prev) => prev.map((s) => (s.id === restored.id ? restored : s)))
      setConfig(defaultConfig(restored))
      pb.clear()
      void loadRecent(restored.id)
    } catch (cause) {
      setBatchError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [scenario, pb, loadRecent])

  // Poll in-flight batches so the strip fills in as round jobs complete.
  const pendingBatchIds = useMemo(
    () => Object.entries(batchRuns).filter(([, runs]) => runs.some((r) => r.status !== 'done' && r.status !== 'error')).map(([id]) => id),
    [batchRuns],
  )
  useEffect(() => {
    if (pendingBatchIds.length === 0) return
    const timer = window.setInterval(async () => {
      for (const id of pendingBatchIds) {
        try {
          const b = await getBatch(id)
          setBatchRuns((prev) => ({ ...prev, [id]: b.runs }))
        } catch {
          /* transient; next tick retries */
        }
      }
    }, 2000)
    return () => window.clearInterval(timer)
  }, [pendingBatchIds])

  const cachedForParadigm = useMemo(
    () => recentRuns.filter((r) => r.config.paradigm === config?.paradigm && r.status === 'done'),
    [recentRuns, config?.paradigm],
  )

  const playCached = useCallback(() => {
    const pick = cachedForParadigm[0]
    if (pick) void openRun(pick.id)
  }, [cachedForParadigm, openRun])

  const runBatch = useCallback(async () => {
    if (!config) return
    setBusy(true)
    setBatchError(null)
    try {
      const b = await createBatch(config, n)
      track('batch.created', { batchId: b.id, n, paradigm: config.paradigm })
      setBatchRuns((prev) => ({ ...prev, [b.id]: b.runs }))
    } catch (cause) {
      const reason = cause instanceof Error ? cause.message : String(cause)
      track('batch.create_failed', { reason }, 'error')
      setBatchError(reason)
    } finally {
      setBusy(false)
    }
  }, [config, n])

  const rows: StripRow[] = useMemo(() => {
    const byId = new Map<string, RunSummary>()
    for (const r of [...Object.values(batchRuns).flat(), ...recentRuns]) byId.set(r.id, r)
    const all = [...byId.values()]
    return PARADIGMS.map((p) => ({ paradigm: p.id, label: p.label, runs: all.filter((r) => r.config.paradigm === p.id) })).filter(
      (row) => row.runs.length > 0,
    )
  }, [recentRuns, batchRuns])

  const pending = useMemo(() => {
    const all = Object.values(batchRuns).flat()
    if (!all.length) return null
    return { done: all.filter((r) => r.status === 'done' || r.status === 'error').length, total: all.length }
  }, [batchRuns])

  const pickRun = useCallback(
    (id: string) => {
      if (recentRuns.some((r) => r.id === id)) void openRun(id)
      else void pb.replayById(id)
    },
    [recentRuns, pb, openRun],
  )

  if (!scenario || !config) {
    return (
      <main>
        <p className="banner">
          {apiDown
            ? 'API unavailable — the backend must be reachable to load scenarios and runs.'
            : 'Loading scenario…'}
        </p>
      </main>
    )
  }

  const status: 'idle' | 'playing' | 'paused' | 'finished' = !pb.run
    ? 'idle'
    : pb.playing
      ? 'playing'
      : pb.derived.finished
        ? 'finished'
        : pb.revealed === 0
          ? 'idle'
          : 'paused'

  const runScenario = pb.run?.scenario ?? scenario
  const roundShown = pb.run ? Math.min(Math.ceil(pb.run.turns.length / Math.max(1, runScenario.agents.length)), Math.floor((pb.revealed - 1) / Math.max(1, runScenario.agents.length)) + 1) : 0

  return (
    <HighlightContext.Provider value={highlight}>
    <main>
      <header>
        <h1>Hidden Profile</h1>
        <p className="hero">
          {runScenario.agents.length} interviewers must pick between {runScenario.candidates.map((c) => c.name).join(' and ')}, but the
          evidence is split: what everyone knows favors {candidateName(runScenario, sharedOnlyVerdict(runScenario))}, and the facts that
          would flip the decision each sit in exactly one person's hand.
          <span className="hero-sub"> Watch whether discussion actually surfaces them — then compare discussion protocols over many runs.</span>
        </p>
      </header>

      {apiDown && <div className="banner">API unavailable — the backend must be reachable to load scenarios and runs.</div>}
      {(pb.error || batchError) && <div className="banner error">{pb.error ?? batchError}</div>}

      <Controls
        config={config}
        onChange={setConfig}
        scenarios={scenarios}
        onSelectScenario={selectScenario}
        onOpenLab={() => setLabOpen(true)}
        onResetScenario={() => void resetCurrent()}
        paradigms={PARADIGMS}
        n={n}
        onChangeN={setN}
        status={status}
        hasCached={cachedForParadigm.length > 0}
        onPlayCached={playCached}
        onPlayLive={() => void pb.startLive({ ...config, seed: Math.floor(Math.random() * 10000) })}
        onRunBatch={() => void runBatch()}
        onPause={() => pb.setPlaying(false)}
        onResume={() => pb.setPlaying(true)}
        onSkip={pb.skipToEnd}
        busy={busy}
        apiDown={apiDown}
      />

      <VerdictBadges scenario={runScenario} />

      <section className="stage">
        <div className="stage-left">
          <Table
            scenario={runScenario}
            config={pb.run?.config ?? null}
            derived={pb.derived}
            status={status}
            round={Math.max(roundShown, 0)}
            live={!!pb.run && pb.run.status !== 'done'}
          />
          {pb.run && pb.derived.finished && <VerdictCard run={pb.run} commonGround={pb.derived.commonGround} />}
          {pb.run &&
            !pb.derived.finished &&
            pb.run.status !== 'done' &&
            pb.revealed >= (pb.run.turns ?? []).length && (
              <div className="waiting live">
                <span className="live-dot" />
                {pb.run.status === 'error'
                  ? `Run failed: ${pb.run.error ?? 'unknown error'}`
                  : (pb.run.turns ?? []).length === 0
                    ? 'Live — agents are reading their notes and casting a pre-discussion ballot…'
                    : pb.run.currentRound >= pb.run.config.rounds
                      ? 'Live — runoff round, waiting on agents…'
                      : `Live — round ${Math.min(pb.run.currentRound + 1, pb.run.config.rounds)} of ${pb.run.config.rounds}, waiting on agents…`}
              </div>
            )}
          {pb.run && pb.derived.finished && (
            <button className="link" onClick={pb.restart}>
              ↺ Replay this run
            </button>
          )}
        </div>
        <aside className="stage-right">
          {pb.run ? (
            <Transcript run={pb.run} turns={pb.derived.revealedTurns} />
          ) : (
            <div className="transcript">
              <h3>Transcript</h3>
              <p className="muted">
                A live run starts automatically. Press ▶ Play to replay a recent run, ⚡ Run live to start another, or click an agent or a fact chip to inspect it.
              </p>
            </div>
          )}
        </aside>
      </section>

      {labOpen && runScenario && (
        <ScenarioLab
          scenario={runScenario}
          onClose={() => setLabOpen(false)}
          onSaved={(saved) => {
            setLabOpen(false)
            setScenarios((prev) => [...prev.filter((item) => item.id !== saved.id), saved])
            setConfig(defaultConfig(saved))
            pb.clear()
            void listScenarios().then(setScenarios)
            void loadRecent(saved.id)
          }}
        />
      )}

      {pb.run && (
        <section className="timeline-section">
          <h3>
            Information flow <span className="muted">· who said which fact when · ghosted chips are decisive facts still sitting unspoken in that hand</span>
          </h3>
          <FlowTimeline run={pb.run} turns={pb.derived.revealedTurns} />
        </section>
      )}

      <ResultsStrip rows={rows} activeRunId={pb.run?.id ?? null} onPick={pickRun} pending={pending} />
    </main>
    </HighlightContext.Provider>
  )
}

export default App

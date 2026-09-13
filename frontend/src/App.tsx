import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import { createBatch, getBatch, getDemo } from './api'
import { Controls, ResultsStrip, Transcript, VerdictBadges, VerdictCard, type StripRow } from './components/Panels'
import { Table } from './components/Table'
import bundled from './demo/snapshot.json'
import { usePlayback } from './hooks/usePlayback'
import { track } from './telemetry'
import { candidateName, sharedOnlyVerdict } from './truth'
import type { DemoSnapshot, Paradigm, RunConfig, RunState, RunSummary, Scenario } from './types'

const PARADIGMS: { id: Paradigm; label: string }[] = [
  { id: 'free_discussion', label: 'Free discussion' },
  { id: 'share_first', label: 'Share facts first' },
]

const fallback = bundled as unknown as DemoSnapshot

function defaultConfig(scenario: Scenario): RunConfig {
  return {
    scenarioId: scenario.id,
    paradigm: 'free_discussion',
    rounds: 3,
    sentencesPerTurn: 2,
    turnOrder: 'clockwise',
    model: 'claude-haiku-4-5',
    seed: Math.floor(Math.random() * 10000),
  }
}

function App() {
  const [scenario, setScenario] = useState<Scenario>(fallback.scenario)
  const [demoRuns, setDemoRuns] = useState<RunState[]>(fallback.runs)
  const [apiDown, setApiDown] = useState(false)
  const [config, setConfig] = useState<RunConfig>(() => defaultConfig(fallback.scenario))
  const [n, setN] = useState(10)
  const [batchRuns, setBatchRuns] = useState<Record<string, RunSummary[]>>({})
  const [busy, setBusy] = useState(false)
  const [batchError, setBatchError] = useState<string | null>(null)
  const pb = usePlayback()

  useEffect(() => {
    getDemo()
      .then((snap) => {
        setScenario(snap.scenario)
        setConfig((c) => ({ ...c, scenarioId: snap.scenario.id }))
        if (snap.runs.length) setDemoRuns(snap.runs)
        setApiDown(false)
      })
      .catch((cause: unknown) => {
        track('demo.load_failed', { reason: String(cause) }, 'warning')
        setApiDown(true)
      })
  }, [])

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
    () => demoRuns.filter((r) => r.config.paradigm === config.paradigm && r.status === 'done'),
    [demoRuns, config.paradigm],
  )

  const playCached = useCallback(() => {
    const pick = cachedForParadigm[0]
    if (pick) pb.loadRun(pick, true)
  }, [cachedForParadigm, pb])

  const runBatch = useCallback(async () => {
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
    const all: RunSummary[] = [...demoRuns, ...Object.values(batchRuns).flat()]
    return PARADIGMS.map((p) => ({ paradigm: p.id, label: p.label, runs: all.filter((r) => r.config.paradigm === p.id) })).filter(
      (row) => row.runs.length > 0,
    )
  }, [demoRuns, batchRuns])

  const pending = useMemo(() => {
    const all = Object.values(batchRuns).flat()
    if (!all.length) return null
    return { done: all.filter((r) => r.status === 'done' || r.status === 'error').length, total: all.length }
  }, [batchRuns])

  const pickRun = useCallback(
    (id: string) => {
      const full = demoRuns.find((r) => r.id === id)
      if (full) pb.loadRun(full, true)
      else void pb.replayById(id)
    },
    [demoRuns, pb],
  )

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
  const roundShown = pb.run ? Math.min(pb.run.config.rounds, Math.floor((pb.revealed - 1) / Math.max(1, runScenario.agents.length)) + 1) : 0

  return (
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

      {apiDown && <div className="banner">API unavailable, showing cached runs</div>}
      {(pb.error || batchError) && <div className="banner error">{pb.error ?? batchError}</div>}

      <Controls
        config={config}
        onChange={setConfig}
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
          <Table scenario={runScenario} config={pb.run?.config ?? null} derived={pb.derived} status={status} round={Math.max(roundShown, 0)} />
          {pb.run && pb.derived.finished && <VerdictCard run={pb.run} commonGround={pb.derived.commonGround} />}
          {pb.run && !pb.derived.finished && pb.run.status !== 'done' && pb.revealed >= pb.run.turns.length && status !== 'idle' && (
            <div className="waiting">
              {pb.run.status === 'error' ? `Run failed: ${pb.run.error ?? 'unknown error'}` : 'Waiting for the next turn from the agents…'}
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
                Press ▶ Play to replay a cached run, ⚡ Run live to start a new one, or click an agent or a fact chip to inspect it.
              </p>
            </div>
          )}
        </aside>
      </section>

      <ResultsStrip rows={rows} activeRunId={pb.run?.id ?? null} onPick={pickRun} pending={pending} />
    </main>
  )
}

export default App

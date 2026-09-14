import { useMemo } from 'react'
import { aloneVotes, candidateName, decisiveFactIds, pooledVerdict, sharedFactIds, tally, tallyText } from '../truth'
import type { FactStyle, Paradigm, RunConfig, RunState, RunSummary, Scenario, TieBreak, Turn, TurnOrder } from '../types'
import { candidateColor } from './Table'

export function VerdictBadges({ scenario }: { scenario: Scenario }) {
  const alone = aloneVotes(scenario)
  const aloneTally = tally(Object.values(alone), scenario)
  const pooled = pooledVerdict(scenario)
  const aloneWinner = scenario.candidates.reduce((b, c) => (aloneTally[c.id] > aloneTally[b.id] ? c : b))
  return (
    <div className="badges">
      <div className="badge">
        <span className="badge-k">If each voted alone</span>
        <span className="badge-v" style={{ color: candidateColor(scenario, aloneWinner.id) }}>
          {aloneWinner.name} {tallyText(aloneTally, scenario)}
        </span>
      </div>
      <div className="badge">
        <span className="badge-k">If they pooled everything</span>
        <span className="badge-v" style={{ color: candidateColor(scenario, pooled) }}>
          {candidateName(scenario, pooled)}
        </span>
      </div>
    </div>
  )
}

export type ControlsProps = {
  config: RunConfig
  onChange: (c: RunConfig) => void
  scenarios: Scenario[]
  onSelectScenario: (id: string) => void
  onOpenLab: () => void
  onResetScenario: () => void
  paradigms: { id: Paradigm; label: string }[]
  n: number
  onChangeN: (n: number) => void
  status: 'idle' | 'playing' | 'paused' | 'finished'
  hasCached: boolean
  onPlayCached: () => void
  onPlayLive: () => void
  onRunBatch: () => void
  onPause: () => void
  onResume: () => void
  onSkip: () => void
  busy: boolean
  apiDown: boolean
}

export function Controls(p: ControlsProps) {
  const set = <K extends keyof RunConfig>(k: K, v: RunConfig[K]) => p.onChange({ ...p.config, [k]: v })
  const selected = p.scenarios.find((s) => s.id === p.config.scenarioId)
  return (
    <div className="controls">
      <label>
        Scenario
        <select value={p.config.scenarioId} onChange={(e) => p.onSelectScenario(e.target.value)}>
          {p.scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title} [{s.source?.kind ?? 'sample'}]
            </option>
          ))}
        </select>
      </label>
      <button type="button" onClick={p.onOpenLab}>Scenario Lab</button>
      {selected?.isSample && (
        <button className="link" onClick={p.onResetScenario} title="Restore this sample scenario to its original state">
          Reset scenario
        </button>
      )}
      <label>
        Paradigm
        <select value={p.config.paradigm} onChange={(e) => set('paradigm', e.target.value as Paradigm)}>
          {p.paradigms.map((x) => (
            <option key={x.id} value={x.id}>
              {x.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Evidence format
        <select value={p.config.factStyle} onChange={(e) => set('factStyle', e.target.value as FactStyle)}>
          <option value="memo">Memo (human-study style)</option>
          <option value="labelled">Labelled facts</option>
        </select>
      </label>
      <label>
        Rounds
        <input type="number" min={1} max={10} value={p.config.rounds} onChange={(e) => set('rounds', Number(e.target.value))} />
      </label>
      <label>
        Sentences/turn
        <input
          type="number"
          min={1}
          max={5}
          value={p.config.sentencesPerTurn}
          onChange={(e) => set('sentencesPerTurn', Number(e.target.value))}
        />
      </label>
      <label>
        Order
        <select value={p.config.turnOrder} onChange={(e) => set('turnOrder', e.target.value as TurnOrder)}>
          <option value="clockwise">clockwise</option>
          <option value="random">random</option>
        </select>
      </label>
      <label>
        Tie-break
        <select value={p.config.tieBreak} onChange={(e) => set('tieBreak', e.target.value as TieBreak)}>
          <option value="runoff">runoff</option>
          <option value="none">none</option>
          <option value="chair">chair</option>
        </select>
      </label>
      <span className="spacer" />
      {p.status === 'playing' ? (
        <button onClick={p.onPause}>❚❚ Pause</button>
      ) : p.status === 'paused' ? (
        <button onClick={p.onResume}>▶ Resume</button>
      ) : (
        <button className="primary" onClick={p.onPlayCached} disabled={!p.hasCached} title="Replay a cached run for this paradigm">
          ▶ Play
        </button>
      )}
      {p.status === 'playing' && <button onClick={p.onSkip}>⏭ Skip</button>}
      <button onClick={p.onPlayLive} disabled={p.busy || p.apiDown} title="Start a new run with live LLM agents">
        ⚡ Run live
      </button>
      <span className="batch">
        <button onClick={p.onRunBatch} disabled={p.busy || p.apiDown}>
          Run ×
        </button>
        <input type="number" min={1} max={25} value={p.n} onChange={(e) => p.onChangeN(Number(e.target.value))} />
      </span>
    </div>
  )
}

export function Transcript({ run, turns }: { run: RunState; turns: Turn[] }) {
  const shared = useMemo(() => sharedFactIds(run.scenario), [run.scenario])
  const agents = new Map(run.scenario.agents.map((a) => [a.id, a]))
  return (
    <div className="transcript">
      <h3>
        Transcript <span className="muted">· {run.llmProvider === 'fake' ? 'synthetic agents' : run.config.model}</span>
      </h3>
      {turns.length === 0 && <p className="muted">Nothing said yet.</p>}
      {turns.map((t) => (
        <div key={t.seq} className="utt">
          <div className="utt-head">
            <span className="utt-round">{t.round >= run.config.rounds ? 'Runoff' : `R${t.round + 1}`}</span>
            <strong>{agents.get(t.agentId)?.name ?? t.agentId}</strong>
            {t.lean !== 'undecided' && (
              <span className="lean" style={{ color: candidateColor(run.scenario, t.lean) }}>
                leans {candidateName(run.scenario, t.lean)}
              </span>
            )}
          </div>
          <div className="utt-text">{t.sentences.length ? t.sentences.join(' ') : <em>(no valid output)</em>}</div>
          <div className="utt-cites">
            {t.cited.map((id) => (
              <span key={id} className={`cite ${shared.has(id) ? 'shared' : 'unique'}`}>
                {id}
              </span>
            ))}
            {t.hallucinated.map((id) => (
              <span key={id} className="cite halluc" title="cited a fact the speaker does not hold — dropped">
                {id} ✗
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export function VerdictCard({ run, commonGround }: { run: RunState; commonGround: Set<string> }) {
  const m = run.metrics
  const s = run.scenario
  const decisive = decisiveFactIds(s)
  const unspoken = [...decisive].filter((id) => !commonGround.has(id))
  if (!m) return null
  const majority = m.majorityCandidateId
  return (
    <div className={`verdict ${m.correct ? 'ok' : 'bad'}`}>
      <div className="verdict-title">
        Panel voted{' '}
        <b style={{ color: candidateColor(s, majority) }}>
          {majority === 'undecided' ? 'undecided' : candidateName(s, majority)}
        </b>{' '}
        {tallyText(m.finalTally, s)}. Correct answer: <b style={{ color: candidateColor(s, m.correctCandidateId) }}>{candidateName(s, m.correctCandidateId)}</b>.
      </div>
      <div className="verdict-sub">
        {unspoken.length} of {decisive.size} decisive {candidateName(s, m.correctCandidateId)} facts never left anyone's hand
        {m.hallucinationCount > 0 && ` · ${m.hallucinationCount} hallucinated citation${m.hallucinationCount === 1 ? '' : 's'} dropped`}
        {' · '}agreement {Math.round(m.agreement * 100)}%
      </div>
    </div>
  )
}

export type StripRow = { paradigm: string; label: string; runs: RunSummary[] }

export function ResultsStrip({
  rows,
  activeRunId,
  onPick,
  pending,
}: {
  rows: StripRow[]
  activeRunId: string | null
  onPick: (id: string) => void
  pending: { done: number; total: number } | null
}) {
  return (
    <div className="strip">
      <div className="strip-head">
        <h3>Paradigm comparison</h3>
        <span className="muted">one dot per run · green = panel chose the correct candidate · click a dot to replay</span>
        {pending && pending.done < pending.total && (
          <span className="progress">
            running {pending.done}/{pending.total}
          </span>
        )}
      </div>
      {rows.map((row) => {
        const done = row.runs.filter((r) => r.status === 'done' && r.metrics)
        const correct = done.filter((r) => r.metrics!.correct).length
        const surfaced = done.length ? done.reduce((a, r) => a + r.metrics!.decisiveSurfaced, 0) / done.length : 0
        return (
          <div key={row.paradigm} className="strip-row">
            <div className="strip-label">{row.label}</div>
            <div className="dots">
              {row.runs.map((r) => (
                <button
                  key={r.id}
                  className={`dot ${r.status !== 'done' ? 'pending' : r.metrics?.correct ? 'ok' : 'bad'} ${
                    r.id === activeRunId ? 'active' : ''
                  }`}
                  title={
                    r.status === 'done'
                      ? `${r.metrics?.correct ? 'correct' : 'wrong'} · ${Math.round((r.metrics?.decisiveSurfaced ?? 0) * 100)}% decisive facts surfaced · seed ${r.config.seed}`
                      : r.status
                  }
                  onClick={() => onPick(r.id)}
                />
              ))}
            </div>
            <div className="strip-stats">
              {done.length ? (
                <>
                  <b>{Math.round((100 * correct) / done.length)}%</b> correct ({correct}/{done.length}) ·{' '}
                  <b>{Math.round(surfaced * 100)}%</b> of decisive facts surfaced
                </>
              ) : (
                <span className="muted">no completed runs</span>
              )}
            </div>
          </div>
        )
      })}
      {rows.length === 0 && <p className="muted">No runs yet — press Run ×N.</p>}
    </div>
  )
}

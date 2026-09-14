import { useMemo } from 'react'
import { aloneVotes, candidateName, decisiveFactIds, pooledVerdict, sharedFactIds, tally, tallyText } from '../truth'
import type { Paradigm, RunConfig, RunState, RunSummary, Scenario, Turn, TurnOrder } from '../types'
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

function scenarioBaseId(id: string): string {
  return id.replace(/-(v\d+|\d+)$/, '')
}

function formatRate(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

function validationBadge(scenario: Scenario): { text: string; title: string } | null {
  const first = Object.entries(scenario.validation ?? {})[0]
  if (!first) return null
  const [model, result] = first
  const aloneRates = Object.entries(result.aloneWrongRate)
  const rates = aloneRates.map(([, rate]) => rate)
  const alone =
    rates.length === 0
      ? 'n/a'
      : rates.every((rate) => rate === rates[0])
        ? formatRate(rates[0])
        : `${formatRate(Math.min(...rates))}..${formatRate(Math.max(...rates))} (${aloneRates
            .map(([agentId, rate]) => `${agentId} ${formatRate(rate)}`)
            .join(', ')})`
  const pooled = formatRate(result.pooledRightRate)
  const freeDiscussion =
    result.freeDiscussionRate == null ? 'n/a' : formatRate(result.freeDiscussionRate)
  const nullGate = result.nullGate == null ? 'n/a' : result.nullGate ? 'pass' : 'FAIL'
  return {
    text: `validated on ${model}${result.nullGate === false ? ' · fails null gate' : ''}`,
    title: `alone-wrong ${alone}, pooled-right ${pooled}, free-discussion ${freeDiscussion}, null-gate ${nullGate}`,
  }
}

export type ControlsProps = {
  config: RunConfig
  onChange: (c: RunConfig) => void
  scenarios: Scenario[]
  onSelectScenario: (id: string) => void
  onOpenLab: () => void
  onResetScenario: () => void
  paradigms: { id: Paradigm; label: string }[]
  status: 'idle' | 'playing' | 'paused' | 'finished'
  hasCached: boolean
  onPlayCached: () => void
  onPlayLive: () => void
  onPause: () => void
  onResume: () => void
  onSkip: () => void
  apiDown: boolean
}

export function Controls(p: ControlsProps) {
  const set = <K extends keyof RunConfig>(k: K, v: RunConfig[K]) => p.onChange({ ...p.config, [k]: v })
  const selected = p.scenarios.find((s) => s.id === p.config.scenarioId)
  const validation = selected ? validationBadge(selected) : null
  const variants = selected
    ? p.scenarios
        .filter((s) => scenarioBaseId(s.id) === scenarioBaseId(selected.id))
        .sort((a, b) => a.agents.length - b.agents.length || a.id.localeCompare(b.id))
    : []
  return (
    <div className="controls">
      <label>
        Scenario
        <select value={p.config.scenarioId} onChange={(e) => p.onSelectScenario(e.target.value)}>
          {p.scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title} · {s.agents.length} agents [{s.source?.kind ?? 'sample'}]
            </option>
          ))}
        </select>
      </label>
      <button type="button" onClick={p.onOpenLab}>Scenario Lab</button>
      {validation ? (
        <span className="badge validation-badge" title={validation.title}>
          {validation.text}
        </span>
      ) : (
        <span className="badge validation-badge">unvalidated</span>
      )}
      {variants.length > 1 && (
        <label>
          Agents
          <select value={selected?.id} onChange={(e) => p.onSelectScenario(e.target.value)}>
            {variants.map((s) => (
              <option key={s.id} value={s.id}>
                {s.agents.length} agents
              </option>
            ))}
          </select>
        </label>
      )}
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
      <span className="spacer" />
      {p.status === 'playing' ? (
        <button onClick={p.onPause}>❚❚ Pause</button>
      ) : p.status === 'paused' ? (
        <button onClick={p.onResume}>▶ Resume</button>
      ) : (
        <button className="primary" onClick={p.onPlayCached} disabled={!p.hasCached} title="Replay a recent run for this paradigm">
          ▶ Play
        </button>
      )}
      {p.status === 'playing' && <button onClick={p.onSkip}>⏭ Skip</button>}
      <button onClick={p.onPlayLive} disabled={p.apiDown} title="Start a new run with live LLM agents">
        ⚡ Run live
      </button>
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
}: {
  rows: StripRow[]
  activeRunId: string | null
  onPick: (id: string) => void
}) {
  return (
    <div className="strip">
      <div className="strip-head">
        <h3>Recent runs</h3>
        <span className="muted">one dot per run · green = panel chose the correct candidate · click a dot to replay</span>
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
      {rows.length === 0 && <p className="muted">No runs yet — press ⚡ Run live.</p>}
    </div>
  )
}

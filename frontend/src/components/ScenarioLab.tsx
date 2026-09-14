import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import {
  analyzeScenario,
  ApiError,
  forkScenario,
  getScenarioAnalysis,
  getScenarioValidationJob,
  getValidationJob,
  startValidation,
} from '../api'
import { useHighlight } from '../hooks/useHighlight'
import {
  candidateName,
  decisiveFactIds,
  scores,
  sharedFactIds,
  uniqueFactIds,
} from '../truth'
import type {
  AgentPersona,
  Candidate,
  Fact,
  Scenario,
  ScenarioAnalysis,
  ValidationJob,
} from '../types'
import { candidateColor } from './FactChip'
import './ScenarioLab.css'

type Props = {
  scenario: Scenario
  onSaved: (scenario: Scenario) => void
  onClose: () => void
}

const copyScenario = (scenario: Scenario): Scenario => JSON.parse(JSON.stringify(scenario)) as Scenario

export function toggleHolder(scenario: Scenario, factId: string, agentId: string): Scenario {
  const held = scenario.distribution[agentId] ?? []
  const nextHeld = held.includes(factId) ? held.filter((id) => id !== factId) : [...held, factId]
  return { ...scenario, distribution: { ...scenario.distribution, [agentId]: nextHeld } }
}

export function updateFact(scenario: Scenario, factId: string, patch: Partial<Fact>): Scenario {
  return { ...scenario, facts: scenario.facts.map((fact) => (fact.id === factId ? { ...fact, ...patch } : fact)) }
}

export function addFact(scenario: Scenario): Scenario {
  const used = new Set(scenario.facts.map((fact) => fact.id))
  let n = 1
  while (used.has(`F${n}`)) n += 1
  return {
    ...scenario,
    facts: [
      ...scenario.facts,
      {
        id: `F${n}`,
        candidateId: scenario.candidates[0]?.id ?? '',
        valence: 'pro',
        weight: 1,
        text: 'New fact',
        memoText: '',
        keywords: [],
      },
    ],
  }
}

export function removeFact(scenario: Scenario, factId: string): Scenario {
  const distribution = Object.fromEntries(
    Object.entries(scenario.distribution).map(([agentId, held]) => [agentId, held.filter((id) => id !== factId)]),
  )
  return { ...scenario, facts: scenario.facts.filter((fact) => fact.id !== factId), distribution }
}

export function addAgent(scenario: Scenario): Scenario {
  const used = new Set(scenario.agents.map((agent) => agent.id))
  let n = 1
  while (used.has(`agent${n}`)) n += 1
  const agent: AgentPersona = { id: `agent${n}`, name: 'New agent', role: '', style: '' }
  return {
    ...scenario,
    agents: [...scenario.agents, agent],
    distribution: { ...scenario.distribution, [agent.id]: [] },
  }
}

export function removeAgent(scenario: Scenario, agentId: string): Scenario {
  if (scenario.agents.length <= 2) return scenario
  const distribution = { ...scenario.distribution }
  delete distribution[agentId]
  return { ...scenario, agents: scenario.agents.filter((agent) => agent.id !== agentId), distribution }
}

function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function shortDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function ScoreBar({ row, scenario, scale }: { row: Record<string, number>; scenario: Scenario; scale: number }) {
  const negatives = scenario.candidates.filter((candidate) => (row[candidate.id] ?? 0) < 0)
  const positives = scenario.candidates.filter((candidate) => (row[candidate.id] ?? 0) > 0)
  return (
    <div className="score-bar">
      <div className="score-half score-negative">
        <div className="score-segments">
          {negatives.map((candidate) => (
            <span
              key={candidate.id}
              className="score-segment negative"
              style={{
                width: `${Math.min(100, (Math.abs(row[candidate.id] ?? 0) / scale) * 100)}%`,
                backgroundColor: candidateColor(scenario, candidate.id),
              }}
              title={`${candidate.name}: ${row[candidate.id]}`}
            />
          ))}
        </div>
      </div>
      <div className="score-axis" />
      <div className="score-half score-positive">
        <div className="score-segments">
          {positives.map((candidate) => (
            <span
              key={candidate.id}
              className="score-segment"
              style={{
                width: `${Math.min(100, (row[candidate.id] ?? 0) / scale) * 100}%`,
                backgroundColor: candidateColor(scenario, candidate.id),
              }}
              title={`${candidate.name}: ${row[candidate.id]}`}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function MeasuredCard({
  analysis,
  scenario,
  job,
}: {
  analysis: ScenarioAnalysis | null
  scenario: Scenario
  job: ValidationJob | null
}) {
  const result = analysis?.validation
  if (!result) {
    return <div className="measured-card"><strong>Measured (Haiku)</strong><span className="muted">not validated</span>{job && <span className="muted">{job.status}</span>}</div>
  }
  return (
    <div className="measured-card">
      <strong>Measured (Haiku)</strong>
      <div className="measured-list">
        {scenario.agents.map((agent) => (
          <span key={agent.id}>{agent.name} {formatPercent(result.aloneWrongRate[agent.id] ?? 0)}</span>
        ))}
      </div>
      <span>pooled right {formatPercent(result.pooledRightRate)}</span>
      <span>
        free discussion {result.freeDiscussionRate == null ? '—' : formatPercent(result.freeDiscussionRate)}
        {result.freeDiscussionRuns ? ` (${result.freeDiscussionRuns})` : ''}
      </span>
      <small>{result.trials} trials · {shortDate(result.date)}</small>
    </div>
  )
}

export function ScenarioLab({ scenario, onSaved, onClose }: Props) {
  const [draft, setDraft] = useState(() => copyScenario(scenario))
  const [analysis, setAnalysis] = useState<ScenarioAnalysis | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [job, setJob] = useState<ValidationJob | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [discussion, setDiscussion] = useState(false)
  const [slug, setSlug] = useState('')
  const hl = useHighlight()
  const dirty = JSON.stringify(draft) !== JSON.stringify(scenario)
  const decisive = useMemo(() => (analysis ? new Set(analysis.decisiveFactIds) : decisiveFactIds(draft)), [analysis, draft])
  const hiddenUnique = useMemo(() => uniqueFactIds(draft), [draft])
  const shared = useMemo(() => sharedFactIds(draft), [draft])
  const groupedFacts = useMemo(
    () => draft.candidates.map((candidate) => ({ candidate, facts: draft.facts.filter((fact) => fact.candidateId === candidate.id) })),
    [draft],
  )

  useEffect(() => setDraft(copyScenario(scenario)), [scenario])

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => {
      analyzeScenario(draft)
        .then((result) => {
          if (active) {
            setAnalysis(result)
            setAnalysisError(null)
          }
        })
        .catch((cause) => {
          if (active) setAnalysisError(errorText(cause))
        })
    }, 300)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [draft])

  useEffect(() => {
    let active = true
    getScenarioValidationJob(scenario.id)
      .then((existing) => {
        if (active && existing) setJob(existing)
      })
      .catch((cause) => active && setValidationError(errorText(cause)))
    return () => {
      active = false
    }
  }, [scenario.id])

  useEffect(() => {
    if (!job || (job.status !== 'queued' && job.status !== 'running')) return
    const poll = async () => {
      try {
        const next = await getValidationJob(job.id)
        setJob((prev) => (prev && prev.id === next.id && prev.status === next.status ? prev : next))
        if (next.status === 'done') {
          setAnalysis(await getScenarioAnalysis(scenario.id))
        } else if (next.status === 'error') {
          setValidationError(next.error ?? 'Validation failed')
        }
      } catch (cause) {
        setValidationError(errorText(cause))
      }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 3000)
    return () => window.clearInterval(timer)
  }, [job, scenario.id])

  const updateAgent = (agentId: string, patch: Partial<AgentPersona>) =>
    setDraft((current) => ({
      ...current,
      agents: current.agents.map((agent) => (agent.id === agentId ? { ...agent, ...patch } : agent)),
    }))
  const updateCandidate = (candidateId: string, patch: Partial<Candidate>) =>
    setDraft((current) => ({
      ...current,
      candidates: current.candidates.map((candidate) => (candidate.id === candidateId ? { ...candidate, ...patch } : candidate)),
    }))
  const update = (next: Scenario) => setDraft(next)

  const validate = async () => {
    setValidationError(null)
    try {
      setJob(await startValidation(scenario.id, discussion))
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) setValidationError('already running')
      else setValidationError(errorText(cause))
    }
  }

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      onSaved(await forkScenario({ baseId: scenario.id, scenario: draft, ...(slug ? { slug } : {}) }))
    } catch (cause) {
      setSaveError(errorText(cause))
    } finally {
      setSaving(false)
    }
  }

  const scoreRows = analysis
    ? [...analysis.agentLeans.map((lean) => ({ label: draft.agents.find((agent) => agent.id === lean.agentId)?.name ?? lean.agentId, scores: lean.scores, verdict: lean.verdict })), { label: 'Pooled', scores: analysis.pooledScores, verdict: analysis.pooledVerdict }, { label: 'Shared only', scores: scores(draft, shared), verdict: analysis.sharedOnlyVerdict }]
    : []
  const scale = Math.max(1, ...scoreRows.flatMap((row) => Object.values(row.scores).map((score) => Math.abs(score))))
  const pooledName = analysis?.pooledVerdict === 'undecided' ? 'Pooled evidence' : candidateName(draft, analysis?.pooledVerdict ?? 'undecided')

  return (
    <section className="scenario-lab" aria-label="Scenario Lab">
      <div className="lab-header">
        <div>
          <div className="lab-kicker">Scenario Lab</div>
          <h2>{draft.title}</h2>
          <div className="lab-meta">
            <span className="lab-tag">{draft.source?.kind ?? 'sample'}</span>
            {draft.source?.fidelity && <span className="lab-tag">{draft.source.fidelity}</span>}
            {draft.source?.paper && <span>{draft.source.paper}</span>}
            {draft.parentId && <span>forked from {draft.parentId}</span>}
          </div>
        </div>
        <button type="button" onClick={onClose}>Close</button>
      </div>
      {draft.source?.notes && <details className="lab-notes"><summary>Source notes</summary><p>{draft.source.notes}</p></details>}
      {analysisError && <div className="lab-error">{analysisError}</div>}

      <h3>Distribution matrix</h3>
      <div className="lab-table-scroll">
        <table className="lab-matrix">
          <thead>
            <tr>
              <th>Fact</th><th>Text</th>
              {draft.agents.map((agent) => (
                <th key={agent.id}>
                  <div className="agent-head">
                    <input value={agent.name} onChange={(e) => updateAgent(agent.id, { name: e.target.value })} />
                    <button type="button" className="icon-button" title="Remove agent" onClick={() => update(removeAgent(draft, agent.id))}>×</button>
                  </div>
                </th>
              ))}
              <th>Weight</th><th>Valence</th><th>Candidate</th><th />
            </tr>
          </thead>
          <tbody>
            {groupedFacts.flatMap(({ candidate, facts }) => [
              <tr className="candidate-group" key={`group-${candidate.id}`}><th colSpan={draft.agents.length + 6} style={{ color: candidateColor(draft, candidate.id) }}>{candidate.name}</th></tr>,
              ...facts.map((fact) => {
                const isShared = shared.has(fact.id)
                const isDecisive = decisive.has(fact.id) && hiddenUnique.has(fact.id)
                return (
                  <tr
                    key={fact.id}
                    className={isShared ? 'shared' : ''}
                    style={{ borderLeftColor: fact.valence === 'pro' ? '#16a34a' : fact.valence === 'con' ? '#dc2626' : '#9ca3af' }}
                    onPointerEnter={() => hl.set({ factId: fact.id, agentId: null })}
                    onPointerLeave={hl.clear}
                  >
                    <td className="fact-id-cell"><code>{fact.id}</code>{isShared && <span className="lab-pill">shared</span>}{isDecisive && <span className="lab-pill decisive">decisive</span>}</td>
                    <td className="fact-edit">
                      <textarea value={fact.text} onChange={(e) => update(updateFact(draft, fact.id, { text: e.target.value }))} />
                      <input value={fact.memoText ?? ''} placeholder="memoText" onChange={(e) => update(updateFact(draft, fact.id, { memoText: e.target.value }))} />
                      <input value={(fact.keywords ?? []).join(', ')} placeholder="keywords" onChange={(e) => update(updateFact(draft, fact.id, { keywords: e.target.value.split(',').map((word) => word.trim()).filter(Boolean) }))} />
                    </td>
                    {draft.agents.map((agent) => {
                      const held = (draft.distribution[agent.id] ?? []).includes(fact.id)
                      const size = fact.weight === 3 ? 14 : fact.weight === 2 ? 11 : 8
                      return (
                        <td key={agent.id} className="holder-cell">
                          <button type="button" className={`holder-toggle ${held ? 'held' : ''}`} style={{ '--dot-size': `${size}px` } as CSSProperties} aria-label={`${held ? 'Remove' : 'Add'} ${fact.id} ${agent.name}`} onClick={() => update(toggleHolder(draft, fact.id, agent.id))}>
                            {held ? '●' : '○'}
                          </button>
                        </td>
                      )
                    })}
                    <td><select value={fact.weight} onChange={(e) => update(updateFact(draft, fact.id, { weight: Number(e.target.value) }))}><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option></select></td>
                    <td><select value={fact.valence} onChange={(e) => update(updateFact(draft, fact.id, { valence: e.target.value as Fact['valence'] }))}><option value="pro">pro</option><option value="con">con</option><option value="neutral">neutral</option></select></td>
                    <td><select value={fact.candidateId} onChange={(e) => update(updateFact(draft, fact.id, { candidateId: e.target.value }))}>{draft.candidates.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}</select></td>
                    <td><button type="button" className="icon-button" title="Delete fact" onClick={() => update(removeFact(draft, fact.id))}>×</button></td>
                  </tr>
                )
              }),
            ])}
          </tbody>
        </table>
      </div>
      <div className="lab-toolbar"><button type="button" onClick={() => update(addFact(draft))}>Add fact</button><button type="button" onClick={() => update(addAgent(draft))}>Add agent</button></div>
      <div className="lab-editor-grid">
        <div><h4>Agent roles and styles</h4>{draft.agents.map((agent) => <div className="mini-editor" key={agent.id}><strong>{agent.name}</strong><input placeholder="role" value={agent.role} onChange={(e) => updateAgent(agent.id, { role: e.target.value })} /><input placeholder="style" value={agent.style} onChange={(e) => updateAgent(agent.id, { style: e.target.value })} /></div>)}</div>
        <div><h4>Candidate blurbs</h4>{draft.candidates.map((candidate) => <div className="mini-editor" key={candidate.id}><strong style={{ color: candidateColor(draft, candidate.id) }}>{candidate.name}</strong><input value={candidate.blurb} onChange={(e) => updateCandidate(candidate.id, { blurb: e.target.value })} /></div>)}</div>
      </div>

      <div className="lab-analysis">
        <h3>Designed lean (arithmetic)</h3>
        {scoreRows.map((row) => <div className="score-row" key={row.label}><span className="score-label">{row.label}</span><ScoreBar row={row.scores} scenario={draft} scale={scale} /><strong>{candidateName(draft, row.verdict)}</strong></div>)}
        <div className="validation-controls">
          <MeasuredCard analysis={analysis} scenario={draft} job={job} />
          <div><button type="button" onClick={() => void validate()} disabled={dirty || Boolean(job && (job.status === 'queued' || job.status === 'running'))} title={dirty ? 'save first' : undefined}>Validate on Haiku</button><label className="check-label"><input type="checkbox" checked={discussion} onChange={(e) => setDiscussion(e.target.checked)} /> include 10 free-discussion runs (~120 calls)</label></div>
        </div>
        {validationError && <div className="lab-error">{validationError}</div>}
      </div>

      {analysis && <div className="hardness">{analysis.pooledVerdict === 'undecided' ? 'Pooled evidence is undecided (margin 0).' : `${pooledName} wins pooled by +${analysis.margin} of ${analysis.totalWeight}; ${analysis.flipK} of ${analysis.hiddenDecisiveFactIds.length} hidden facts must surface to flip the panel.`} <span className="lab-pill">{analysis.isHiddenProfile ? 'hidden profile' : 'NOT a hidden profile'}</span></div>}

      <footer className="lab-footer">
        <label>Slug <input value={slug} placeholder={`${scenario.id.replace(/-v\d+$/, '')}-v2`} onChange={(e) => setSlug(e.target.value)} /></label>
        <button type="button" onClick={() => void save()} disabled={!dirty || saving}>{saving ? 'Saving…' : 'Save as new scenario'}</button>
        <button type="button" className="link" onClick={() => setDraft(copyScenario(scenario))} disabled={!dirty}>Discard changes</button>
        {saveError && <div className="lab-error">{saveError}</div>}
      </footer>
    </section>
  )
}

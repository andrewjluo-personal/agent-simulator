import { useMemo, type ReactNode } from 'react'
import { useHighlight } from '../hooks/useHighlight'
import { candidateName, decisiveFactIds, factsById, holders, sharedFactIds } from '../truth'
import type { RunState, Turn } from '../types'
import { FactChip } from './FactChip'

type Props = {
  run: RunState
  turns: Turn[] // revealed turns only (seq ≤ playhead)
}

type SeenFirst = { seq: number; round: number; agentId: string }

export function FlowTimeline({ run, turns }: Props) {
  const hl = useHighlight()
  const scenario = run.scenario
  const rounds = run.config.rounds
  const byId = useMemo(() => factsById(scenario), [scenario])
  const shared = useMemo(() => sharedFactIds(scenario), [scenario])
  const decisive = useMemo(() => decisiveFactIds(scenario), [scenario])
  const agents = scenario.agents
  const agentName = (id: string) => agents.find((a) => a.id === id)?.name ?? id

  // Ghosting is derived from scenario + turns seen so far, so it works mid-playback (metrics arrive only at the end).
  const firstSeen = useMemo(() => {
    const out = new Map<string, SeenFirst>()
    for (const t of turns) for (const id of t.cited) if (!out.has(id)) out.set(id, { seq: t.seq, round: t.round, agentId: t.agentId })
    return out
  }, [turns])

  const cells = useMemo(() => {
    const m = new Map<string, Turn>()
    for (const t of turns) m.set(`${t.agentId}:${t.round}`, t)
    return m
  }, [turns])

  const decisiveByHolder = useMemo(() => {
    const out = new Map<string, string[]>()
    for (const id of decisive) for (const h of holders(scenario, id)) out.set(h, [...(out.get(h) ?? []), id])
    return out
  }, [scenario, decisive])

  const revealedRounds = turns.length ? Math.max(...turns.map((t) => t.round)) + 1 : 0
  const finished = run.status === 'done' && turns.length >= run.turns.length
  const neverSurfaced = finished ? [...decisive].filter((id) => !firstSeen.has(id)).sort() : []

  const mentions = useMemo(() => {
    let s = 0
    let u = 0
    for (const t of turns) for (const id of t.cited) if (shared.has(id)) s++; else u++
    return { shared: s, unique: u }
  }, [turns, shared])

  const surfacedDecisive = [...decisive].filter((id) => firstSeen.has(id))
  const firstDecisive = surfacedDecisive
    .map((id) => ({ id, ...firstSeen.get(id)! }))
    .sort((a, b) => a.seq - b.seq)[0]

  const agreement = run.metrics?.agreementByRound ?? []
  const accuracy = run.metrics?.accuracyByRound ?? []
  const showChart = finished && agreement.length > 0

  const enterFact = (factId: string, agentId: string) => hl.set({ factId, agentId })

  return (
    <div className="timeline">
      <div className="timeline-summary">
        <span>
          <b>{surfacedDecisive.length}</b> of <b>{decisive.size}</b> decisive facts surfaced
        </span>
        <span>
          shared mentions <b>{mentions.shared}</b> vs unique <b>{mentions.unique}</b>
        </span>
        <span>
          first decisive fact:{' '}
          {firstDecisive ? (
            <>
              round <b>{firstDecisive.round + 1}</b> by <b>{agentName(firstDecisive.agentId)}</b> ({firstDecisive.id})
            </>
          ) : (
            <em>none yet</em>
          )}
        </span>
      </div>

      <div className="timeline-grid" style={{ gridTemplateColumns: `110px repeat(${rounds}, minmax(0, 1fr))` }}>
        <div className="tl-head" />
        {Array.from({ length: rounds }, (_, r) => (
          <div key={r} className={`tl-head ${r < revealedRounds ? '' : 'future'}`}>
            Round {r + 1}
          </div>
        ))}
        {agents.map((a) => {
          const held = decisiveByHolder.get(a.id) ?? []
          return (
            <TimelineRow
              key={a.id}
              agentId={a.id}
              name={a.name}
              active={hl.agentId === a.id}
              onEnter={() => hl.set({ agentId: a.id })}
              onLeave={() => hl.set({ agentId: null })}
            >
              {Array.from({ length: rounds }, (_, r) => {
                const turn = cells.get(`${a.id}:${r}`)
                const started = r < revealedRounds
                const ghosts = held.filter((id) => {
                  const seen = firstSeen.get(id)
                  return !seen || seen.round > r
                })
                return (
                  <div key={r} className={`tl-cell ${started ? '' : 'future'}`}>
                    {turn?.cited.map((id) => {
                      const fact = byId.get(id)
                      if (!fact) return null
                      const first = firstSeen.get(id)
                      const isFirst = first?.seq === turn.seq
                      return (
                        <span key={id} className="tl-chipwrap">
                          <FactChip
                            fact={fact}
                            scenario={scenario}
                            shared={shared.has(id)}
                            className={`tl-chip ${hl.factId === id ? 'hl' : ''}`}
                            title={`${fact.text}${isFirst ? ' · first mention' : ''}`}
                            onPointerEnter={() => enterFact(id, a.id)}
                            onPointerLeave={hl.clear}
                          />
                          {isFirst && !shared.has(id) && <span className="tl-first">first</span>}
                        </span>
                      )
                    })}
                    {ghosts.map((id) => {
                      const fact = byId.get(id)
                      if (!fact) return null
                      return (
                        <FactChip
                          key={`ghost-${id}`}
                          fact={fact}
                          scenario={scenario}
                          shared={false}
                          ghost
                          className={`tl-chip ${hl.factId === id ? 'hl' : ''}`}
                          title={`${fact.text} · decisive, still unspoken in ${a.name}'s hand`}
                          onPointerEnter={() => enterFact(id, a.id)}
                          onPointerLeave={hl.clear}
                        />
                      )
                    })}
                  </div>
                )
              })}
            </TimelineRow>
          )
        })}
      </div>

      {neverSurfaced.length > 0 && (
        <div className="timeline-footer">
          Never surfaced:{' '}
          {neverSurfaced.map((id, i) => (
            <span key={id}>
              {i > 0 && ', '}
              <span
                className={`tl-never ${hl.factId === id ? 'hl' : ''}`}
                onPointerEnter={() => enterFact(id, holders(scenario, id)[0] ?? '')}
                onPointerLeave={hl.clear}
              >
                {id} ({holders(scenario, id).map(agentName).join(', ')})
              </span>
            </span>
          ))}
        </div>
      )}

      <ConvergenceChart
        agreement={showChart ? agreement : []}
        accuracy={showChart ? accuracy : []}
        rounds={rounds}
        correctName={run.metrics ? candidateName(scenario, run.metrics.correctCandidateId) : 'the correct candidate'}
      />
    </div>
  )
}

function TimelineRow({
  agentId,
  name,
  active,
  onEnter,
  onLeave,
  children,
}: {
  agentId: string
  name: string
  active: boolean
  onEnter: () => void
  onLeave: () => void
  children: ReactNode
}) {
  return (
    <>
      <div className={`tl-agent ${active ? 'hl' : ''}`} data-agent={agentId} onPointerEnter={onEnter} onPointerLeave={onLeave}>
        {name}
      </div>
      {children}
    </>
  )
}

const CW = 360
const CH = 120
const PAD = { l: 34, r: 12, t: 10, b: 24 }

function ConvergenceChart({ agreement, accuracy, rounds, correctName }: { agreement: number[]; accuracy: number[]; rounds: number; correctName: string }) {
  const n = Math.max(rounds, 1)
  const x = (i: number) => PAD.l + (n === 1 ? (CW - PAD.l - PAD.r) / 2 : (i * (CW - PAD.l - PAD.r)) / (n - 1))
  const y = (v: number) => PAD.t + (1 - v) * (CH - PAD.t - PAD.b)
  const path = (vals: number[]) => vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const empty = agreement.length === 0
  return (
    <div className="convergence">
      <div className="convergence-head">
        <h4>Convergence vs correctness</h4>
        <span className="legend">
          <i className="sw agree" /> agreement — share of the panel voting with the round's plurality
          <i className="sw acc" /> accuracy — share voting for {correctName}
        </span>
      </div>
      <svg width={CW} height={CH} className="convergence-svg">
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={CW - PAD.r} y1={y(v)} y2={y(v)} className="grid" />
            <text x={PAD.l - 6} y={y(v) + 3} textAnchor="end" className="tick">
              {Math.round(v * 100)}%
            </text>
          </g>
        ))}
        {Array.from({ length: n }, (_, i) => (
          <text key={i} x={x(i)} y={CH - 8} textAnchor="middle" className="tick">
            R{i + 1}
          </text>
        ))}
        {!empty && (
          <>
            <path d={path(agreement)} className="line agree" />
            <path d={path(accuracy)} className="line acc" />
            {agreement.map((v, i) => (
              <circle key={`a${i}`} cx={x(i)} cy={y(v)} r={3} className="dot agree" />
            ))}
            {accuracy.map((v, i) => (
              <circle key={`c${i}`} cx={x(i)} cy={y(v)} r={3} className="dot acc" />
            ))}
          </>
        )}
        {empty && (
          <text x={CW / 2} y={CH / 2} textAnchor="middle" className="tick">
            available when the run finishes
          </text>
        )}
      </svg>
    </div>
  )
}

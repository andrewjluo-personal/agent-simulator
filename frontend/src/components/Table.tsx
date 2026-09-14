import { useEffect, useMemo, useState, type CSSProperties, type MouseEvent } from 'react'
import { useHighlight } from '../hooks/useHighlight'
import type { Derived } from '../hooks/usePlayback'
import { candidateName, decisiveFactIds, favoredCandidate, factsById, sharedFactIds, tally } from '../truth'
import type { Fact, RunConfig, Scenario, Turn } from '../types'
import { CHIP_H, CHIP_W, candidateColor, chipColors } from './FactChip'

export { CANDIDATE_COLORS, candidateColor } from './FactChip'

export const W = 820
const CX = W / 2
const R = 225
const CHIP_GAP = 3
const TB_COLS = 8
const HAND_OFF_TOP = 40
const HAND_OFF_BOTTOM = 66
const CENTER_W = 250
const CENTER_COLS = 8

type Seat = { agentId: string; x: number; y: number; angle: number }
type Popover =
  | { kind: 'agent'; agentId: string }
  | { kind: 'fact'; agentId: string; factId: string; x: number; y: number }

function tableHeight(scenario: Scenario): number {
  const maxRows = Math.max(...scenario.agents.map((agent) => Math.ceil((scenario.distribution[agent.id]?.length ?? 0) / TB_COLS)), 1)
  const gridH = maxRows * (CHIP_H + CHIP_GAP)
  return 2 * (R + HAND_OFF_BOTTOM + gridH + 8)
}

function seats(scenario: Scenario, cy: number): Seat[] {
  const n = scenario.agents.length
  return scenario.agents.map((a, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n
    return { agentId: a.id, x: CX + R * Math.cos(angle), y: cy + R * Math.sin(angle), angle }
  })
}

type HandLayout = { x: number; y: number; cols: number }

function handLayout(seat: Seat, count: number, height: number): HandLayout {
  const dx = Math.cos(seat.angle)
  const dy = Math.sin(seat.angle)
  const cols = Math.abs(dx) < 0.5 ? TB_COLS : Math.max(2, Math.floor(((dx < 0 ? seat.x : W - seat.x) - 40 - 4) / (CHIP_W + CHIP_GAP)))
  const rows = Math.ceil(count / cols)
  const gridW = cols * (CHIP_W + CHIP_GAP)
  const gridH = rows * (CHIP_H + CHIP_GAP)
  if (Math.abs(dx) < 0.5) {
    const x = Math.min(Math.max(seat.x - gridW / 2, 4), W - gridW - 4)
    const y = dy < 0 ? seat.y - HAND_OFF_TOP - gridH : seat.y + HAND_OFF_BOTTOM
    return { x, y, cols }
  }
  const x = dx < 0 ? seat.x - 40 - gridW : seat.x + 40
  const cy = seat.y + dy * (gridH / 2)
  const y = Math.min(Math.max(cy - gridH / 2, 4), height - gridH - 4)
  return { x, y, cols }
}

type ChipPos = { key: string; factId: string; agentId: string; x: number; y: number; inCenter: boolean; dim: boolean }

function placeNear(anchorX: number, anchorY: number, w: number, h: number, preferRight: boolean, height: number): { left: number; top: number } {
  const left = preferRight ? anchorX + 14 : anchorX - w - 14
  const top = anchorY - 20
  return {
    left: Math.min(Math.max(left, 4), W - w - 4),
    top: Math.min(Math.max(top, 4), height - h - 4),
  }
}

type Props = {
  scenario: Scenario
  config: RunConfig | null
  derived: Derived
  status: 'idle' | 'playing' | 'paused' | 'finished'
  round: number
  live?: boolean
}

export function Table({ scenario, config, derived, status, round, live }: Props) {
  const [popover, setPopover] = useState<Popover | null>(null)
  const hl = useHighlight()
  const byId = useMemo(() => factsById(scenario), [scenario])
  const shared = useMemo(() => sharedFactIds(scenario), [scenario])
  const decisive = useMemo(() => decisiveFactIds(scenario), [scenario])
  const height = useMemo(() => tableHeight(scenario), [scenario])
  const cy = height / 2 + 6
  const seatList = useMemo(() => seats(scenario, cy), [scenario, cy])
  const { commonGround, citedBy, currentTurn, latestVotes, finished } = derived

  const centerOrder = useMemo(() => {
    const order: string[] = []
    for (const t of derived.revealedTurns) for (const id of t.cited) if (!order.includes(id)) order.push(id)
    return order
  }, [derived.revealedTurns])

  const centerTop = cy + 28
  const centerGridX = CX - (CENTER_COLS * (CHIP_W + CHIP_GAP)) / 2

  const chips: ChipPos[] = useMemo(() => {
    const out: ChipPos[] = []
    for (const seat of seatList) {
      const hand = scenario.distribution[seat.agentId] ?? []
      const layout = handLayout(seat, hand.length, height)
      hand.forEach((factId, i) => {
        const owner = citedBy.get(factId)
        const inCenter = owner === seat.agentId
        if (inCenter) {
          const idx = centerOrder.indexOf(factId)
          out.push({
            key: `${seat.agentId}:${factId}`,
            factId,
            agentId: seat.agentId,
            x: centerGridX + (idx % CENTER_COLS) * (CHIP_W + CHIP_GAP),
            y: centerTop + Math.floor(idx / CENTER_COLS) * (CHIP_H + CHIP_GAP),
            inCenter: true,
            dim: false,
          })
        } else {
          out.push({
            key: `${seat.agentId}:${factId}`,
            factId,
            agentId: seat.agentId,
            x: layout.x + (i % layout.cols) * (CHIP_W + CHIP_GAP),
            y: layout.y + Math.floor(i / layout.cols) * (CHIP_H + CHIP_GAP),
            inCenter: false,
            dim: commonGround.has(factId),
          })
        }
      })
    }
    return out
  }, [seatList, scenario, citedBy, centerOrder, commonGround, centerGridX, centerTop, height])

  const voteTally = tally([...latestVotes.values()].map((v) => v.choice), scenario)
  const hasVotes = latestVotes.size > 0
  const leader = hasVotes
    ? scenario.candidates.reduce((best, c) => (voteTally[c.id] > (voteTally[best.id] ?? 0) ? c : best))
    : null

  const inspectedAgent = popover?.kind === 'agent' ? scenario.agents.find((a) => a.id === popover.agentId) : null
  const inspectedFact =
    popover?.kind === 'fact'
      ? {
          fact: byId.get(popover.factId),
          x: popover.x,
          y: popover.y,
        }
      : null

  useEffect(() => {
    if (!popover) return
    const onPointerDown = (e: PointerEvent) => {
      if (e.target instanceof Element && e.target.closest('[data-popover-root]')) return
      setPopover(null)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPopover(null)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [popover])

  useEffect(() => {
    setPopover(null)
  }, [scenario])

  const openFactPopover = (agentId: string, factId: string, x: number, y: number) => {
    setPopover((current) =>
      current?.kind === 'fact' && current.agentId === agentId && current.factId === factId
        ? null
        : { kind: 'fact', agentId, factId, x, y },
    )
  }

  return (
    <div className="table-wrap" style={{ width: W, height }}>
      <svg className="table-svg" width={W} height={height}>
        <circle cx={CX} cy={cy} r={R - 62} className="table-felt" />
        {seatList.map((s) => {
          const agent = scenario.agents.find((a) => a.id === s.agentId)!
          const speaking = currentTurn?.agentId === s.agentId && status === 'playing'
          const vote = latestVotes.get(s.agentId)
          const reading = !!live && !derived.revealedTurns.length && !vote
          return (
            <g
              key={s.agentId}
              className={`seat ${speaking ? 'speaking' : ''} ${hl.agentId === s.agentId ? 'hl' : ''}`}
              onPointerDown={(e) => e.stopPropagation()}
              onPointerEnter={() => hl.set({ agentId: s.agentId })}
              onPointerLeave={() => hl.set({ agentId: null })}
              onClick={(e) => {
                e.stopPropagation()
                setPopover((current) =>
                  current?.kind === 'agent' && current.agentId === s.agentId ? null : { kind: 'agent', agentId: s.agentId },
                )
              }}
            >
              <circle cx={s.x} cy={s.y} r={26} className={`avatar${reading ? ' reading' : ''}`} />
              <text x={s.x} y={s.y + 5} textAnchor="middle" className="avatar-initial">
                {agent.name[0]}
              </text>
              <text x={s.x} y={s.y + 44} textAnchor="middle" className="seat-name">
                {agent.name}
              </text>
              <text x={s.x} y={s.y + 57} textAnchor="middle" className="seat-role">
                {agent.role}
              </text>
              {vote && (
                <g
                  key={vote.round}
                  className={`lean-badge ${vote.saidLean !== 'undecided' && vote.saidLean !== vote.choice ? 'lean-diverge' : ''}`}
                >
                  {vote.saidLean !== 'undecided' && vote.saidLean !== vote.choice && (
                    <title>
                      said {candidateName(scenario, vote.saidLean)}, voted {candidateName(scenario, vote.choice)}
                    </title>
                  )}
                  <rect x={s.x + 12} y={s.y - 34} width={34} height={16} rx={8} fill={candidateColor(scenario, vote.choice)} />
                  <text x={s.x + 29} y={s.y - 22} textAnchor="middle">
                    {vote.choice === 'undecided' ? '?' : candidateName(scenario, vote.choice)}
                  </text>
                </g>
              )}
            </g>
          )
        })}
      </svg>

      <div className="center-box" style={{ left: CX - CENTER_W / 2, top: cy - 72, width: CENTER_W }}>
        <div className="center-round">
          {config ? (status === 'idle' ? 'Ready' : `Round ${round} / ${config.rounds}`) : 'Ready'}
          {hasVotes && (
            <span className="center-sub">
              {' '}
              · private votes {derived.completedRounds === 0 ? 'before discussion' : `after round ${derived.completedRounds}`}
            </span>
          )}
        </div>
        <div className="cand-row">
          {scenario.candidates.map((c) => (
            <div
              key={c.id}
              className={`cand-card ${leader?.id === c.id ? 'leading' : ''}`}
              style={{ borderColor: candidateColor(scenario, c.id) }}
            >
              <div className="cand-name" style={{ color: candidateColor(scenario, c.id) }}>
                {c.name}
              </div>
              <div className="cand-tally">{hasVotes ? voteTally[c.id] : '–'}</div>
            </div>
          ))}
        </div>
        <div className="center-label">common ground · {commonGround.size} facts</div>
      </div>

      <div className="chip-layer">
        {chips.map((c) => {
          const fact = byId.get(c.factId)
          if (!fact) return null
          const unspokenDecisive = finished && decisive.has(c.factId) && !commonGround.has(c.factId)
          return (
            <Chip
              key={c.key}
              fact={fact}
              scenario={scenario}
              shared={shared.has(fact.id)}
              x={c.x}
              y={c.y}
              inCenter={c.inCenter}
              dim={c.dim}
              pulse={unspokenDecisive}
              fresh={c.inCenter && currentTurn?.cited.includes(c.factId) === true}
              hl={hl.factId === c.factId || (hl.factId === null && hl.agentId === c.agentId)}
              onEnter={() => hl.set({ factId: c.factId, agentId: c.agentId })}
              onLeave={hl.clear}
              onClick={(e) => {
                e.stopPropagation()
                openFactPopover(c.agentId, c.factId, c.x + CHIP_W / 2, c.y + CHIP_H / 2)
              }}
            />
          )
        })}
      </div>

      {currentTurn && status !== 'idle' && (
        <SpeechBubble turn={currentTurn} seat={seatList.find((s) => s.agentId === currentTurn.agentId)!} scenario={scenario} height={height} />
      )}

      {inspectedAgent && (() => {
        const seat = seatList.find((s) => s.agentId === inspectedAgent.id)!
        const position = placeNear(seat.x, seat.y, 340, 280, seat.x <= CX, height)
        return (
          <div
            className="popover hand-popover"
            data-popover-root
            style={{ left: position.left, top: position.top, width: 340 }}
          >
            <div className="hand-popover-head">
              <strong>{inspectedAgent.name}</strong> · {inspectedAgent.role}
              <span className="muted"> — {scenario.distribution[inspectedAgent.id]?.length ?? 0} facts in hand</span>
            </div>
            <button className="popover-close" type="button" aria-label="Close popover" onClick={() => setPopover(null)}>
              ×
            </button>
            <ul>
              {(scenario.distribution[inspectedAgent.id] ?? [])
                .map((id) => byId.get(id))
                .filter((f): f is Fact => Boolean(f))
                .sort((a, b) => Number(shared.has(a.id)) - Number(shared.has(b.id)))
                .map((f) => (
                  <li
                    key={f.id}
                    className={shared.has(f.id) ? 'shared' : 'unique'}
                    role="button"
                    tabIndex={0}
                    onClick={() => openFactPopover(inspectedAgent.id, f.id, seat.x, seat.y)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        openFactPopover(inspectedAgent.id, f.id, seat.x, seat.y)
                      }
                    }}
                  >
                    <span className="fact-tag" style={{ background: candidateColor(scenario, favoredCandidate(f, scenario)) }}>
                      {f.id}
                    </span>
                    <span className="fact-kind">{shared.has(f.id) ? 'shared' : 'unique'}</span>
                    <span className="fact-weight">w{f.weight}</span>
                    {commonGround.has(f.id) && <span className="fact-said">said</span>}
                    <span className="fact-text">{f.text}</span>
                  </li>
                ))}
            </ul>
          </div>
        )
      })()}
      {inspectedFact?.fact && (() => {
        const fact = inspectedFact.fact
        const position = placeNear(inspectedFact.x, inspectedFact.y, 280, 150, inspectedFact.x - CHIP_W / 2 <= CX, height)
        const holders = scenario.agents.filter((agent) => (scenario.distribution[agent.id] ?? []).includes(fact.id))
        return (
          <div
            className="popover fact-popover"
            data-popover-root
            style={{ left: position.left, top: position.top, width: 280 }}
          >
            <button className="popover-close" type="button" aria-label="Close popover" onClick={() => setPopover(null)}>
              ×
            </button>
            <div className="fact-popover-head">
              <span className="fact-tag" style={{ background: candidateColor(scenario, favoredCandidate(fact, scenario)) }}>
                {fact.id}
              </span>
              <span className="fact-kind">{shared.has(fact.id) ? 'shared' : 'unique'}</span>
              <span className="fact-weight">w{fact.weight}</span>
              {commonGround.has(fact.id) && <span className="fact-said">said</span>}
            </div>
            <div className="fact-popover-text">{fact.text}</div>
            <div className="fact-held-by muted">held by: {holders.map((agent) => agent.name).join(', ')}</div>
            {decisive.has(fact.id) && <div className="fact-decisive muted">decisive</div>}
          </div>
        )
      })()}
    </div>
  )
}

type ChipProps = {
  fact: Fact
  scenario: Scenario
  shared: boolean
  x: number
  y: number
  inCenter: boolean
  dim: boolean
  pulse: boolean
  fresh: boolean
  hl: boolean
  onEnter: () => void
  onLeave: () => void
  onClick: (e: MouseEvent<HTMLDivElement>) => void
}

function Chip({ fact, scenario, shared, x, y, inCenter, dim, pulse, fresh, hl, onEnter, onLeave, onClick }: ChipProps) {
  const style: CSSProperties = {
    transform: `translate(${x}px, ${y}px)`,
    width: CHIP_W,
    height: CHIP_H,
    ...chipColors(fact, scenario, shared),
  }
  const cls = ['chip', inCenter ? 'in-center' : '', dim ? 'dim' : '', pulse ? 'pulse' : '', fresh ? 'fresh' : '', hl ? 'hl' : ''].join(' ')
  return (
    <div
      className={cls}
      style={style}
      onPointerDown={(e) => e.stopPropagation()}
      onPointerEnter={onEnter}
      onPointerLeave={onLeave}
      onClick={onClick}
    >
      {fact.id}
    </div>
  )
}

function SpeechBubble({ turn, seat, scenario, height }: { turn: Turn; seat: Seat; scenario: Scenario; height: number }) {
  const width = 250
  const dx = Math.cos(seat.angle)
  const dy = Math.sin(seat.angle)
  let left: number
  let top: number | undefined
  let bottom: number | undefined
  if (Math.abs(dx) < 0.5) {
    left = seat.x + (dx >= 0 ? 60 : -60 - width)
    top = seat.y - 30
  } else {
    left = Math.min(Math.max(seat.x - width / 2, 4), W - width - 4)
    if (dy > 0) bottom = height - (seat.y - 70)
    else top = seat.y + 70
  }
  left = Math.min(Math.max(left, 4), W - width - 4)
  const shared = sharedFactIds(scenario)
  return (
    <div className="bubble" style={{ left, width, ...(top === undefined ? { bottom } : { top }) }} key={turn.seq}>
      <div className="bubble-text">{turn.sentences.length ? turn.sentences.join(' ') : <em>(said nothing)</em>}</div>
      <div className="bubble-meta">
        {turn.cited.map((id) => (
          <span key={id} className={`cite ${shared.has(id) ? 'shared' : 'unique'}`}>
            {id}
          </span>
        ))}
        {turn.hallucinated.map((id) => (
          <span key={id} className="cite halluc" title="cited a fact the speaker does not hold">
            {id}
          </span>
        ))}
        {turn.lean !== 'undecided' && (
          <span className="lean" style={{ color: candidateColor(scenario, turn.lean) }}>
            → {candidateName(scenario, turn.lean)}
          </span>
        )}
      </div>
    </div>
  )
}

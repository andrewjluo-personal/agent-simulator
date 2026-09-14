import type { CSSProperties, MouseEvent, PointerEvent } from 'react'
import { favoredCandidate } from '../truth'
import type { Fact, Scenario } from '../types'

export const CHIP_W = 27
export const CHIP_H = 16

export const CANDIDATE_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#a855f7', '#ef4444']

export function candidateColor(scenario: Scenario, candidateId: string | null): string {
  const idx = scenario.candidates.findIndex((c) => c.id === candidateId)
  return idx < 0 ? '#9ca3af' : CANDIDATE_COLORS[idx % CANDIDATE_COLORS.length]
}

/** Colours for a fact chip: grey body with a candidate-tinted edge for shared facts, solid candidate colour for unique ones. */
export function chipColors(fact: Fact, scenario: Scenario, shared: boolean): CSSProperties {
  if (fact.valence === 'neutral') {
    return {
      background: '#9ca3af',
      color: '#fff',
      boxShadow: shared ? 'inset 3px 0 0 #6b7280' : undefined,
    }
  }
  const color = candidateColor(scenario, favoredCandidate(fact, scenario))
  return {
    background: shared ? '#e5e7eb' : color,
    color: shared ? '#374151' : '#fff',
    boxShadow: shared ? `inset 3px 0 0 ${color}` : undefined,
  }
}

type Props = {
  fact: Fact
  scenario: Scenario
  shared: boolean
  className?: string
  style?: CSSProperties
  title?: string
  ghost?: boolean
  onClick?: (e: MouseEvent<HTMLDivElement>) => void
  onPointerDown?: (e: PointerEvent<HTMLDivElement>) => void
  onPointerEnter?: () => void
  onPointerLeave?: () => void
}

export function FactChip({ fact, scenario, shared, className, style, title, ghost, onClick, onPointerDown, onPointerEnter, onPointerLeave }: Props) {
  const colors = chipColors(fact, scenario, shared)
  const ghostStyle: CSSProperties = ghost
    ? { background: 'transparent', color: colors.background as string, border: `1.5px dashed ${colors.background as string}`, boxShadow: undefined }
    : {}
  return (
    <div
      className={['chip', ghost ? 'ghost' : '', className ?? ''].join(' ').trim()}
      style={{ width: CHIP_W, height: CHIP_H, ...colors, ...ghostStyle, ...style }}
      title={title}
      onClick={onClick}
      onPointerDown={onPointerDown}
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
    >
      {fact.id}
    </div>
  )
}

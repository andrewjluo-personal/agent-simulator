import { createContext, useCallback, useContext, useMemo, useState } from 'react'

export type Highlight = { factId: string | null; agentId: string | null }

export type HighlightState = Highlight & {
  set: (next: Partial<Highlight>) => void
  clear: () => void
}

const NONE: Highlight = { factId: null, agentId: null }

export const HighlightContext = createContext<HighlightState>({
  ...NONE,
  set: () => {},
  clear: () => {},
})

export function useHighlightState(): HighlightState {
  const [hl, setHl] = useState<Highlight>(NONE)
  const set = useCallback((next: Partial<Highlight>) => setHl((h) => ({ ...h, ...next })), [])
  const clear = useCallback(() => setHl(NONE), [])
  return useMemo(() => ({ ...hl, set, clear }), [hl, set, clear])
}

export function useHighlight(): HighlightState {
  return useContext(HighlightContext)
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createRun, getRun, stepRun } from '../api'
import type { RunConfig, RunState, Turn, Vote } from '../types'

export const TURN_MS = 2600
const POLL_MS = 750

export type Derived = {
  revealedTurns: Turn[]
  currentTurn: Turn | null
  commonGround: Set<string>
  citedBy: Map<string, string>
  completedRounds: number
  latestVotes: Map<string, Vote>
  finished: boolean
}

function mergeTurns(existing: Turn[], incoming: Turn[]): Turn[] {
  const bySeq = new Map(existing.map((t) => [t.seq, t]))
  for (const t of incoming) bySeq.set(t.seq, t)
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq)
}

export function usePlayback() {
  const [run, setRun] = useState<RunState | null>(null)
  const [revealed, setRevealed] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const runRef = useRef<RunState | null>(null)
  useEffect(() => {
    runRef.current = run
  }, [run])
  const lastRevealAt = useRef(0)

  const loadRun = useCallback((next: RunState, autoplay: boolean) => {
    setRun(next)
    lastRevealAt.current = 0
    setRevealed(0)
    setPlaying(autoplay)
    setError(null)
  }, [])

  const startLive = useCallback(
    async (config: RunConfig) => {
      try {
        const created = await createRun(config)
        loadRun(created, true)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    },
    [loadRun],
  )

  const replayById = useCallback(
    async (id: string) => {
      try {
        loadRun(await getRun(id), true)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    },
    [loadRun],
  )

  // Drive the run forward one round per call; a step can take ~10-15 s, so
  // iterate sequentially and never overlap steps from this tab.
  useEffect(() => {
    const id = run?.id
    if (!id || run?.status === 'done' || run?.status === 'error') return
    let cancelled = false
    const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))
    const loop = async () => {
      while (!cancelled) {
        const current = runRef.current
        if (!current || current.id !== id) return
        if (current.status === 'done' || current.status === 'error') return
        const turns = current.turns ?? []
        const sinceSeq = turns.length ? turns[turns.length - 1].seq : -1
        try {
          const delta = await stepRun(id, sinceSeq)
          if (cancelled) return
          setRun((prev) =>
            prev && prev.id === id
              ? { ...delta, turns: mergeTurns(prev.turns ?? [], delta.turns ?? []), votes: delta.votes ?? [] }
              : prev,
          )
        } catch (cause) {
          if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause))
        }
        await sleep(POLL_MS)
      }
    }
    void loop()
    return () => {
      cancelled = true
    }
  }, [run?.id, run?.status])

  // Reveal one turn per tick so replays and live runs animate identically.
  useEffect(() => {
    if (!playing || !run) return
    const turns = run.turns ?? []
    if (revealed >= turns.length) {
      if (run.status === 'done' || run.status === 'error') setPlaying(false)
      return
    }
    const wait = revealed === 0 ? 300 : Math.max(0, TURN_MS - (Date.now() - lastRevealAt.current))
    const timer = window.setTimeout(() => {
      lastRevealAt.current = Date.now()
      setRevealed((r) => r + 1)
    }, wait)
    return () => window.clearTimeout(timer)
  }, [playing, revealed, run])

  const derived = useMemo<Derived>(() => {
    if (!run) {
      return {
        revealedTurns: [],
        currentTurn: null,
        commonGround: new Set(),
        citedBy: new Map(),
        completedRounds: 0,
        latestVotes: new Map(),
        finished: false,
      }
    }
    const turns = run.turns ?? []
    const votes = run.votes ?? []
    const revealedTurns = turns.slice(0, revealed)
    const commonGround = new Set<string>()
    const citedBy = new Map<string, string>()
    for (const t of revealedTurns) {
      for (const id of t.cited) {
        commonGround.add(id)
        if (!citedBy.has(id)) citedBy.set(id, t.agentId)
      }
    }
    const n = run.scenario.agents.length
    const completedRounds = n ? Math.floor(revealed / n) : 0
    const latestVotes = new Map<string, Vote>()
    for (const v of votes) if (v.round === completedRounds - 1) latestVotes.set(v.agentId, v)
    const finished = run.status === 'done' && revealed >= turns.length
    return {
      revealedTurns,
      currentTurn: revealedTurns.length ? revealedTurns[revealedTurns.length - 1] : null,
      commonGround,
      citedBy,
      completedRounds,
      latestVotes,
      finished,
    }
  }, [run, revealed])

  const skipToEnd = useCallback(() => {
    lastRevealAt.current = Date.now()
    setRevealed(runRef.current?.turns?.length ?? 0)
  }, [])

  const restart = useCallback(() => {
    lastRevealAt.current = 0
    setRevealed(0)
    setPlaying(true)
  }, [])

  const clear = useCallback(() => {
    setRun(null)
    lastRevealAt.current = 0
    setRevealed(0)
    setPlaying(false)
    setError(null)
  }, [])

  return { run, revealed, playing, error, derived, loadRun, startLive, replayById, setPlaying, skipToEnd, restart, clear }
}

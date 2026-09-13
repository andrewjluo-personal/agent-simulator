import type { BatchState, DemoSnapshot, Paradigm, RunConfig, RunState, Scenario } from './types'

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export type Health = {
  status: string
  env: string
  checks: Record<string, string>
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    if (response.status === 429) {
      const body = (await response.json().catch(() => null)) as { detail?: string } | null
      throw new Error(body?.detail ?? `Request rate-limited: ${response.status}`)
    }
    throw new Error(`${init?.method ?? 'GET'} ${path} failed: ${response.status}`)
  }
  return (await response.json()) as T
}

export const getHealth = () => request<Health>('/api/health')
export const getScenario = () => request<Scenario>('/api/scenario')
export const listScenarios = () => request<Scenario[]>('/api/scenarios')
export const getScenarioById = (id: string) => request<Scenario>(`/api/scenarios/${encodeURIComponent(id)}`)
export const listParadigms = () =>
  request<{ id: Paradigm; label: string; description: string }[]>('/api/paradigms')
export const resetScenario = (id: string) =>
  request<Scenario>(`/api/scenarios/${encodeURIComponent(id)}/reset`, { method: 'POST' })
export const getDemo = (scenarioId?: string) =>
  request<DemoSnapshot>(`/api/demo${scenarioId ? `?scenarioId=${encodeURIComponent(scenarioId)}` : ''}`)
export function normalizeRun(run: RunState): RunState {
  return { ...run, turns: run.turns ?? [], votes: run.votes ?? [] }
}
export const getRun = (id: string, sinceSeq = -1) =>
  request<RunState>(`/api/runs/${encodeURIComponent(id)}?since_seq=${sinceSeq}`).then(normalizeRun)
export const getBatch = (id: string) => request<BatchState>(`/api/batches/${encodeURIComponent(id)}`)
export const createRun = (config: RunConfig) =>
  request<RunState>('/api/runs', { method: 'POST', body: JSON.stringify(config) }).then(normalizeRun)
export const createBatch = (config: RunConfig, n: number) =>
  request<BatchState>('/api/runs/batch', { method: 'POST', body: JSON.stringify({ config, n }) })

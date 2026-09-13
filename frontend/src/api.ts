import type { BatchState, DemoSnapshot, RunConfig, RunState, Scenario } from './types'

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
    throw new Error(`${init?.method ?? 'GET'} ${path} failed: ${response.status}`)
  }
  return (await response.json()) as T
}

export const getHealth = () => request<Health>('/api/health')
export const getScenario = () => request<Scenario>('/api/scenario')
export const getDemo = () => request<DemoSnapshot>('/api/demo')
export const getRun = (id: string, sinceSeq = -1) =>
  request<RunState>(`/api/runs/${encodeURIComponent(id)}?since_seq=${sinceSeq}`)
export const getBatch = (id: string) => request<BatchState>(`/api/batches/${encodeURIComponent(id)}`)
export const createRun = (config: RunConfig) =>
  request<RunState>('/api/runs', { method: 'POST', body: JSON.stringify(config) })
export const createBatch = (config: RunConfig, n: number) =>
  request<BatchState>('/api/runs/batch', { method: 'POST', body: JSON.stringify({ config, n }) })

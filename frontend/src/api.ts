import type {
  BatchState,
  DemoSnapshot,
  RunConfig,
  RunState,
  Scenario,
  ScenarioAnalysis,
  ValidationJob,
} from './types'

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export type Health = {
  status: string
  env: string
  checks: Record<string, string>
}

export class ApiError extends Error {
  status: number

  constructor(method: string, path: string, status: number) {
    super(`${method} ${path} failed: ${status}`)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    throw new ApiError(init?.method ?? 'GET', path, response.status)
  }
  return (await response.json()) as T
}

export const getHealth = () => request<Health>('/api/health')
export const getScenario = () => request<Scenario>('/api/scenario')
export const listScenarios = () => request<Scenario[]>('/api/scenarios')
export const getScenarioById = (id: string) => request<Scenario>(`/api/scenarios/${encodeURIComponent(id)}`)
export const getScenarioAnalysis = (id: string) =>
  request<ScenarioAnalysis>(`/api/scenarios/${encodeURIComponent(id)}/analysis`)
export const analyzeScenario = (draft: Scenario) =>
  request<ScenarioAnalysis>('/api/scenarios/analyze', { method: 'POST', body: JSON.stringify(draft) })
export const forkScenario = (input: { baseId: string; scenario: Scenario; slug?: string }) =>
  request<Scenario>('/api/scenarios', { method: 'POST', body: JSON.stringify(input) })
export const startValidation = (id: string, discussion: boolean) =>
  request<ValidationJob>(
    `/api/scenarios/${encodeURIComponent(id)}/validate?discussion=${discussion ? 'true' : 'false'}`,
    { method: 'POST' },
  )
export const getValidationJob = (jobId: string) => request<ValidationJob>(`/api/validation-jobs/${encodeURIComponent(jobId)}`)
export const getScenarioValidationJob = async (id: string): Promise<ValidationJob | null> => {
  try {
    return await request<ValidationJob>(`/api/scenarios/${encodeURIComponent(id)}/validation-job`)
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 404) return null
    throw cause
  }
}
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

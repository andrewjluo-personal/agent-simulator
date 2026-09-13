const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export type Greeting = {
  id: number
  message: string
  created_at: string
  queueMessageId?: string | null
}

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
export const listGreetings = () => request<Greeting[]>('/api/greetings')
export const createGreeting = (message: string) =>
  request<Greeting>('/api/greetings', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })

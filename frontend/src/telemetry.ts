const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/** Correlates every event from one page visit; grep it in Vercel Logs. */
export const sessionId = crypto.randomUUID()

type Level = 'info' | 'warning' | 'error'

export function track(name: string, context: Record<string, unknown> = {}, level: Level = 'info') {
  const body = JSON.stringify({ level, name, sessionId, context })
  // keepalive so events survive the page being closed mid-flight.
  void fetch(`${baseUrl}/api/client-logs`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body,
    keepalive: true,
  }).catch(() => undefined)
}

export function installGlobalHandlers() {
  window.addEventListener('error', (event) => {
    track('window.error', { message: event.message, source: event.filename }, 'error')
  })
  window.addEventListener('unhandledrejection', (event) => {
    track('window.unhandledrejection', { reason: String(event.reason) }, 'error')
  })
}

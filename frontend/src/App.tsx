import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { createGreeting, getHealth, listGreetings, type Greeting, type Health } from './api'

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [greetings, setGreetings] = useState<Greeting[]>([])
  const [message, setMessage] = useState('Hello World')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [nextHealth, nextGreetings] = await Promise.all([getHealth(), listGreetings()])
      setHealth(nextHealth)
      setGreetings(nextGreetings)
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setPending(true)
    try {
      await createGreeting(message)
      await refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setPending(false)
    }
  }

  return (
    <main>
      <h1>agent-simulator</h1>
      <p>React + TypeScript frontend, FastAPI backend, Neon Postgres, Vercel Queues.</p>

      <section>
        <h2>Health</h2>
        <pre>{health ? JSON.stringify(health, null, 2) : 'loading…'}</pre>
      </section>

      <section>
        <h2>Greetings</h2>
        <form onSubmit={submit}>
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            maxLength={280}
            required
          />
          <button type="submit" disabled={pending}>
            {pending ? 'Saving…' : 'Save + enqueue'}
          </button>
        </form>
        <ul>
          {greetings.map((greeting) => (
            <li key={greeting.id}>
              {greeting.message} <small>{new Date(greeting.created_at).toLocaleString()}</small>
            </li>
          ))}
        </ul>
      </section>

      {error && <p role="alert">{error}</p>}
    </main>
  )
}

export default App

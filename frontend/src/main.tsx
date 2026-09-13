import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { installGlobalHandlers, track } from './telemetry'

installGlobalHandlers()
track('app.loaded', { path: window.location.pathname })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

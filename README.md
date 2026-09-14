# agent-simulator

Hello-World scaffold for the stack:

| Piece | Tech |
| --- | --- |
| Frontend | Vite + React 19 + TypeScript (`frontend/`) |
| Backend | FastAPI on the Vercel Python runtime (`backend/`) |
| Database | Neon Postgres (`DATABASE_URL`) |
| Async work | Vercel Queues (topic `greetings`) |
| Telemetry | Structured JSON logs → Vercel Logs / Observability |

## Layout

```
frontend/   Vite app, deployed as its own Vercel project
backend/    FastAPI app, deployed as a single Vercel Function
  app/main.py        routes (entrypoint declared in pyproject [tool.vercel])
  app/db.py          Neon access via psycopg3
  app/queues.py      Vercel Queues HTTP API client
  app/telemetry.py   JSON log formatter + request middleware
  scripts/init_db.py schema bootstrap
  scripts/worker.py  poll-mode queue consumer for local dev
```

## Local development

Backend:

```bash
cd backend
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env          # set DATABASE_URL to your Neon branch
set -a && source .env && set +a
python scripts/init_db.py
uvicorn app.main:app --reload --port 8000
```

Frontend (proxies `/api` to `http://127.0.0.1:8000`):

```bash
cd frontend
npm install
npm run dev
```

## Endpoints

- `GET /api/health` — API, Neon, and queue configuration status
- `GET /api/greetings` — recent rows
- `POST /api/greetings` — insert a row, then publish to the `greetings` topic
- `POST /api/queues/greetings` — push callback invoked by Vercel Queues

## Deployment

Two Vercel projects share this repo:

- frontend → root directory `frontend`, env `VITE_API_BASE_URL` = backend URL
- backend → root directory `backend`, env `DATABASE_URL`, `ALLOWED_ORIGINS`, `VERCEL_QUEUE_REGION`,
  optional `RUN_RATE_LIMIT_PER_MIN` (default 6, 0 disables), `AUTO_RUN_ON_LOAD` (default 1)

`VERCEL_OIDC_TOKEN` is injected by Vercel at runtime and authenticates queue calls; pull it locally
with `vercel env pull` if you want to exercise queues outside Vercel.

## Demo runs & engine version

Every run is stamped with `ENGINE_VERSION` (`backend/app/engine_version.py`) — the first 12 hex of
sha256 over `app/prompts.py`, `app/orchestrator.py`, `app/truth.py`, `app/paradigms.py`, and
`app/samples.py`. The landing page is live-first: it auto-starts a real run on load (once per
browser session, unless `AUTO_RUN_ON_LOAD=0`), and `/api/demo` lists the most recent *finished*
runs — demo or live — stamped with the current version. Any deploy touching those files makes
older runs disappear from the recent list until new ones finish.

`scripts/seed_demo.py` is optional/manual — nothing in deploy calls it. Use it to pre-fill the
recent list before a review or demo (idempotent — tops up to N done runs per paradigm and deletes
stale-version demo rows; `--keep-stale` to keep them, `--reset-demo` to wipe all demos):

```
cd backend && DATABASE_URL=<prod> LLM_PROVIDER=anthropic \
  .venv/bin/python scripts/seed_demo.py --provider anthropic \
  --scenario hiring-panel-v1 --per-paradigm 5
```

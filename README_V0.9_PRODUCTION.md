# Job Hunter Agent v0.9 — Production Architecture

This release upgrades v0.8 from a dashboard prototype into a deployable single-user production application.

## Runtime
- Next.js + React + TypeScript dashboard
- FastAPI API with HTTP-only signed dashboard session
- PostgreSQL persistence and indexes
- APScheduler worker for recurring scans
- Exa as primary search provider
- TinyFish Search as automatic fallback when Exa fails or returns no results
- Fireworks Qwen 3.7 Plus primary model with DeepSeek V4 Flash fallback
- SMTP email notifications for scan completion, scan failure, settings changes, and application-status changes
- Human approval required before any application submission

## Secrets
Never commit `.env`. Required production secrets include `EXA_API_KEY`, `TINYFISH_API_KEY`, `FIREWORKS_API_KEY`, `SMTP_PASSWORD`, `POSTGRES_PASSWORD`, `DASHBOARD_PASSWORD`, and `DASHBOARD_SESSION_SECRET`.

The TinyFish MCP/CLI connect command is for connecting coding agents. The application uses the TinyFish REST Search API for runtime failover. TinyFish REST requests authenticate with `X-API-Key`.

## Start
1. Copy `.env.example` to `.env` and replace every placeholder.
2. Set `NEXT_PUBLIC_API_URL` to the public HTTPS URL of the API (or put frontend/API behind one reverse proxy).
3. Run `docker compose -f docker-compose.v0.9.yml up -d --build`.
4. Verify `/health` and `/ready` on the API.
5. Open the dashboard and sign in with `DASHBOARD_PASSWORD`.

For internet deployment, terminate TLS at a reverse proxy/load balancer and set `COOKIE_SECURE=true`.

## Vercel + Railway deployment

Vercel hosts the `frontend` directory only. Deploy the root Dockerfile as the
FastAPI backend on Railway, and provision Railway PostgreSQL and Redis services.
Run the scheduler as a second Railway service using `python -m app.scheduler`.
Set `NEXT_PUBLIC_API_URL` in Vercel to the public Railway API URL. Set
`CORS_ORIGINS` in Railway to the exact Vercel URL. Add all runtime secrets from
`.env.example` to Railway only; never upload `.env` or provider credentials to
GitHub or Vercel.


## v1.2 Production DB & Cache

The backend now uses a PostgreSQL connection pool (`psycopg-pool`) with configurable min/max connections, idempotent migrations, production indexes, Redis-backed short-TTL response caching, Redis rate limiting, and a distributed lock preventing concurrent agent runs. PostgreSQL remains the source of truth; Redis is disposable cache/coordination infrastructure. Configure `DB_POOL_*`, `REDIS_PASSWORD`, `REDIS_URL`, `CACHE_*`, and `AGENT_RUN_LOCK_SECONDS` in `.env`. Use `docker-compose.v1.2.yml` for the production-oriented stack.

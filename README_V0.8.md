# Job Hunter Agent v0.8

Production-oriented React + TypeScript dashboard with FastAPI API integration and SMTP email notifications.

## Stack
- Next.js + React + TypeScript
- FastAPI + PostgreSQL
- Redis (compose-ready)
- APScheduler
- Exa discovery/retrieval
- Fireworks Qwen3.7 Plus primary + DeepSeek-V4-Flash fallback
- SMTP email notifications

## Email
Every important agent update is sent when `EMAIL_UPDATES=true`. Set:

`NOTIFY_TO=sheikhasan44@gmail.com`

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD` in `.env`. Credentials are never stored in source code.

## Run
1. Copy `.env.example` to `.env` and add fresh credentials.
2. Start PostgreSQL/Redis and the backend/scheduler/frontend with `docker compose -f docker-compose.v0.8.yml up --build`.
3. Open `http://localhost:3000`.
4. Backend API: `http://localhost:8000/docs`.

The dashboard calls the live `/api/dashboard`, `/api/jobs`, `/api/runs`, `/api/applications`, `/api/sources`, `/api/settings`, and `/api/jobs/{id}/status` endpoints. Application submission remains human-in-the-loop; there is no auto-apply action.

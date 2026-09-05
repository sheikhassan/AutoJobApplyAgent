# Job Hunter v0.7 — Ultimate Dashboard

The `frontend/index.html` is a dependency-free dashboard prototype that can be served as static content.

## Production API contract

Wire the existing FastAPI application to these endpoints:

- `GET /api/dashboard` — metrics, source mix, automation state
- `GET /api/jobs?status=&source=&remote=&min_score=` — normalized jobs
- `GET /api/jobs/{job_id}` — full job + match explanation
- `POST /api/jobs/{job_id}/tailor` — generate tailored resume
- `POST /api/jobs/{job_id}/cover-letter` — generate cover letter
- `PATCH /api/jobs/{job_id}/status` — human application status
- `GET /api/applications` — application pipeline
- `GET /api/runs` — scheduler/search history
- `POST /api/runs` — run a scan now
- `GET /api/sources` — source configuration
- `GET /api/settings` / `PATCH /api/settings` — preferences and scheduler config

The frontend intentionally has no secrets. Exa and Fireworks keys remain server-side in environment variables.

## Recommended deployment

Docker Compose services:
- frontend (static/Nginx)
- backend (FastAPI)
- worker
- scheduler
- postgres
- redis

Human-in-the-loop remains the default: the system prepares the application package but never submits an application automatically.

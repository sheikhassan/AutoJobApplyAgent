# AutoJobApplyAgent: Antigravity Handoff

## Mission

Build and maintain this as a real production Job Hunter Agent. Do not replace the existing architecture with a mock, static prototype, or auto-apply bot.

The application must:

- Search remote jobs first and hybrid jobs second.
- Target AI/software roles: AI Engineer, AI/ML Engineer, Agentic AI Engineer, AI Software Engineer/Developer, LLM Engineer, Generative AI Engineer, Machine Learning Engineer, SDE, Backend AI Engineer, and related roles.
- Rank compensation in this order: USD, EUR, AED, SAR, undisclosed/other, INR. Undisclosed compensation remains eligible. Never invent or convert salary values.
- Treat missing experience requirements as eligible. Candidate experience is 2 years; roles requiring up to 3 years remain eligible.
- Tailor resumes and generate useful cover letters only from trusted candidate facts.
- Show the real application URL and require human approval before every application. Never automatically submit applications.
- Use Exa as primary search and TinyFish REST Search as automatic fallback when Exa fails or returns no usable results.
- Use Fireworks Qwen as the primary model and DeepSeek as fallback.
- Persist durable state in PostgreSQL, use Redis only for cache/coordination/rate limiting, and send important updates by SMTP email.

## Account Separation

- GitHub/deployment account: `sheikhassan`.
- Student/Copilot GitHub account: `Hassan-4287`.
- Never use or store passwords, API keys, SMTP credentials, database credentials, session secrets, or tokens in this file.
- Never commit `.env`.
- Credentials previously exposed in chat or local files must be rotated before production use.

## Repository Source Of Truth

Read these before changing architecture:

- `AGENTS.md`
- `README.md`
- `README_V0.9_PRODUCTION.md`
- `SECURITY.md`
- `MODEL_API.md`
- `.env.example`
- `docker-compose.v1.2.yml`
- `app/`
- `frontend/`
- `tests/`

Existing stack:

- Backend: FastAPI in `app/api.py`.
- Pipeline: `app/pipeline.py`.
- Scheduler: APScheduler in `app/scheduler.py`.
- Database and migrations: `app/database.py`, `app/migrations.py`.
- Search: Exa primary and TinyFish fallback in `app/search_router.py`.
- Models: Fireworks Qwen and DeepSeek fallback.
- Frontend: Next.js + React + TypeScript in `frontend/`.
- Deployment image: root `Dockerfile`.
- `SERVICE_ROLE=api` runs the API; `SERVICE_ROLE=scheduler` runs `python -m app.scheduler`.

## Current Production Services

Railway project: `AutoJobApplyAgent` in the `sheikhassan` workspace.

Existing Railway services:

- `backend`: `https://backend-production-089f.up.railway.app`
- `scheduler`: separate service; no public domain is required.
- `Postgres`: online.
- `Redis`: online.

Verified before this handoff:

- Backend `/health` returned HTTP 200.
- Backend `/ready` returned HTTP 200 and reported ready.
- PostgreSQL and Redis were connected.
- Vercel frontend was redeployed with the Railway backend URL.

Vercel production frontend:

- Latest deployment: `https://frontend-kc3y7s3wc-aura-team4.vercel.app`
- Vercel project: `aura-team4/frontend`.
- The Vercel variable `NEXT_PUBLIC_API_URL` must remain the Railway backend URL above.

## Current Deployment Blocker

Railway service settings display the repository name `sheikhassan/AutoJobApplyAgent`, but Railway reports `GitHub Repo not found`. The active backend and scheduler deployments are still old deployments created through the previous GitHub integration account `mohdfayyad2007-byte`.

Fix this before claiming the latest code is deployed:

1. Open the Railway backend service settings.
2. Under Source Repo, choose `Edit` then `Configure GitHub App`.
3. Authorize/install Railway's GitHub App for the `sheikhassan` account.
4. Grant access to `sheikhassan/AutoJobApplyAgent`.
5. Confirm the production branch is `main`.
6. Repeat the source check for the scheduler service if it has a separate source connection.
7. Trigger a deployment from the latest `main` commit.
8. Confirm the deployment author/source is `sheikhassan`, not `mohdfayyad2007-byte`.
9. Do not disconnect or delete the currently active services until the replacement deployment is healthy.

## Railway Service Configuration

### Backend service

- Source repository: `sheikhassan/AutoJobApplyAgent`.
- Branch: `main`.
- Root directory: repository root.
- Builder: Dockerfile.
- Dockerfile: `/Dockerfile`.
- Start command may use the Dockerfile default, or:
  `uvicorn app.api:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`
- Healthcheck path: `/health`.
- Restart policy: on failure.
- Public domain: `backend-production-089f.up.railway.app`.

### Scheduler service

- Source repository: `sheikhassan/AutoJobApplyAgent`.
- Branch: `main`.
- Root directory: repository root.
- Builder: Dockerfile.
- Set `SERVICE_ROLE=scheduler`, or set command to:
  `python -m app.scheduler`
- Do not expose a public HTTP domain.
- Keep one scheduler service only. Do not run the scheduler inside the API service.
- Restart policy: on failure.
- Logs must show the configured timezone and all configured times.

### PostgreSQL and Redis

- PostgreSQL is the durable system of record and must remain private.
- Redis is cache/coordination/rate limiting only and must remain private.
- Use Railway reference variables for connection URLs where available.
- Do not paste or commit connection strings containing credentials.
- Confirm the API can report both dependencies healthy through `/health` and `/ready`.

## Production Environment Variables

Set these in Railway service variables/secrets, never in GitHub or Vercel unless explicitly marked public:

Required provider/model secrets:

- `EXA_API_KEY`
- `TINYFISH_API_KEY`
- `TINYFISH_BASE_URL=https://api.tinyfish.ai/v1`
- `FIREWORKS_API_KEY`
- `FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1`
- `FIREWORKS_MODEL=accounts/fireworks/models/qwen3p7-plus`
- `MODEL_TARGETS=qwen=accounts/fireworks/models/qwen3p7-plus:3,deepseek=accounts/fireworks/models/deepseek-v4-flash:2`
- `USE_MODEL=true`

Database/cache:

- Railway-provided `DATABASE_URL`.
- Railway-provided `REDIS_URL`, with authentication enabled.
- `CACHE_REQUIRED=true`
- `DB_POOL_MIN_SIZE=2`
- `DB_POOL_MAX_SIZE=12`
- `REDIS_CONNECT_TIMEOUT_SECONDS=1.5`
- `REDIS_SOCKET_TIMEOUT_SECONDS=1.5`
- `AGENT_RUN_LOCK_SECONDS=1800`

Authentication/security:

- `AUTH_REQUIRED=true`
- A new strong `DASHBOARD_PASSWORD`.
- A random 32+ character `DASHBOARD_SESSION_SECRET`.
- `COOKIE_SECURE=true`
- `CSRF_PROTECTION=true`
- `RATE_LIMIT_ENABLED=true`
- `REQUIRE_HTTPS=true`
- `CORS_ORIGINS=https://frontend-six-psi-ktywfm7c1o.vercel.app`

Email:

- `EMAIL_UPDATES=true`
- `NOTIFY_TO` set to the configured recipient.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS=true`.
- Use a newly generated SMTP app password. Never reuse the exposed local value.

Scheduler:

- `JOB_HUNTER_TIMES=06:00,08:00,13:00,22:00,00:00`
- `JOB_HUNTER_TIMEZONE=Asia/Kolkata`
- `JOB_HUNTER_DAYS=mon-sun`
- `RUN_SCHEDULED_SCAN_ON_STARTUP=false`
- `MAX_PACKAGES_PER_RUN=10`
- `MIN_MATCH_SCORE=0.60`

Search limits:

- `EXA_QUERY_BUDGET=8`
- `EXA_MAX_RESULTS_PER_QUERY=5`
- `EXA_CONTENTS_LIMIT=5`

Cold outreach remains disabled unless explicitly approved:

- `COLD_OUTREACH_ENABLED=false`

## Scheduler Requirements

The scheduler must run automatically at 06:00, 08:00, 13:00, 22:00, and 00:00 Asia/Kolkata every day.

Every run must:

1. Acquire the Redis distributed lock.
2. Search with Exa and fall back to TinyFish when needed.
3. Normalize, deduplicate, filter, score, and persist jobs.
4. Persist `job_runs` and associate jobs with their `last_run_id` and `last_run_at`.
5. Send a completion email containing counts and real application links.
6. Record notification success/failure without losing successful jobs.
7. Release the distributed lock.

Verify scheduler logs contain:

- `Job Hunter scheduler active`.
- `mon-sun`.
- `06:00,08:00,13:00,22:00,00:00`.
- A successful scan completion after the next scheduled time.

Do not rely on a manual `Run scan` button as a substitute for the scheduler.

## Job Dashboard Rules

The jobs page must:

- Show only jobs from the latest 24-hour run window.
- Put the newest scheduler run first.
- Within each run, prioritize remote, then hybrid, then match score and compensation preference.
- Use pagination; never render an unbounded job list.
- Preserve real source and application URLs.
- Show run time and match percentage clearly.
- Never fabricate company, salary, location, job ID, or application link.

Search must cover broad web sources, not Indeed only. Keep source-specific and role/skill query groups for Indeed, LinkedIn, HiringCafe, Wellfound, ATS pages, company careers, Mercor, micro1, Dice, and configured overseas recruiters. Use web search/indexing through the provider adapters; do not add fragile uncontrolled scraping or bypass anti-bot protections.

## Deployment Sequence

1. Fix Railway GitHub App access for `sheikhassan/AutoJobApplyAgent`.
2. Confirm Railway backend and scheduler use the root Dockerfile.
3. Confirm PostgreSQL and Redis are attached privately.
4. Set all Railway variables from `.env.example` using newly rotated secrets.
5. Deploy backend.
6. Verify `https://backend-production-089f.up.railway.app/health`.
7. Verify `https://backend-production-089f.up.railway.app/ready`.
8. Deploy scheduler separately with `SERVICE_ROLE=scheduler`.
9. Inspect scheduler logs and wait for or manually invoke one controlled test run.
10. Set Vercel Production `NEXT_PUBLIC_API_URL` to `https://backend-production-089f.up.railway.app`.
11. Set Railway `CORS_ORIGINS` to the exact Vercel production URL.
12. Redeploy Vercel after changing `NEXT_PUBLIC_API_URL`.
13. Sign in to the dashboard and verify jobs, run history, notifications, sources, and settings.
14. Trigger one controlled scan only after the scheduler service is confirmed healthy.
15. Verify the notification email contains real links and the scan result is visible in run history.

## Acceptance Checklist

- [ ] Railway GitHub App sees `sheikhassan/AutoJobApplyAgent`.
- [ ] Latest backend deployment source is `sheikhassan`, not `mohdfayyad2007-byte`.
- [ ] Latest scheduler deployment source is `sheikhassan`, not `mohdfayyad2007-byte`.
- [ ] Backend `/health` returns HTTP 200.
- [ ] Backend `/ready` returns HTTP 200.
- [ ] PostgreSQL is healthy and migrations complete.
- [ ] Redis is healthy and distributed run lock works.
- [ ] Scheduler is a separate always-on service.
- [ ] Scheduler logs show all five daily times in Asia/Kolkata.
- [ ] A scheduled run creates a `job_runs` record.
- [ ] Jobs are associated with `last_run_id` and `last_run_at`.
- [ ] Jobs older than 24 hours are excluded from the jobs page.
- [ ] Newest run is shown before older runs and score ordering is stable.
- [ ] Pagination works on the jobs page.
- [ ] Source cards fit without horizontal overflow.
- [ ] Exa success path works.
- [ ] Exa failure/empty result falls back to TinyFish.
- [ ] Email completion digest is delivered with real application links.
- [ ] Vercel frontend calls the Railway backend, not localhost or a malformed URL.
- [ ] Authentication, CSRF, rate limiting, SSRF protection, and prompt-injection boundaries remain enabled.
- [ ] No automatic application submission exists.
- [ ] Exposed local credentials have been rotated.

## Validation Commands

From the repository root:

```powershell
python -m py_compile app\api.py app\database.py app\migrations.py app\scheduler.py
.venv\Scripts\python.exe -m pytest -q
Push-Location frontend
npm run build
Pop-Location
```

Useful production checks:

```powershell
Invoke-WebRequest https://backend-production-089f.up.railway.app/health -UseBasicParsing
Invoke-WebRequest https://backend-production-089f.up.railway.app/ready -UseBasicParsing
```

Never report a deployment as complete until the acceptance checklist is satisfied.

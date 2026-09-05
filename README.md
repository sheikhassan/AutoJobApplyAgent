# Job Hunter Agent v0.2

End-to-end, model-agnostic job hunting pipeline:
1. Search jobs with Exa.
2. Normalize and deduplicate listings.
3. Filter/rank for role, work mode, currency and fit.
4. Fetch full job pages when needed.
5. Match the JD against the master resume without inventing experience.
6. Produce a tailored-resume/cover-letter request for a pluggable model.
7. Write an application queue for human review.
8. Never auto-submit applications.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set EXA_API_KEY
```

Run:
```bash
python -m app.cli --queries 3 --results-per-query 5
```

API:
```bash
uvicorn app.api:app --reload
```

### Model plug-in
`app/model_provider.py` defines the interface. v0.2 ships with a deterministic stub provider so the pipeline runs without an LLM. Replace it later with OpenAI/Anthropic/Gemini/local provider implementing `ModelProvider`.

### Outputs
- `outputs/jobs.json`
- `outputs/application_queue.json`
- `outputs/run_report.json`

The agent intentionally stops before application submission. You review each package and apply through the employer/ATS link.


## v0.2 Fireworks model layer

Fireworks is now a model provider behind an environment-variable API key. A weighted
application-level load balancer and SMTP completion notification are included.

Do not paste API keys into source code or commit them to git. If a real key has already
been shared in chat, rotate/revoke it and use the replacement in `.env`.


## Low-cost model layer

OpenAI is optional. The production pipeline uses Fireworks-hosted open-weight models with weighted failover: **Qwen3.7 Plus** primary and **DeepSeek-V4-Flash** fallback. Configure `FIREWORKS_API_KEY` and `MODEL_TARGETS` in `.env`.


## Exa Free-Tier Search Mode

The job hunter is configured for a conservative Exa free-tier workflow:

- Standard Exa Search only
- No Deep Search / Deep Reasoning Search
- 8 role queries per run by default
- Up to 5 results per query
- URL de-duplication before downstream processing
- Highlights are requested for token-efficient filtering
- Full page contents should be fetched only for shortlisted jobs

Environment overrides:

```bash
EXA_QUERY_BUDGET=8
EXA_MAX_RESULTS_PER_QUERY=5
```

For a tighter free-tier run, use `EXA_QUERY_BUDGET=4` and
`EXA_MAX_RESULTS_PER_QUERY=5`.

## v0.5 Multi-Source Job Discovery

The search layer now treats Exa as the discovery/retrieval engine across three source families:

- Job boards: HiringCafe, LinkedIn Jobs, Indeed, Wellfound, Dice, YC Jobs
- ATS/direct hiring: Greenhouse, Lever, Ashby, Workday, SmartRecruiters, company career pages
- AI talent networks: Mercor, micro1

The system is still Exa-free-tier conscious: default 8 search requests/run, 5 results/request, highlights-first retrieval, URL deduplication, and full contents retrieval only for the top 5 shortlisted jobs. No automatic application submission is performed.

Environment knobs: `EXA_QUERY_BUDGET`, `EXA_MAX_RESULTS_PER_QUERY`, `EXA_CONTENTS_LIMIT`.


## v0.6 Production Scheduler + PostgreSQL

The production shape is now a long-running scheduler. It runs the existing Job Hunter pipeline on a schedule, stores run/job/application history in PostgreSQL, and optionally sends a completion digest through the configured SMTP notifier. Human review remains mandatory; there is no auto-apply.

Default schedule: weekends at 06:00, 08:00, 13:00, 22:00, and 00:00 Asia/Kolkata. Configure `JOB_HUNTER_TIMES` as comma-separated `HH:MM` values, plus `JOB_HUNTER_TIMEZONE` and `JOB_HUNTER_DAYS`. `JOB_HUNTER_HOUR` and `JOB_HUNTER_MINUTE` remain supported as a legacy single-time fallback.

### Start the scheduler
```bash
pip install -r requirements.txt
python -m app.scheduler
```

### PostgreSQL
Set `DATABASE_URL` before starting. The application creates its tables automatically on startup. If `DATABASE_URL` is empty, the JSON output workflow still works for local development.

### Cost control
The scheduler uses the Exa free-tier-conscious search settings already in v0.5 and caps AI-generated application packages with `MAX_PACKAGES_PER_RUN` (default 10).


## v0.7 Ultimate Dashboard

Open `frontend/index.html` for the Job Hunter Command Center UI. It is designed for the production FastAPI + worker + scheduler + PostgreSQL + Redis architecture.

Production services are described in `docker-compose.v0.7.yml`. Keep all API keys in `.env`; never commit them.

### Automatic cold outreach
When `COLD_OUTREACH_ENABLED=true`, the agent can automatically send a personalized outreach email from the configured SMTP account when a qualified job page explicitly publishes a contact email. It uses a daily cap, recipient+job deduplication, audit logging, and a kill switch. It never guesses addresses or submits job applications.

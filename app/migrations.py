"""Idempotent database migrations for production deployments."""
from .db_pool import connection

MIGRATIONS = [
("001_baseline_indexes", """
CREATE INDEX IF NOT EXISTS idx_jobs_score_seen ON jobs(match_score DESC NULLS LAST, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_company_title ON jobs(company, title);
CREATE INDEX IF NOT EXISTS idx_jobs_work_mode_score ON jobs(work_mode, match_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_status_seen ON jobs(application_status, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs(posted_date);
CREATE INDEX IF NOT EXISTS idx_runs_status_started ON job_runs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_packages_job_created ON application_packages(job_url, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_type_created ON notification_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event_created ON security_audit_log(event, created_at DESC);
"""),
("002_constraints", """
ALTER TABLE jobs ADD CONSTRAINT jobs_match_score_range CHECK (match_score IS NULL OR (match_score >= 0 AND match_score <= 1));
ALTER TABLE application_packages ADD CONSTRAINT packages_human_review_required CHECK (needs_human_review = TRUE);
"""),
("003_cold_outreach", """
CREATE INDEX IF NOT EXISTS idx_cold_outreach_recipient_job ON cold_outreach_events(recipient, job_url, sent);
CREATE INDEX IF NOT EXISTS idx_cold_outreach_created ON cold_outreach_events(created_at DESC);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS contact_emails JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS contact_phones JSONB NOT NULL DEFAULT '[]'::jsonb;
"""),
 ("004_job_context_and_review", """
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS requirements JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS search_query TEXT DEFAULT '';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cover_letter_required BOOLEAN;
ALTER TABLE application_packages ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE application_packages ADD COLUMN IF NOT EXISTS jd_snapshot TEXT NOT NULL DEFAULT '';
ALTER TABLE application_packages ADD COLUMN IF NOT EXISTS requirements_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb;
CREATE INDEX IF NOT EXISTS idx_packages_review_status ON application_packages(review_status, created_at DESC);
"""),
]


def run_migrations():
    with connection() as conn:
        if conn is None:
            return
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""")
        for version, sql in MIGRATIONS:
            exists = conn.execute("SELECT 1 FROM schema_migrations WHERE version=%s", (version,)).fetchone()
            if exists:
                continue
            try:
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute("INSERT INTO schema_migrations(version) VALUES(%s)", (version,))
            except Exception as exc:
                # Constraint migrations may encounter an already-existing constraint from a prior deployment.
                if version == "002_constraints" and "already exists" in str(exc).lower():
                    conn.rollback()
                    conn.execute("INSERT INTO schema_migrations(version) VALUES(%s) ON CONFLICT DO NOTHING", (version,))
                else:
                    raise

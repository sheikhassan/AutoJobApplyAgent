import json
from datetime import datetime, timezone
from typing import Iterable, Any
from .db_pool import connection, check
from .migrations import run_migrations
from .cache import bump


def database_url():
    import os
    return os.getenv('DATABASE_URL', '')


def enabled(): return bool(database_url())


def init_db():
    if not enabled(): return
    with connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS job_runs (
          id BIGSERIAL PRIMARY KEY, started_at TIMESTAMPTZ NOT NULL, finished_at TIMESTAMPTZ,
          status TEXT NOT NULL, queries_run JSONB NOT NULL DEFAULT '[]', jobs_found INTEGER NOT NULL DEFAULT 0,
          qualified INTEGER NOT NULL DEFAULT 0, content_pages_fetched INTEGER NOT NULL DEFAULT 0, error TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS jobs (
          id BIGSERIAL PRIMARY KEY, url TEXT UNIQUE NOT NULL, title TEXT NOT NULL, company TEXT,
          source_title TEXT, source_category TEXT, location TEXT, work_mode TEXT, salary TEXT, currency TEXT,
          description TEXT, posted_date TEXT, match_score DOUBLE PRECISION, reasons JSONB NOT NULL DEFAULT '[]',
          gaps JSONB NOT NULL DEFAULT '[]', first_seen_at TIMESTAMPTZ NOT NULL, last_seen_at TIMESTAMPTZ NOT NULL,
          application_status TEXT NOT NULL DEFAULT 'new', application_url TEXT DEFAULT '', years_experience_required DOUBLE PRECISION, sponsorship TEXT DEFAULT 'unknown', eligibility_note TEXT DEFAULT '', contact_emails JSONB NOT NULL DEFAULT '[]', contact_phones JSONB NOT NULL DEFAULT '[]')''')
        conn.execute('''CREATE TABLE IF NOT EXISTS security_audit_log (
          id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          event TEXT NOT NULL, actor TEXT, client_ip INET, details JSONB NOT NULL DEFAULT '{}'::jsonb)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS application_packages (
          id BIGSERIAL PRIMARY KEY, job_url TEXT NOT NULL REFERENCES jobs(url) ON DELETE CASCADE, role TEXT NOT NULL,
          company TEXT, match_score DOUBLE PRECISION, tailored_resume TEXT NOT NULL, cover_letter TEXT,
          application_notes TEXT, needs_human_review BOOLEAN NOT NULL DEFAULT TRUE,
          review_status TEXT NOT NULL DEFAULT 'pending', jd_snapshot TEXT NOT NULL DEFAULT '',
          requirements_snapshot JSONB NOT NULL DEFAULT '[]', created_at TIMESTAMPTZ NOT NULL)''')
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS application_url TEXT DEFAULT ''")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS years_experience_required DOUBLE PRECISION")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS sponsorship TEXT DEFAULT 'unknown'")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS eligibility_note TEXT DEFAULT ''")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS contact_emails JSONB NOT NULL DEFAULT '[]'::jsonb")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS contact_phones JSONB NOT NULL DEFAULT '[]'::jsonb")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS requirements JSONB NOT NULL DEFAULT '[]'::jsonb")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS search_query TEXT DEFAULT ''")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cover_letter_required BOOLEAN")
        conn.execute("ALTER TABLE application_packages ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'pending'")
        conn.execute("ALTER TABLE application_packages ADD COLUMN IF NOT EXISTS jd_snapshot TEXT NOT NULL DEFAULT ''")
        conn.execute("ALTER TABLE application_packages ADD COLUMN IF NOT EXISTS requirements_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb")
        conn.execute('''CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY, value JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS notification_events (
          id BIGSERIAL PRIMARY KEY, event_type TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL,
          recipient TEXT, sent BOOLEAN NOT NULL DEFAULT FALSE, error TEXT, created_at TIMESTAMPTZ NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS cold_outreach_events (
          id BIGSERIAL PRIMARY KEY, job_url TEXT NOT NULL REFERENCES jobs(url) ON DELETE CASCADE,
          recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL, sent BOOLEAN NOT NULL DEFAULT FALSE,
          error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        conn.commit()
    run_migrations()


def save_run(jobs: Iterable, packages: Iterable, report: dict, status='success', error=None):
    if not enabled(): return None
    now=datetime.now(timezone.utc); jobs=list(jobs); packages=list(packages)
    job_by_url={j.url:j for j in jobs}
    with connection() as conn:
        rid=conn.execute('''INSERT INTO job_runs
          (started_at,finished_at,status,queries_run,jobs_found,qualified,content_pages_fetched,error)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
          (now,now,status,json.dumps(report.get('queries_run',[])),report.get('jobs_found',0),
           report.get('qualified',0),report.get('content_pages_fetched',0),error)).fetchone()[0]
        for j in jobs:
            d=j.model_dump()
            conn.execute('''INSERT INTO jobs
              (url,title,company,source_title,source_category,location,work_mode,salary,currency,description,
               posted_date,match_score,reasons,gaps,first_seen_at,last_seen_at,application_url,
               years_experience_required,sponsorship,eligibility_note,contact_emails,contact_phones,
               requirements,search_query,cover_letter_required)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT (url) DO UPDATE SET title=EXCLUDED.title,company=EXCLUDED.company,
              source_title=EXCLUDED.source_title,source_category=EXCLUDED.source_category,location=EXCLUDED.location,
              work_mode=EXCLUDED.work_mode,salary=EXCLUDED.salary,currency=EXCLUDED.currency,
              description=EXCLUDED.description,posted_date=EXCLUDED.posted_date,match_score=EXCLUDED.match_score,
              reasons=EXCLUDED.reasons,gaps=EXCLUDED.gaps,last_seen_at=EXCLUDED.last_seen_at,
              application_url=EXCLUDED.application_url,
              years_experience_required=EXCLUDED.years_experience_required,
              sponsorship=EXCLUDED.sponsorship,
              eligibility_note=EXCLUDED.eligibility_note,
              contact_emails=EXCLUDED.contact_emails, contact_phones=EXCLUDED.contact_phones,
              requirements=EXCLUDED.requirements,search_query=EXCLUDED.search_query,
              cover_letter_required=EXCLUDED.cover_letter_required''',
              (d['url'],d['title'],d['company'],d['source_title'],d['source_category'],d['location'],d['work_mode'],
               d['salary'],d['currency'],d['description'],d['posted_date'],d['match_score'],json.dumps(d['reasons']),
               json.dumps(d['gaps']),now,now,d.get('application_url',''),d.get('years_experience_required'),d.get('sponsorship','unknown'),d.get('eligibility_note',''),json.dumps(d.get('contact_emails',[])),json.dumps(d.get('contact_phones',[])),json.dumps(d.get('requirements',[])),d.get('search_query',''),d.get('cover_letter_required')))
        for p in packages:
            d=p.model_dump()
            conn.execute('''INSERT INTO application_packages
              (job_url,role,company,match_score,tailored_resume,cover_letter,application_notes,
               needs_human_review,review_status,jd_snapshot,requirements_snapshot,created_at)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
              (d['job_url'],d['role'],d['company'],d['match_score'],d['tailored_resume'],d['cover_letter'],
               d['application_notes'],True,d.get('review_status','pending'),d.get('jd_snapshot') or getattr(job_by_url.get(d['job_url']),'description',''),json.dumps(d.get('requirements_snapshot') or getattr(job_by_url.get(d['job_url']),'requirements',[])),now))
        conn.commit()
    bump('jobs'); bump('dashboard'); bump('applications'); bump('runs')
    return rid


def save_package(package, job, review_status='pending'):
    if not enabled(): return None
    d=package.model_dump()
    now=datetime.now(timezone.utc)
    with connection() as conn:
      package_id=conn.execute('''INSERT INTO application_packages
        (job_url,role,company,match_score,tailored_resume,cover_letter,application_notes,
         needs_human_review,review_status,jd_snapshot,requirements_snapshot,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE,%s,%s,%s,%s) RETURNING id''',
        (d['job_url'],d['role'],d['company'],d['match_score'],d['tailored_resume'],d['cover_letter'],
         d['application_notes'],review_status,job.description,json.dumps(job.requirements),now)).fetchone()[0]
      conn.commit()
    bump('applications'); bump('dashboard')
    return package_id


def query(sql, params=()):
    if not enabled(): return []
    with connection() as conn:
        cur=conn.execute(sql,params)
        if cur.description is None: return []
        cols=[d.name for d in cur.description]
        return [dict(zip(cols,r)) for r in cur.fetchall()]


def execute(sql, params=()):
    if not enabled(): return False
    with connection() as conn:
        conn.execute(sql,params); conn.commit()
    return True


def get_setting(key: str, default: Any=None):
    rows=query('SELECT value FROM app_settings WHERE key=%s',(key,))
    if not rows: return default
    return rows[0]['value']


def set_setting(key: str, value: Any):
    if not enabled(): return
    now=datetime.now(timezone.utc)
    with connection() as conn:
        conn.execute('''INSERT INTO app_settings(key,value,updated_at) VALUES(%s,%s,%s)
          ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,updated_at=EXCLUDED.updated_at''',
          (key,json.dumps(value),now)); conn.commit()
    bump('settings')


def log_notification(event_type, subject, detail, recipient, sent, error=None):
    if not enabled(): return
    now=datetime.now(timezone.utc)
    with connection() as conn:
        conn.execute('''INSERT INTO notification_events(event_type,subject,detail,recipient,sent,error,created_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s)''',(event_type,subject,detail,recipient,sent,error,now)); conn.commit()
    bump('notifications')


def audit(event: str, actor: str = '', client_ip: str = '', details: dict | None = None):
    if not enabled(): return
    try:
        execute('INSERT INTO security_audit_log(event,actor,client_ip,details) VALUES (%s,%s,%s,%s)',
                (event, actor[:320], client_ip or None, json.dumps(details or {})))
    except Exception:
        pass


def database_ready():
    return check()

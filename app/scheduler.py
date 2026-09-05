import logging, os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from .config import JobConfig
from .pipeline import run
from .database import init_db
from .email_notifier import notify_update, notify_job_digest
from .cache import get_client as cache_client

log=logging.getLogger(__name__)

def scheduled_run():
    lock = None
    try:
        client = cache_client()
        if client:
            lock = client.lock(
                'jh:v1:agent-run',
                timeout=int(os.getenv('AGENT_RUN_LOCK_SECONDS', '1800')),
                blocking_timeout=1,
            )
            if not lock.acquire(blocking=True):
                log.warning('Skipping scheduled run because another agent run is active')
                return
        jobs, packages = run(JobConfig())
        top='\n'.join(f'{j.match_score:.0%} | {j.work_mode} | {j.title} | {j.url}' for j in jobs[:10])
        notify_update('Scheduled scan completed', f'{len(jobs)} jobs discovered; {len(packages)} qualified packages.\n\nTop matches:\n{top}', swallow=True)
        notify_job_digest(jobs, packages, 'New matching jobs with apply links', swallow=True)
        log.info('Scheduled scan completed: jobs=%s packages=%s',len(jobs),len(packages))
    except Exception as exc:
        log.exception('Scheduled Job Hunter run failed')
        notify_update('Scheduled scan failed', str(exc), swallow=True)
    finally:
        if lock:
            try:
                lock.release()
            except Exception:
                pass

def main():
    init_db()
    tz=os.getenv('JOB_HUNTER_TIMEZONE','Asia/Kolkata'); days=os.getenv('JOB_HUNTER_DAYS','mon-fri')
    scheduler=BlockingScheduler(timezone=tz)
    times=os.getenv('JOB_HUNTER_TIMES','').split(',')
    if not times or not times[0].strip():
        times=[f"{int(os.getenv('JOB_HUNTER_HOUR','8')):02d}:{int(os.getenv('JOB_HUNTER_MINUTE','0')):02d}"]
    for index, value in enumerate(times):
        hour_text, minute_text = value.strip().split(':', 1)
        scheduler.add_job(
            scheduled_run,
            CronTrigger(day_of_week=days,hour=int(hour_text),minute=int(minute_text)),
            id=f'job-hunter-{index}',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    log.info('Job Hunter scheduler active: %s at %s %s',days,','.join(x.strip() for x in times),tz)
    scheduler.start()
if __name__=='__main__': main()

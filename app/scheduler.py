import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from .config import JobConfig
from .pipeline import run
from .database import init_db
from .email_notifier import notify_update, notify_job_digest
from .cache import get_client as cache_client, delete as cache_delete

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
log = logging.getLogger(__name__)


def run_scheduled_scan():
    """Execute one scan pass under the distributed Redis lock.
    
    Returns a status dict describing the execution result.
    """
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
                return {'status': 'skipped', 'reason': 'another_run_active'}
        log.info('Starting scheduled Job Hunter scan...')
        jobs, packages = run(JobConfig())
        top = '\n'.join(f'{j.match_score:.0%} | {j.work_mode} | {j.title} | {j.url}' for j in jobs[:10])
        notify_update(
            'Scheduled scan completed',
            f'{len(jobs)} jobs discovered; {len(packages)} qualified packages.\n\nTop matches:\n{top}',
            swallow=True,
        )
        notify_job_digest(jobs, packages, 'New matching jobs with apply links', swallow=True)
        # Invalidate cached dashboard views so fresh jobs and run history display immediately
        for ns in ('dashboard', 'runs', 'jobs', 'applications', 'notifications'):
            try:
                cache_delete(ns, 'main')
            except Exception:
                pass
        log.info('Scheduled scan completed: jobs=%s packages=%s', len(jobs), len(packages))
        return {'status': 'success', 'jobs_found': len(jobs), 'packages': len(packages)}
    except Exception as exc:
        log.exception('Scheduled Job Hunter run failed')
        notify_update('Scheduled scan failed', str(exc), swallow=True)
        return {'status': 'failed', 'error': str(exc)}
    finally:
        if lock:
            try:
                lock.release()
            except Exception:
                pass


# Backward compatibility alias
scheduled_run = run_scheduled_scan


def get_configured_times() -> list[str]:
    raw = os.getenv('JOB_HUNTER_TIMES', '').strip()
    if raw:
        times = [x.strip() for x in raw.split(',') if x.strip()]
        if times:
            return times
    hour = int(os.getenv('JOB_HUNTER_HOUR', '8'))
    minute = int(os.getenv('JOB_HUNTER_MINUTE', '0'))
    return [f"{hour:02d}:{minute:02d}"]


def setup_scheduler(scheduler=None):
    """Configure all daily cron jobs on the given scheduler instance."""
    tz = os.getenv('JOB_HUNTER_TIMEZONE', 'Asia/Kolkata')
    days = os.getenv('JOB_HUNTER_DAYS', 'mon-sun')
    if scheduler is None:
        scheduler = BlockingScheduler(timezone=tz)
    times = get_configured_times()
    for index, value in enumerate(times):
        if ':' not in value:
            continue
        hour_text, minute_text = value.strip().split(':', 1)
        scheduler.add_job(
            run_scheduled_scan,
            CronTrigger(day_of_week=days, hour=int(hour_text), minute=int(minute_text), timezone=tz),
            id=f'job-hunter-{index}',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    log.info('Configured Job Hunter scheduler: %s at %s %s', days, ','.join(times), tz)
    return scheduler


def get_scheduler_info(scheduler=None) -> dict:
    tz = os.getenv('JOB_HUNTER_TIMEZONE', 'Asia/Kolkata')
    days = os.getenv('JOB_HUNTER_DAYS', 'mon-sun')
    times = get_configured_times()
    next_fire_time = None
    running = False
    if scheduler and getattr(scheduler, 'running', False):
        running = True
        jobs = scheduler.get_jobs()
        next_times = [j.next_run_time for j in jobs if getattr(j, 'next_run_time', None)]
        if next_times:
            next_fire_time = min(next_times).isoformat()
    return {
        'running': running,
        'timezone': tz,
        'days': days,
        'schedule_times': times,
        'next_run_time': next_fire_time,
    }


def main():
    init_db()
    tz = os.getenv('JOB_HUNTER_TIMEZONE', 'Asia/Kolkata')
    scheduler = BlockingScheduler(timezone=tz)
    setup_scheduler(scheduler)
    if os.getenv('RUN_SCHEDULED_SCAN_ON_STARTUP', 'false').lower() in {'1', 'true', 'yes'}:
        log.info('Running startup scan because RUN_SCHEDULED_SCAN_ON_STARTUP is enabled')
        run_scheduled_scan()
    scheduler.start()


if __name__ == '__main__':
    main()

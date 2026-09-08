import logging, os, hmac, threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from .config import JobConfig
from .pipeline import run
from .database import init_db, query, execute, get_setting, set_setting, audit, database_ready, save_package
from .cache import get as cache_get, set as cache_set, delete as cache_delete, delete_namespace as cache_delete_namespace, ping as cache_ping, get_client as cache_client
from .email_notifier import notify_update, notify_job_digest
from .cold_outreach import send_cold_outreach
from .auth import issue_session, valid_session, COOKIE, require_auth
from .security import require_csrf, security_headers, security_posture, new_csrf_token, set_csrf_cookie, client_ip, SecurityError, validate_external_url
from .exa_search import SOURCES

logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'))
log=logging.getLogger(__name__)

_embedded_scheduler = None

def get_scheduler_status() -> dict:
    try:
        from .scheduler import get_scheduler_info
        return get_scheduler_info(_embedded_scheduler)
    except Exception as exc:
        return {'running': False, 'error': str(exc)}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedded_scheduler
    try:
        init_db()
    except Exception as exc:
        log.warning('Database initialization deferred: %s', exc)

    if os.getenv('EMBEDDED_SCHEDULER', 'true').lower() in {'1', 'true', 'yes'} and os.getenv('SERVICE_ROLE', 'api') != 'scheduler':
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from .scheduler import setup_scheduler, run_scheduled_scan
            tz = os.getenv('JOB_HUNTER_TIMEZONE', 'Asia/Kolkata')
            _embedded_scheduler = BackgroundScheduler(timezone=tz)
            setup_scheduler(_embedded_scheduler)
            _embedded_scheduler.start()
            log.info('Embedded Job Hunter BackgroundScheduler active for timezone %s', tz)
            if os.getenv('RUN_SCHEDULED_SCAN_ON_STARTUP', 'false').lower() in {'1', 'true', 'yes'}:
                log.info('Running startup scan in background thread...')
                threading.Thread(target=run_scheduled_scan, daemon=True).start()
        except Exception as exc:
            log.exception('Failed to start embedded scheduler: %s', exc)

    yield

    if _embedded_scheduler and getattr(_embedded_scheduler, 'running', False):
        try:
            _embedded_scheduler.shutdown(wait=False)
            log.info('Embedded BackgroundScheduler stopped')
        except Exception:
            pass

app=FastAPI(title='VentureGPT Job Hunter API',version='1.0.0',lifespan=lifespan)

class RateLimiter:
    def __init__(self):
        self.window=int(os.getenv('RATE_LIMIT_WINDOW_SECONDS','60'))
        self.limit=int(os.getenv('RATE_LIMIT_REQUESTS','120'))
        self.login_limit=int(os.getenv('LOGIN_RATE_LIMIT','8'))
        self._memory={}
        self._redis=None
        url=os.getenv('REDIS_URL','')
        if url:
            try:
                import redis
                self._redis=redis.Redis.from_url(url, decode_responses=True, socket_timeout=1)
            except Exception: log.warning('Redis rate limiter unavailable; memory limiter will be used')
    def hit(self, key, limit=None):
        limit=limit or self.limit
        bucket=int(time.time())//self.window
        rkey=f'jh:rl:{key}:{bucket}'
        try:
            if self._redis:
                n=self._redis.incr(rkey)
                if n == 1: self._redis.expire(rkey,self.window+2)
                return n <= limit
        except Exception:
            pass
        now=time.time(); start,count=self._memory.get(rkey,(now,0))
        if now-start >= self.window: start,count=now,0
        count += 1; self._memory[rkey]=(start,count)
        return count <= limit
    def login(self, ip): return self.hit(f'login:{ip}',self.login_limit)
    def api(self, ip): return self.hit(f'api:{ip}',self.limit)

import time
limiter=RateLimiter()

@app.middleware('http')
async def security_middleware(request: Request, call_next):
    ip=client_ip(request)
    if request.url.path.startswith('/auth/login') and not limiter.login(ip):
        audit('rate_limit_login', client_ip=ip)
        return JSONResponse({'detail':'Too many login attempts. Try again later.'}, status_code=429, headers={'Retry-After':os.getenv('RATE_LIMIT_WINDOW_SECONDS','60')})
    if request.url.path.startswith('/api/') and not limiter.api(ip):
        audit('rate_limit_api', client_ip=ip, details={'path':request.url.path})
        return JSONResponse({'detail':'Rate limit exceeded.'}, status_code=429, headers={'Retry-After':os.getenv('RATE_LIMIT_WINDOW_SECONDS','60')})
    if request.method not in {'GET','HEAD','OPTIONS'} and request.url.path not in {'/auth/login', '/api/cron/run'}:
        require_csrf(request)
    response=await call_next(request)
    security_headers(response)
    response.headers.setdefault('Cache-Control','no-store' if request.url.path.startswith(('/auth/','/api/')) else 'no-cache')
    return response

origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:3000').split(',') if x.strip()]
try:
    init_db()
except Exception:
    pass

class StatusBody(BaseModel): status:str=Field(pattern='^(new|shortlisted|applied|interview|rejected|archived)$')
class SettingsBody(BaseModel): email_updates: bool|None=None; min_match_score: float|None=Field(default=None,ge=0,le=1); cold_outreach_enabled: bool|None=None
class LoginBody(BaseModel): password:str
class ReviewBody(BaseModel): review_status:str=Field(pattern='^(approved|rejected|pending)$')
class ArtifactBody(BaseModel): artifact:str=Field(pattern='^(resume|cover_letter)$')

@app.get('/health')
def health(): return {'status':'ok','version':'1.2.0','database':database_ready(),'cache':cache_ping(),'search':('exa' if os.getenv('EXA_API_KEY') else '') + ('+tinyfish' if os.getenv('TINYFISH_API_KEY') else ''),'email_updates':os.getenv('EMAIL_UPDATES','true').lower() in {'1','true','yes'}}

@app.get('/ready')
def ready():
    if not os.getenv('DATABASE_URL'): return {'status':'degraded','reason':'DATABASE_URL not configured'}
    if not database_ready(): raise HTTPException(503,'Database unavailable')
    if os.getenv('CACHE_REQUIRED','true').lower() in {'1','true','yes'} and not cache_ping():
        raise HTTPException(503,'Redis cache unavailable')
    if not (os.getenv('EXA_API_KEY') or os.getenv('TINYFISH_API_KEY')): raise HTTPException(503,'No search provider configured')
    return {'status':'ready'}

@app.post('/auth/login')
def login(body:LoginBody, request:Request):
    expected=os.getenv('DASHBOARD_PASSWORD','')
    if not expected or not hmac.compare_digest(body.password, expected):
        audit('login_failed', client_ip=client_ip(request))
        raise HTTPException(401,'Invalid credentials')
    resp=JSONResponse({'ok':True})
    same_site=os.getenv('COOKIE_SAMESITE','lax').lower()
    if same_site not in {'lax','strict','none'}: same_site='lax'
    resp.set_cookie(COOKIE,issue_session(),httponly=True,secure=os.getenv('COOKIE_SECURE','false').lower() in {'1','true','yes'},samesite=same_site,max_age=86400,path='/')
    audit('login_success', client_ip=client_ip(request))
    return resp

@app.get('/auth/csrf')
def csrf(request:Request):
    if os.getenv('AUTH_REQUIRED','true').lower() in {'1','true','yes'} and not valid_session(request.cookies.get(COOKIE,'')):
        raise HTTPException(401,'Not authenticated')
    token=new_csrf_token(); resp=JSONResponse({'csrf_token':token}); set_csrf_cookie(resp,token); return resp

@app.post('/auth/logout')
def logout(request:Request):
    audit('logout', client_ip=client_ip(request))
    resp=JSONResponse({'ok':True}); resp.delete_cookie(COOKIE,path='/'); return resp

@app.get('/auth/me')
def me(request:Request):
    if os.getenv('AUTH_REQUIRED','true').lower() in {'1','true','yes'} and not valid_session(request.cookies.get(COOKIE,'')):
        raise HTTPException(401,'Not authenticated')
    return {'authenticated':True,'email':os.getenv('NOTIFY_TO','')}

@app.post('/api/runs',dependencies=[Depends(require_auth)])
def run_agent(queries:int=8, results_per_query:int=5):
    lock=None
    try:
        rc=cache_client()
        if rc:
            lock=rc.lock('jh:v1:agent-run', timeout=int(os.getenv('AGENT_RUN_LOCK_SECONDS','1800')), blocking_timeout=1)
            if not lock.acquire(blocking=True):
                raise HTTPException(409,'Another agent run is already in progress.')
        jobs,packages=run(JobConfig(),queries,results_per_query)
        notify_update('Scan completed', f'{len(jobs)} jobs discovered; {len(packages)} application packages prepared. Human review remains required.', swallow=True)
        notify_job_digest(jobs, packages, 'New matching jobs with apply links', swallow=True)
        cache_delete('dashboard','main')
        return {'jobs':[j.model_dump() for j in jobs],'packages':[p.model_dump() for p in packages]}
    except HTTPException:
        raise
    except Exception as e:
        log.exception('Scan failed')
        notify_update('Scan failed', str(e), swallow=True)
        raise HTTPException(500,'Scan failed. See server logs and notification email.')
    finally:
        if lock:
            try: lock.release()
            except Exception: pass

@app.get('/api/dashboard',dependencies=[Depends(require_auth)])
def dashboard():
    cached=cache_get('dashboard','main')
    if cached is not None: return cached
    jobs=query('''SELECT * FROM jobs
        WHERE last_run_at >= NOW() - INTERVAL '1 day'
        ORDER BY last_run_at DESC,
                 (work_mode = 'remote') DESC,
                 (work_mode = 'hybrid') DESC,
                 CASE UPPER(COALESCE(currency,''))
                   WHEN 'USD' THEN 5 WHEN 'EUR' THEN 4 WHEN 'AED' THEN 3 WHEN 'SAR' THEN 2
                   WHEN 'INR' THEN 0 ELSE 1 END DESC,
                 match_score DESC NULLS LAST,last_seen_at DESC LIMIT 100''')
    runs=query('SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 20')
    packages=query('''SELECT DISTINCT ON (p.job_url) p.*, COALESCE(j.application_url,j.url) AS application_url
        FROM application_packages p JOIN jobs j ON j.url=p.job_url
        ORDER BY p.job_url, p.created_at DESC, p.id DESC''')
    packages.sort(key=lambda package: (package.get('created_at') or ''), reverse=True)
    payload={'jobs':jobs,'runs':runs,'packages':packages,'counts':{'jobs':len(jobs),'strong_matches':sum((j.get('match_score') or 0)>=.8 for j in jobs),'remote':sum(j.get('work_mode')=='remote' for j in jobs),'ready':len(packages)},'scheduler':get_scheduler_status()}
    cache_set('dashboard','main',payload,int(os.getenv('CACHE_DASHBOARD_TTL_SECONDS','15')))
    return payload

@app.get('/api/jobs',dependencies=[Depends(require_auth)])
def jobs(status:str|None=None,source:str|None=None,remote:str|None=None,min_score:float=0,search:str|None=None):
    sql='SELECT * FROM jobs WHERE COALESCE(match_score,0) >= %s'; params=[min_score]
    if source: sql+=' AND source_title ILIKE %s'; params.append('%'+source+'%')
    if remote: sql+=' AND work_mode=%s'; params.append(remote)
    if status: sql+=' AND application_status=%s'; params.append(status)
    if search: sql+=' AND (title ILIKE %s OR company ILIKE %s OR location ILIKE %s)'; params += ['%'+search+'%']*3
    sql+=''' AND last_run_at >= NOW() - INTERVAL '1 day'
             ORDER BY last_run_at DESC,
                 (work_mode = 'remote') DESC,
                 (work_mode = 'hybrid') DESC,
                 CASE UPPER(COALESCE(currency,''))
                   WHEN 'USD' THEN 5 WHEN 'EUR' THEN 4 WHEN 'AED' THEN 3 WHEN 'SAR' THEN 2
                   WHEN 'INR' THEN 0 ELSE 1 END DESC,
                 match_score DESC NULLS LAST,last_seen_at DESC LIMIT 200'''
    cache_key='|'.join(str(x) for x in [status,source,remote,min_score,search])
    cached=cache_get('jobs',cache_key)
    if cached is not None: return cached
    payload=query(sql,params)
    cache_set('jobs',cache_key,payload,int(os.getenv('CACHE_JOBS_TTL_SECONDS','20')))
    return payload

@app.get('/api/jobs/{job_id}',dependencies=[Depends(require_auth)])
def job(job_id:int):
    rows=query('SELECT * FROM jobs WHERE id=%s',(job_id,))
    if not rows: raise HTTPException(404,'Job not found')
    return rows[0]

def _job_from_row(row):
    from .models import Job
    values={key: row.get(key) for key in Job.model_fields if key in row}
    for key in ('company','source_title','source_category','location','work_mode','salary','currency','description','application_url','sponsorship','eligibility_note','posted_date','search_query'):
        if values.get(key) is None: values[key]=''
    for key in ('requirements','contact_emails','contact_phones','reasons','gaps'):
        if values.get(key) is None: values[key]=[]
    return Job(**values)

@app.get('/api/jobs/{job_id}/package',dependencies=[Depends(require_auth)])
def job_package(job_id:int):
    rows=query('SELECT url FROM jobs WHERE id=%s',(job_id,))
    if not rows: raise HTTPException(404,'Job not found')
    packages=query('''SELECT * FROM application_packages
        WHERE job_url=%s ORDER BY created_at DESC, id DESC LIMIT 1''',(rows[0]['url'],))
    return packages[0] if packages else None

@app.post('/api/jobs/{job_id}/package',dependencies=[Depends(require_auth)])
def generate_job_package(job_id:int, request:Request):
    rows=query('SELECT * FROM jobs WHERE id=%s',(job_id,))
    if not rows: raise HTTPException(404,'Job not found')
    job_obj=_job_from_row(rows[0])
    if not job_obj.description.strip():
        raise HTTPException(422,'This job has no JD content to review yet.')
    try:
        from .model_provider import LoadBalancedModelProvider, StubModelProvider
        provider=LoadBalancedModelProvider() if os.getenv('USE_MODEL','true').lower() in {'1','true','yes'} else StubModelProvider()
        package=provider.build_application_package(job_obj)
        package_id=save_package(package,job_obj)
    except Exception:
        log.exception('On-demand package generation failed', extra={'job_id':job_id})
        raise HTTPException(502,'Could not create application materials. The job was not changed.')
    audit('package_generated', client_ip=client_ip(request), details={'job_id':job_id,'package_id':package_id})
    return {'id':package_id,**package.model_dump(),'application_url':job_obj.application_url or job_obj.url,
            'jd_snapshot':job_obj.description,'requirements_snapshot':job_obj.requirements}

@app.patch('/api/packages/{package_id}/review',dependencies=[Depends(require_auth)])
def review_package(package_id:int, body:ReviewBody, request:Request):
    rows=query('SELECT id FROM application_packages WHERE id=%s',(package_id,))
    if not rows: raise HTTPException(404,'Package not found')
    execute('UPDATE application_packages SET review_status=%s, needs_human_review=%s WHERE id=%s',
            (body.review_status,body.review_status != 'approved',package_id))
    cache_delete('dashboard','main'); cache_delete('applications','main')
    audit('package_reviewed', client_ip=client_ip(request), details={'package_id':package_id,'review_status':body.review_status})
    return {'id':package_id,'review_status':body.review_status}

@app.get('/api/packages/{package_id}/download',dependencies=[Depends(require_auth)])
def download_package(package_id:int, artifact:str='resume'):
    if artifact not in {'resume','cover_letter'}:
        raise HTTPException(400,'Artifact must be resume or cover_letter')
    rows=query('''SELECT p.*, j.title AS job_title, j.company AS job_company
                 FROM application_packages p JOIN jobs j ON j.url=p.job_url
                 WHERE p.id=%s''',(package_id,))
    if not rows: raise HTTPException(404,'Package not found')
    row=rows[0]
    content=row['tailored_resume'] if artifact == 'resume' else (row.get('cover_letter') or '')
    if not content: raise HTTPException(404,'This package has no cover letter')
    stem='-'.join(str(row.get('job_title') or row.get('role') or 'job').lower().split())[:80]
    filename=f'{stem}-{artifact}.txt'
    return PlainTextResponse(content,headers={'Content-Disposition':f'attachment; filename="{filename}"'})

@app.get('/api/applications',dependencies=[Depends(require_auth)])
def applications():
    cached=cache_get('applications','main')
    if cached is not None: return cached
    payload=query('''SELECT DISTINCT ON (p.job_url) p.*, COALESCE(j.application_url,j.url) AS application_url
        FROM application_packages p JOIN jobs j ON j.url=p.job_url
        ORDER BY p.job_url, p.created_at DESC, p.id DESC''')
    payload.sort(key=lambda package: (package.get('created_at') or ''), reverse=True)
    cache_set('applications','main',payload,int(os.getenv('CACHE_APPLICATIONS_TTL_SECONDS','20')))
    return payload
@app.get('/api/runs',dependencies=[Depends(require_auth)])
def runs():
    cached=cache_get('runs','main')
    if cached is not None: return cached
    payload=query('SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 100')
    cache_set('runs','main',payload,int(os.getenv('CACHE_RUNS_TTL_SECONDS','20')))
    return payload
@app.get('/api/notifications',dependencies=[Depends(require_auth)])
def notifications():
    cached=cache_get('notifications','main')
    if cached is not None: return cached
    payload=query('SELECT * FROM notification_events ORDER BY created_at DESC LIMIT 100')
    cache_set('notifications','main',payload,int(os.getenv('CACHE_NOTIFICATIONS_TTL_SECONDS','30')))
    return payload
@app.get('/api/sources',dependencies=[Depends(require_auth)])
def sources():
    cached=cache_get('sources','main')
    if cached is not None: return cached
    counts=query('SELECT source_title, COUNT(*) AS jobs FROM jobs GROUP BY source_title ORDER BY jobs DESC')
    count_map={str(x.get('source_title') or ''):int(x.get('jobs') or 0) for x in counts}
    official={
        'Randstad':'https://www.randstad.in/jobs/s-it/',
        'Michael Page':'https://www.michaelpage.co.in/jobs/it/technology-telecoms',
        'Quess Global Mobility':'https://www.quesscorp.com/global-mobility-services/',
        'Manpower First':'https://manpowerfirst.com/jobs/',
        'BCM Group':'https://bcmgroup.in/',
        'Ambe International':'https://www.ambeinter.com/jobs-in-india.php',
        'Abroseas':'https://www.abroseas.com/',
    }
    payload=[{'name':src.name,'category':src.category,'domains':list(src.domains),'jobs':count_map.get(src.name,0),'official_url':official.get(src.name)} for src in SOURCES]
    cache_set('sources','main',payload,int(os.getenv('CACHE_SOURCES_TTL_SECONDS','60')))
    return payload

@app.get('/api/settings',dependencies=[Depends(require_auth)])
def settings():
    return {'email_updates':get_setting('email_updates',os.getenv('EMAIL_UPDATES','true').lower() in {'1','true','yes'}),
            'notify_to':os.getenv('NOTIFY_TO',''),'min_match_score':float(get_setting('min_match_score',os.getenv('MIN_MATCH_SCORE','0.60'))),
            'auto_apply':False,'cold_outreach_enabled':get_setting('cold_outreach_enabled',os.getenv('COLD_OUTREACH_ENABLED','false').lower() in {'1','true','yes'}),'search_primary':'Exa','search_fallback':'TinyFish','auth_required':os.getenv('AUTH_REQUIRED','true').lower() in {'1','true','yes'},
            'schedule_times':os.getenv('JOB_HUNTER_TIMES','08:00'),'schedule_days':os.getenv('JOB_HUNTER_DAYS','mon-sun'),'timezone':os.getenv('JOB_HUNTER_TIMEZONE','Asia/Kolkata'),
            'scheduler':get_scheduler_status()}

@app.patch('/api/settings',dependencies=[Depends(require_auth)])
def update_settings(body:SettingsBody):
    if body.email_updates is not None: set_setting('email_updates',body.email_updates); os.environ['EMAIL_UPDATES']='true' if body.email_updates else 'false'
    if body.min_match_score is not None: set_setting('min_match_score',body.min_match_score); os.environ['MIN_MATCH_SCORE']=str(body.min_match_score)
    if body.cold_outreach_enabled is not None:
        set_setting('cold_outreach_enabled',body.cold_outreach_enabled)
        os.environ['COLD_OUTREACH_ENABLED']='true' if body.cold_outreach_enabled else 'false'
    notify_update('Settings updated','Dashboard notification settings changed.',swallow=True)
    return settings()

@app.patch('/api/jobs/{job_id}/status',dependencies=[Depends(require_auth)])
def status(job_id:int, body:StatusBody, request:Request):
    if not query('SELECT id FROM jobs WHERE id=%s',(job_id,)): raise HTTPException(404,'Job not found')
    execute('UPDATE jobs SET application_status=%s WHERE id=%s',(body.status,job_id))
    cache_delete('dashboard','main')
    cache_delete_namespace('jobs')
    audit('job_status_changed', client_ip=client_ip(request), details={'job_id':job_id,'status':body.status})
    notify_update('Application status changed', f'Job #{job_id} is now {body.status}.', swallow=True)
    return {'id':job_id,'status':body.status}


@app.post('/api/jobs/{job_id}/cold-outreach',dependencies=[Depends(require_auth)])
def cold_outreach(job_id:int, request:Request):
    rows=query('SELECT * FROM jobs WHERE id=%s',(job_id,))
    if not rows: raise HTTPException(404,'Job not found')
    row=rows[0]
    from .models import Job
    job_obj=Job(**{k:row.get(k) for k in Job.model_fields if k in row})
    result=send_cold_outreach(job_obj, request_actor=client_ip(request))
    if result.get('status') == 'failed': raise HTTPException(502, result.get('error','Cold outreach failed'))
    return result


@app.get('/api/security',dependencies=[Depends(require_auth)])
def security():
    return security_posture()

@app.get('/api/security/audit',dependencies=[Depends(require_auth)])
def security_audit():
    return query('SELECT id,created_at,event,actor,client_ip,details FROM security_audit_log ORDER BY created_at DESC LIMIT 100')

@app.get('/api/scheduler/status')
def scheduler_status():
    return get_scheduler_status()

@app.post('/api/cron/run')
def trigger_cron_run(request: Request, background_tasks: BackgroundTasks):
    allowed_secrets = [s for s in [os.getenv('CRON_SECRET', ''), os.getenv('DASHBOARD_SESSION_SECRET', '')] if s]
    auth_header = request.headers.get('Authorization', '')
    bearer_token = auth_header.removeprefix('Bearer ').strip() if auth_header.startswith('Bearer ') else ''
    header_secret = request.headers.get('X-Cron-Secret', '') or bearer_token
    is_secret_auth = any(header_secret and hmac.compare_digest(header_secret, s) for s in allowed_secrets)

    token = request.cookies.get(COOKIE)
    is_session_auth = bool(token and valid_session(token))

    if not is_secret_auth and not is_session_auth:
        audit('cron_trigger_unauthorized', client_ip=client_ip(request))
        raise HTTPException(401, 'Unauthorized: invalid cron secret or session')

    from .scheduler import run_scheduled_scan
    background_tasks.add_task(run_scheduled_scan)
    audit('cron_trigger_accepted', client_ip=client_ip(request))
    return {
        'ok': True,
        'status': 'triggered',
        'message': 'Job Hunter scan initiated in background under distributed lock',
        'scheduler': get_scheduler_status(),
    }


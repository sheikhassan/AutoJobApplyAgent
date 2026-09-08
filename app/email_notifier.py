import logging, os, smtplib, ssl
from email.message import EmailMessage
from .database import log_notification, get_setting
log=logging.getLogger(__name__)

def send_via_resend(subject:str, body:str, html:str|None=None) -> bool:
    api_key=os.getenv('RESEND_API_KEY','')
    if not api_key: return False
    import requests
    from_email=os.getenv('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
    to_email=os.getenv('NOTIFY_TO','')
    if not to_email: return False
    payload={'from':from_email,'to':[to_email],'subject':subject,'text':body}
    if html: payload['html']=html
    resp=requests.post('https://api.resend.com/emails',
                       headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json'},
                       json=payload,timeout=15)
    if not resp.ok: raise RuntimeError(f'Resend API error: {resp.status_code} {resp.text}')
    return True

def send_email(subject:str, body:str, html:str|None=None):
    if os.getenv('RESEND_API_KEY'):
        try:
            if send_via_resend(subject, body, html): return
        except Exception as exc:
            log.warning('Resend HTTPS email failed, trying SMTP fallback: %s', exc)
    required=['SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','NOTIFY_TO']
    missing=[x for x in required if not os.getenv(x)]
    if missing: raise RuntimeError('Missing email settings: '+', '.join(missing))
    msg=EmailMessage(); msg['Subject']=subject; msg['From']=os.environ['SMTP_USER']; msg['To']=os.environ['NOTIFY_TO']; msg.set_content(body)
    if html: msg.add_alternative(html,subtype='html')
    host=os.environ['SMTP_HOST']; port=int(os.environ['SMTP_PORT']); timeout=int(os.getenv('SMTP_TIMEOUT_SECONDS','30'))
    with smtplib.SMTP(host,port,timeout=timeout) as s:
        if os.getenv('SMTP_STARTTLS','true').lower() in {'1','true','yes'}: s.starttls(context=ssl.create_default_context())
        s.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']); s.send_message(msg)

def notify_update(event:str,detail:str,swallow:bool=False):
    enabled=get_setting('email_updates',os.getenv('EMAIL_UPDATES','true').lower() in {'1','true','yes'})
    if not enabled: return False
    subject=f'Job Hunter Update — {event}'
    try:
        send_email(subject,f'{event}\n\n{detail}\n\nJob Hunter Agent')
        log_notification(event,subject,detail,os.getenv('NOTIFY_TO',''),True)
        return True
    except Exception as exc:
        log.exception('Email notification failed for %s',event)
        try: log_notification(event,subject,detail,os.getenv('NOTIFY_TO',''),False,str(exc))
        except Exception: pass
        if not swallow: raise
        return False


def notify_job_digest(jobs, packages, event="New job matches", swallow:bool=False):
    """Email actionable job matches with direct application links and artifact status."""
    enabled=get_setting('email_updates',os.getenv('EMAIL_UPDATES','true').lower() in {'1','true','yes'})
    if not enabled: return False
    rows=[]
    for j in list(jobs)[:25]:
        url=getattr(j,'application_url','') or getattr(j,'url','')
        rows.append(f"{getattr(j,'match_score',0):.0%} | {getattr(j,'work_mode','unknown')} | {getattr(j,'title','Role')} | {getattr(j,'company','Company') or 'Company'} | {url}")
    body=(f"{event}\n\n" + "\n".join(rows) +
          f"\n\nTailored application packages prepared: {len(list(packages))}.\n"
          "Every application requires your human review; the agent does not auto-submit applications.")
    try:
        send_email(f"Job Hunter — {event}", body)
        log_notification(event,f"Job Hunter — {event}",body,os.getenv('NOTIFY_TO',''),True)
        return True
    except Exception as exc:
        log.exception('Job digest email failed')
        try: log_notification(event,f"Job Hunter — {event}",body,os.getenv('NOTIFY_TO',''),False,str(exc))
        except Exception: pass
        if not swallow: raise
        return False

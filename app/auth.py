import hashlib,hmac,os,secrets,time
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from .security import new_csrf_token, set_csrf_cookie

COOKIE='jh_session'

def _secret():
    s=os.getenv('DASHBOARD_SESSION_SECRET','')
    if len(s)<32: raise RuntimeError('DASHBOARD_SESSION_SECRET must be at least 32 characters')
    return s.encode()

def issue_session():
    payload=f'{int(time.time())}:{secrets.token_urlsafe(24)}'
    sig=hmac.new(_secret(),payload.encode(),hashlib.sha256).hexdigest()
    return f'{payload}:{sig}'

def valid_session(token):
    try:
        ts,nonce,sig=token.split(':',2)
        if int(time.time())-int(ts)>86400: return False
        expected=hmac.new(_secret(),f'{ts}:{nonce}'.encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig,expected)
    except Exception: return False

def require_auth(request: Request):
    if os.getenv('AUTH_REQUIRED','true').lower() not in {'1','true','yes'}: return
    token=request.cookies.get(COOKIE)
    if not token or not valid_session(token): raise HTTPException(401,'Authentication required')

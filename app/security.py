import hashlib, hmac, ipaddress, os, secrets, socket, time
from urllib.parse import urlparse
from fastapi import HTTPException, Request

SAFE_METHODS = {'GET','HEAD','OPTIONS'}
CSRF_COOKIE = 'jh_csrf'

class SecurityError(Exception):
    pass

def _bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {'1','true','yes','on'}

def client_ip(request: Request) -> str:
    # Do not trust X-Forwarded-For unless the deployment explicitly puts the app
    # behind a trusted proxy. proxy-headers are enabled only at the ASGI layer.
    return request.client.host if request.client else 'unknown'

def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)

def set_csrf_cookie(response, token: str):
    response.set_cookie(CSRF_COOKIE, token, httponly=False,
                        secure=_bool('COOKIE_SECURE', False), samesite='lax',
                        max_age=86400, path='/')

def require_csrf(request: Request):
    if request.method in SAFE_METHODS or not _bool('CSRF_PROTECTION', True):
        return
    cookie = request.cookies.get(CSRF_COOKIE, '')
    header = request.headers.get('X-CSRF-Token', '')
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(403, 'CSRF validation failed')

def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    response.headers.setdefault('Content-Security-Policy', os.getenv(
        'CONTENT_SECURITY_POLICY',
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
        "img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "connect-src 'self' https:; form-action 'self'"))
    if _bool('COOKIE_SECURE', False):
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

def validate_external_url(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > 2048:
        raise SecurityError('URL is invalid or too long')
    p = urlparse(raw.strip())
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password:
        raise SecurityError('Only public HTTP(S) URLs are allowed')
    host = p.hostname.rstrip('.').lower()
    if host in {'localhost','localhost.localdomain'} or host.endswith('.local'):
        raise SecurityError('Private/local hosts are not allowed')
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SecurityError('Hostname does not resolve') from exc
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast or addr.is_unspecified:
            raise SecurityError('Private or reserved network targets are not allowed')
    return raw.strip()

def redact_secret(value: str | None) -> str:
    if not value:
        return ''
    if len(value) <= 8:
        return '********'
    return value[:3] + '…' + value[-3:]

def security_posture() -> dict:
    return {
        'auth_required': _bool('AUTH_REQUIRED', True),
        'csrf_protection': _bool('CSRF_PROTECTION', True),
        'secure_cookie': _bool('COOKIE_SECURE', False),
        'rate_limit_enabled': _bool('RATE_LIMIT_ENABLED', True),
        'rate_limit_backend': 'redis' if os.getenv('REDIS_URL') else 'memory',
        'auto_apply': False,
        'external_url_ssrf_guard': True,
        'prompt_injection_boundary': True,
        'secrets_server_side': True,
        'https_required_in_production': _bool('REQUIRE_HTTPS', False),
    }

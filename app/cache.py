"""Redis-backed application cache with safe failure behavior.

Cache is an optimization only: the database remains the source of truth.
"""
import hashlib
import json
import os
from typing import Any

try:
    import redis
except ImportError:
    redis = None

_client = None


def get_client():
    global _client
    url = os.getenv("REDIS_URL", "")
    if not url or redis is None:
        return None
    if _client is None:
        _client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "1.5")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "1.5")),
            health_check_interval=30,
        )
    return _client


def _key(namespace: str, value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()
    return f"jh:v1:{namespace}:{digest}"


def get(namespace: str, value: str):
    c = get_client()
    if not c:
        return None
    try:
        raw = c.get(_key(namespace, value))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def set(namespace: str, value: str, payload: Any, ttl: int | None = None) -> bool:
    c = get_client()
    if not c:
        return False
    ttl = ttl or int(os.getenv("CACHE_DEFAULT_TTL_SECONDS", "30"))
    try:
        c.setex(_key(namespace, value), max(1, ttl), json.dumps(payload, default=str))
        return True
    except Exception:
        return False


def delete(namespace: str, value: str) -> None:
    c = get_client()
    if not c:
        return
    try:
        c.delete(_key(namespace, value))
    except Exception:
        pass


def delete_namespace(namespace: str) -> None:
    c = get_client()
    if not c:
        return
    try:
        pattern = f"jh:v1:{namespace}:*"
        batch = []
        for key in c.scan_iter(match=pattern, count=100):
            batch.append(key)
            if len(batch) >= 100:
                c.delete(*batch)
                batch.clear()
        if batch:
            c.delete(*batch)
    except Exception:
        pass


def bump(namespace: str) -> int:
    c = get_client()
    if not c:
        return 0
    key = f"jh:v1:version:{namespace}"
    try:
        return int(c.incr(key))
    except Exception:
        return 0


def version(namespace: str) -> int:
    c = get_client()
    if not c:
        return 0
    try:
        return int(c.get(f"jh:v1:version:{namespace}") or 0)
    except Exception:
        return 0


def ping() -> bool:
    c = get_client()
    if not c:
        return False
    try:
        return bool(c.ping())
    except Exception:
        return False

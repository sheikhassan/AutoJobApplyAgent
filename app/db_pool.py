"""Production PostgreSQL connection pooling and health helpers."""
import os
from contextlib import contextmanager
from typing import Iterator

try:
    from psycopg_pool import ConnectionPool
except ImportError:
    ConnectionPool = None

_pool = None


def _enabled() -> bool:
    return bool(os.getenv("DATABASE_URL"))


def get_pool():
    global _pool
    if not _enabled():
        return None
    if ConnectionPool is None:
        raise RuntimeError("psycopg-pool is required when DATABASE_URL is configured")
    if _pool is None:
        min_size = max(1, int(os.getenv("DB_POOL_MIN_SIZE", "2")))
        max_size = max(min_size, int(os.getenv("DB_POOL_MAX_SIZE", "10")))
        timeout = float(os.getenv("DB_POOL_TIMEOUT_SECONDS", "10"))
        kwargs = {
            "conninfo": os.environ["DATABASE_URL"],
            "min_size": min_size,
            "max_size": max_size,
            "timeout": timeout,
            "max_idle": float(os.getenv("DB_POOL_MAX_IDLE_SECONDS", "300")),
            "max_lifetime": float(os.getenv("DB_POOL_MAX_LIFETIME_SECONDS", "1800")),
            "open": False,
        }
        _pool = ConnectionPool(**kwargs)
        _pool.open(wait=True, timeout=timeout)
    return _pool


@contextmanager
def connection() -> Iterator:
    pool = get_pool()
    if pool is None:
        yield None
        return
    with pool.connection() as conn:
        yield conn


def check() -> bool:
    try:
        with connection() as conn:
            if conn is None:
                return False
            conn.execute("SELECT 1").fetchone()
            return True
    except Exception:
        return False


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None

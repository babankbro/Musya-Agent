import asyncpg
import psycopg2
import psycopg2.pool
from contextlib import contextmanager
from src.config import get_settings

_async_pool: asyncpg.Pool | None = None
_sync_pool: psycopg2.pool.ThreadedConnectionPool | None = None


async def get_async_pool() -> asyncpg.Pool:
    """Get or create the async connection pool."""
    global _async_pool
    if _async_pool is None:
        s = get_settings()
        _async_pool = await asyncpg.create_pool(
            host=s.DB_HOST,
            port=s.DB_PORT,
            database=s.DB_NAME,
            user=s.DB_USER,
            password=s.DB_PASSWORD,
            min_size=2,
            max_size=10,
        )
    return _async_pool


async def close_async_pool() -> None:
    global _async_pool
    if _async_pool is not None:
        await _async_pool.close()
        _async_pool = None


def get_sync_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Get or create the sync connection pool (for CrewAI tools)."""
    global _sync_pool
    if _sync_pool is None:
        s = get_settings()
        _sync_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            host=s.DB_HOST,
            port=s.DB_PORT,
            database=s.DB_NAME,
            user=s.DB_USER,
            password=s.DB_PASSWORD,
        )
    return _sync_pool


def close_sync_pool() -> None:
    global _sync_pool
    if _sync_pool is not None:
        _sync_pool.closeall()
        _sync_pool = None


@contextmanager
def get_db_connection():
    """Context manager for sync DB connection from pool."""
    pool = get_sync_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def query_db(sql: str, params: tuple | list | None = None) -> list[dict]:
    """Execute a query and return rows as dicts (supports SELECT + RETURNING)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            if cur.description is None:
                return []
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]


def execute_db(sql: str, params: tuple | list | None = None) -> int:
    """Execute a write query (INSERT/UPDATE/DELETE) and return rowcount."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount

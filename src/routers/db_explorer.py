"""Database Explorer API — list tables, columns, and paginated rows."""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.db.pool import get_async_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/db", tags=["db-explorer"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce(value: Any) -> Any:
    """Convert non-JSON-serialisable DB values to safe types."""
    if value is None:
        return None
    # asyncpg returns vectors as a custom type; detect by module name
    t = type(value)
    module = getattr(t, "__module__", "") or ""
    if "pgproto" in module or t.__name__ in ("BitString", "Point", "Circle"):
        return "[…vector…]"
    if hasattr(value, "isoformat"):          # date / datetime / time
        return value.isoformat()
    if hasattr(value, "__float__") and not isinstance(value, (int, float, bool)):
        return float(value)                  # Decimal
    return value


def _coerce_row(row) -> dict:
    return {k: _coerce(v) for k, v in dict(row).items()}


async def _assert_table_exists(conn, table: str) -> None:
    """Raise HTTP 404 if *table* is not in the public schema."""
    exists = await conn.fetchval(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name   = $1
        """,
        table,
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Table '{table}' not found")


# ---------------------------------------------------------------------------
# Task 1 — list tables
# ---------------------------------------------------------------------------

@router.get("/tables")
async def list_tables():
    """Return all public tables with approximate row counts."""
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.table_name,
                   GREATEST(0, c.reltuples::bigint) AS row_count
            FROM information_schema.tables t
            JOIN pg_class c
              ON c.relname = t.table_name
             AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            WHERE t.table_schema = 'public'
              AND t.table_type   = 'BASE TABLE'
            ORDER BY t.table_name
            """
        )
    return {"tables": [{"name": r["table_name"], "row_count": r["row_count"]} for r in rows]}


# ---------------------------------------------------------------------------
# Task 2 — column metadata
# ---------------------------------------------------------------------------

@router.get("/tables/{table}/columns")
async def list_columns(table: str):
    """Return column names, data types, and nullability for *table*."""
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        await _assert_table_exists(conn, table)
        rows = await conn.fetch(
            """
            SELECT column_name,
                   data_type,
                   is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = $1
            ORDER BY ordinal_position
            """,
            table,
        )
    return {
        "table": table,
        "columns": [
            {
                "name": r["column_name"],
                "data_type": r["data_type"],
                "nullable": r["is_nullable"] == "YES",
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Task 3 — paginated rows with optional filter
# ---------------------------------------------------------------------------

@router.get("/tables/{table}/rows")
async def list_rows(
    table: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1),
    filter_col: str = Query(default=""),
    filter_val: str = Query(default=""),
):
    """Return paginated rows from *table*, with optional equality filter."""
    page_size = min(page_size, 200)
    offset = (page - 1) * page_size

    pool = await get_async_pool()
    async with pool.acquire() as conn:
        await _assert_table_exists(conn, table)

        # Resolve valid column names once for safety
        col_rows = await conn.fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            """,
            table,
        )
        valid_columns = {r["column_name"] for r in col_rows}

        # Build WHERE clause when filter is requested
        where_sql = ""
        params: list[Any] = []
        if filter_col and filter_val:
            if filter_col not in valid_columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Column '{filter_col}' does not exist in table '{table}'",
                )
            where_sql = f'WHERE "{filter_col}" = $1'
            params.append(filter_val)

        # Total count
        count_sql = f'SELECT COUNT(*) FROM "{table}" {where_sql}'
        total = await conn.fetchval(count_sql, *params)

        # Data rows — offset/limit params come after any filter param
        n = len(params)
        data_sql = (
            f'SELECT * FROM "{table}" {where_sql} '
            f"LIMIT ${n + 1} OFFSET ${n + 2}"
        )
        rows = await conn.fetch(data_sql, *params, page_size, offset)

    return {
        "table": table,
        "total": total,
        "page": page,
        "page_size": page_size,
        "rows": [_coerce_row(r) for r in rows],
    }

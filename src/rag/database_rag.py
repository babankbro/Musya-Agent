"""Database RAG: structured queries against PostgreSQL marts and fact tables."""
import logging
from src.db.pool import query_db

logger = logging.getLogger(__name__)


def safe_query(sql: str, params: tuple | None = None) -> list[dict]:
    """Execute a read-only query with error handling."""
    try:
        return query_db(sql, params)
    except Exception as e:
        logger.error(f"Database query failed: {e}\nSQL: {sql}\nParams: {params}")
        return []


def get_table_columns(table_name: str) -> list[str]:
    """Get column names for a table (safe, no user input in table name)."""
    sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """
    rows = safe_query(sql, (table_name,))
    return [r["column_name"] for r in rows]


def get_table_sample(table_name: str, limit: int = 5) -> list[dict]:
    """Get sample rows from a known table. Only call with hardcoded table names."""
    allowed_tables = {
        "accident", "diabetes", "bipola",
        "mart_accident_summary", "mart_accident_hotspot",
        "fact_accident_event", "fact_accident_person",
        "dim_geography", "dim_time",
    }
    if table_name not in allowed_tables:
        logger.warning(f"Table {table_name} not in allowed list")
        return []
    sql = f"SELECT * FROM {table_name} LIMIT %s"  # noqa: S608
    return safe_query(sql, (limit,))

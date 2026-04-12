"""SQL tools for custom database queries and schema exploration."""
import json
import logging
from crewai.tools import tool
from src.db.pool import query_db

logger = logging.getLogger(__name__)


@tool("execute_custom_sql")
def execute_custom_sql(sql_query: str) -> str:
    """Execute a custom SQL SELECT query on the accident database.
    
    Args:
        sql_query: SQL SELECT query to execute. Must be a SELECT or WITH query only.
                  Do NOT include INSERT, UPDATE, DELETE, DROP, or other modification statements.
    
    Returns:
        JSON string with query results or error message.
        Format: {"success": true, "rows": [...], "row_count": N}
        
    Example queries:
        - "SELECT province_name, SUM(accident_count) as total FROM mart_province_year GROUP BY province_name"
        - "SELECT * FROM fact_accident_event WHERE csv_year = 2023 LIMIT 10"
        - "SELECT g.province_name, COUNT(*) FROM fact_accident_event f JOIN dim_geography g ON f.geography_id = g.geography_id GROUP BY g.province_name"
    
    Safety:
        - Only SELECT and WITH queries are allowed
        - Automatically adds LIMIT 1000 if no LIMIT specified
        - Returns error if query is not read-only
    """
    sql = sql_query.strip()
    
    # Safety check: only allow SELECT/WITH queries
    first_word = sql.split()[0].upper() if sql else ""
    if first_word not in ("SELECT", "WITH"):
        return json.dumps({
            "success": False,
            "error": "Only SELECT or WITH queries are allowed. Do not use INSERT, UPDATE, DELETE, DROP, or other modification statements.",
            "rows": []
        }, ensure_ascii=False)
    
    # Add LIMIT if not present (prevent huge result sets)
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + " LIMIT 1000"
    
    try:
        rows = query_db(sql)
        
        # Convert any non-JSON-serializable types
        clean_rows = []
        for row in rows:
            clean = {}
            for k, v in row.items():
                if hasattr(v, '__float__'):  # Decimal
                    clean[k] = float(v)
                elif hasattr(v, 'isoformat'):  # datetime/date
                    clean[k] = v.isoformat()
                else:
                    clean[k] = v
            clean_rows.append(clean)
        
        result = {
            "success": True,
            "rows": clean_rows,
            "row_count": len(clean_rows),
            "query": sql
        }
        
        logger.info(f"SQL query executed successfully: {len(clean_rows)} rows returned")
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"SQL query failed: {e}\nQuery: {sql}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "rows": [],
            "query": sql
        }, ensure_ascii=False)


@tool("explain_schema")
def explain_schema(table_name: str = "") -> str:
    """Get database schema information for accident tables.
    
    Args:
        table_name: Optional. Specific table name to get details for.
                   If empty, returns list of all available tables.
                   Examples: "fact_accident_event", "dim_geography", "mart_province_year"
    
    Returns:
        JSON string with schema information.
        
    Available tables:
        - fact_accident_event: Main accident events (event_datetime, geography_id, death_count, etc.)
        - fact_accident_person: Person-level details (age, sex, injury_level, etc.)
        - dim_geography: Geographic locations (province_name, district_name, latitude, longitude)
        - dim_road_segment: Road information (road_name, road_code, geography_id, km_marker)
        - dim_time: Time dimension (full_date, year_no, month_no, day_of_week)
        - dim_source: Data sources (source_name, source_type, owner_org)
        - mart_accident_summary: Monthly accident summaries (year_no, month_no, accident_count)
        - mart_accident_hotspot: High-risk locations (hotspot_score, accident_count)
        - mart_province_year: Province yearly summary (province_name, year_no, accident_count)
        - mart_province_road: Province road breakdown (province_name, road_name, year_no)
    """
    if not table_name:
        # Return list of all tables
        sql = """
            SELECT table_name, 
                   COALESCE(obj_description((table_schema||'.'||table_name)::regclass), 'No description') as description
            FROM information_schema.tables
            WHERE table_schema = 'public' 
              AND table_type = 'BASE TABLE'
              AND table_name IN (
                  'fact_accident_event', 'fact_accident_person',
                  'dim_geography', 'dim_road_segment', 'dim_time', 'dim_source',
                  'dim_population_group', 'dim_facility',
                  'mart_accident_summary', 'mart_accident_hotspot',
                  'mart_province_year', 'mart_province_road',
                  'document_registry', 'document_chunks', 'indicator_catalog'
              )
            ORDER BY 
                CASE 
                    WHEN table_name LIKE 'fact_%' THEN 1
                    WHEN table_name LIKE 'dim_%' THEN 2
                    WHEN table_name LIKE 'mart_%' THEN 3
                    ELSE 4
                END,
                table_name
        """
        try:
            rows = query_db(sql)
            return json.dumps({
                "success": True,
                "tables": [{"name": r["table_name"], "description": r["description"]} for r in rows],
                "count": len(rows)
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    
    # Get columns for specific table
    sql = """
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default,
            COALESCE(col_description((table_schema||'.'||table_name)::regclass::oid, ordinal_position), '') as description
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """
    try:
        rows = query_db(sql, (table_name,))
        if not rows:
            return json.dumps({
                "success": False,
                "error": f"Table '{table_name}' not found",
                "available_tables": [
                    "fact_accident_event", "fact_accident_person",
                    "dim_geography", "dim_road_segment", "dim_time", "dim_source",
                    "mart_accident_summary", "mart_accident_hotspot",
                    "mart_province_year", "mart_province_road"
                ]
            }, ensure_ascii=False)
        
        columns = []
        for r in rows:
            col_info = {
                "name": r["column_name"],
                "type": r["data_type"],
                "nullable": r["is_nullable"] == "YES",
            }
            if r["character_maximum_length"]:
                col_info["max_length"] = r["character_maximum_length"]
            if r["column_default"]:
                col_info["default"] = r["column_default"]
            if r["description"]:
                col_info["description"] = r["description"]
            columns.append(col_info)
        
        # Get sample data (first 3 rows)
        sample_sql = f"SELECT * FROM {table_name} LIMIT 3"
        sample_rows = query_db(sample_sql)
        
        # Clean sample data
        clean_samples = []
        for row in sample_rows:
            clean = {}
            for k, v in row.items():
                if hasattr(v, '__float__'):
                    clean[k] = float(v)
                elif hasattr(v, 'isoformat'):
                    clean[k] = v.isoformat()
                else:
                    clean[k] = v
            clean_samples.append(clean)
        
        return json.dumps({
            "success": True,
            "table_name": table_name,
            "columns": columns,
            "column_count": len(columns),
            "sample_rows": clean_samples
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Schema explain failed for table '{table_name}': {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "table_name": table_name
        }, ensure_ascii=False)


@tool("get_table_row_count")
def get_table_row_count(table_name: str) -> str:
    """Get the number of rows in a specific table.
    
    Args:
        table_name: Name of the table to count rows.
                   Examples: "fact_accident_event", "mart_province_year"
    
    Returns:
        JSON string with row count or error.
    """
    # Validate table name (prevent SQL injection)
    allowed_tables = [
        "fact_accident_event", "fact_accident_person",
        "dim_geography", "dim_road_segment", "dim_time", "dim_source",
        "mart_accident_summary", "mart_accident_hotspot",
        "mart_province_year", "mart_province_road"
    ]
    
    if table_name not in allowed_tables:
        return json.dumps({
            "success": False,
            "error": f"Table '{table_name}' not in allowed list",
            "allowed_tables": allowed_tables
        }, ensure_ascii=False)
    
    try:
        sql = f"SELECT COUNT(*) as row_count FROM {table_name}"
        rows = query_db(sql)
        count = rows[0]["row_count"] if rows else 0
        
        return json.dumps({
            "success": True,
            "table_name": table_name,
            "row_count": count
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "table_name": table_name
        }, ensure_ascii=False)

"""Test database connectivity and data availability."""
import pytest


class TestDatabaseConnection:
    """Test PostgreSQL connection and basic queries."""

    def test_db_pool_connects(self, db_pool):
        """Pool should connect to PostgreSQL successfully."""
        conn = db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
        finally:
            db_pool.putconn(conn)

    def test_query_db_helper(self, db_query):
        """query_db should return list of dicts."""
        rows = db_query("SELECT 1 AS value")
        assert len(rows) == 1
        assert rows[0]["value"] == 1

    def test_tables_exist(self, db_query):
        """All required Agent tables should exist."""
        expected_tables = [
            "dim_geography",
            "dim_time",
            "dim_source",
            "dim_road_segment",
            "fact_accident_event",
            "fact_accident_person",
            "mart_accident_summary",
            "mart_accident_hotspot",
            "indicator_catalog",
            "document_registry",
        ]
        rows = db_query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        existing = {r["table_name"] for r in rows}
        for t in expected_tables:
            assert t in existing, f"Table '{t}' missing from database"


class TestMockupData:
    """Test that mockup accident data was seeded correctly."""

    def test_dim_geography_has_data(self, db_query):
        rows = db_query("SELECT COUNT(*) AS cnt FROM dim_geography")
        assert rows[0]["cnt"] >= 20, "dim_geography should have ≥20 rows"

    def test_dim_road_segment_has_data(self, db_query):
        rows = db_query("SELECT COUNT(*) AS cnt FROM dim_road_segment")
        assert rows[0]["cnt"] >= 10, "dim_road_segment should have ≥10 rows"

    def test_dim_source_has_data(self, db_query):
        rows = db_query("SELECT COUNT(*) AS cnt FROM dim_source")
        assert rows[0]["cnt"] >= 4, "dim_source should have ≥4 rows"

    def test_fact_accident_event_has_data(self, db_query):
        rows = db_query("SELECT COUNT(*) AS cnt FROM fact_accident_event")
        assert rows[0]["cnt"] >= 200, "fact_accident_event should have ≥200 rows"

    def test_mart_accident_summary_has_data(self, db_query):
        rows = db_query("SELECT COUNT(*) AS cnt FROM mart_accident_summary")
        assert rows[0]["cnt"] >= 50, "mart_accident_summary should have ≥50 rows"

    def test_mart_accident_hotspot_has_data(self, db_query):
        rows = db_query("SELECT COUNT(*) AS cnt FROM mart_accident_hotspot")
        assert rows[0]["cnt"] >= 20, "mart_accident_hotspot should have ≥20 rows"

    def test_accident_events_have_valid_foreign_keys(self, db_query):
        """Every accident event should reference valid geography and road segment."""
        rows = db_query("""
            SELECT COUNT(*) AS cnt
            FROM fact_accident_event e
            LEFT JOIN dim_geography g ON e.geography_id = g.geography_id
            LEFT JOIN dim_road_segment r ON e.road_segment_id = r.road_segment_id
            WHERE g.geography_id IS NULL OR r.road_segment_id IS NULL
        """)
        assert rows[0]["cnt"] == 0, "All FKs should be valid"

    def test_accident_summary_covers_multiple_months(self, db_query):
        rows = db_query(
            "SELECT DISTINCT year_no, month_no FROM mart_accident_summary ORDER BY year_no, month_no"
        )
        assert len(rows) >= 12, "Summary should cover at least 12 year-month combos"

"""Tests for the Database Explorer API endpoints."""
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Task 1 — GET /api/db/tables
# ---------------------------------------------------------------------------

class TestListTables:

    def test_returns_200(self, client):
        resp = client.get("/api/db/tables")
        assert resp.status_code == 200

    def test_response_has_tables_key(self, client):
        data = client.get("/api/db/tables").json()
        assert "tables" in data

    def test_tables_is_list(self, client):
        data = client.get("/api/db/tables").json()
        assert isinstance(data["tables"], list)

    def test_tables_not_empty(self, client):
        data = client.get("/api/db/tables").json()
        assert len(data["tables"]) > 0

    def test_each_table_has_name_and_row_count(self, client):
        data = client.get("/api/db/tables").json()
        for t in data["tables"]:
            assert "name" in t
            assert "row_count" in t
            assert isinstance(t["row_count"], int)

    def test_known_table_is_present(self, client):
        data = client.get("/api/db/tables").json()
        names = [t["name"] for t in data["tables"]]
        assert "users" in names

    def test_no_pg_internal_tables(self, client):
        data = client.get("/api/db/tables").json()
        names = [t["name"] for t in data["tables"]]
        assert not any(n.startswith("pg_") for n in names)

    def test_sorted_alphabetically(self, client):
        data = client.get("/api/db/tables").json()
        names = [t["name"] for t in data["tables"]]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# Task 2 — GET /api/db/tables/{table}/columns
# ---------------------------------------------------------------------------

class TestListColumns:

    def test_known_table_returns_200(self, client):
        resp = client.get("/api/db/tables/users/columns")
        assert resp.status_code == 200

    def test_response_has_columns_key(self, client):
        data = client.get("/api/db/tables/users/columns").json()
        assert "columns" in data

    def test_columns_have_required_fields(self, client):
        data = client.get("/api/db/tables/users/columns").json()
        for col in data["columns"]:
            assert "name" in col
            assert "data_type" in col
            assert "nullable" in col

    def test_unknown_table_returns_404(self, client):
        resp = client.get("/api/db/tables/nonexistent_table_xyz/columns")
        assert resp.status_code == 404

    def test_injection_attempt_returns_404(self, client):
        resp = client.get("/api/db/tables/users; DROP TABLE users; --/columns")
        assert resp.status_code in (404, 422)

    def test_users_has_id_and_email(self, client):
        data = client.get("/api/db/tables/users/columns").json()
        names = [c["name"] for c in data["columns"]]
        assert "id" in names
        assert "email" in names


# ---------------------------------------------------------------------------
# Task 3 — GET /api/db/tables/{table}/rows
# ---------------------------------------------------------------------------

class TestListRows:

    def test_known_table_returns_200(self, client):
        resp = client.get("/api/db/tables/users/rows")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        data = client.get("/api/db/tables/users/rows").json()
        assert "rows" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_default_page_is_1(self, client):
        data = client.get("/api/db/tables/users/rows").json()
        assert data["page"] == 1

    def test_page_size_param_respected(self, client):
        data = client.get("/api/db/tables/users/rows?page_size=5").json()
        assert data["page_size"] == 5
        assert len(data["rows"]) <= 5

    def test_page_size_clamped_to_200(self, client):
        data = client.get("/api/db/tables/users/rows?page_size=9999").json()
        assert data["page_size"] == 200

    def test_unknown_table_returns_404(self, client):
        resp = client.get("/api/db/tables/no_such_table/rows")
        assert resp.status_code == 404

    def test_vector_table_does_not_crash(self, client):
        resp = client.get("/api/db/tables/document_embeddings/rows?page_size=2")
        assert resp.status_code == 200

    def test_filter_col_and_val(self, client):
        resp = client.get("/api/db/tables/users/rows?filter_col=role&filter_val=user")
        assert resp.status_code == 200
        data = resp.json()
        for row in data["rows"]:
            assert row.get("role") == "user"

    def test_filter_with_invalid_column_returns_400(self, client):
        resp = client.get("/api/db/tables/users/rows?filter_col=no_such_col&filter_val=x")
        assert resp.status_code == 400

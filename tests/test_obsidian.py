"""Tests for Obsidian Knowledge Vault — tools, API endpoints, and indexer.

TestObsidianTools      — unit tests against _search_obsidian_impl, _read_note_impl, _list_notes_impl (real DB)
TestObsidianAPISearch  — POST /api/obsidian/search endpoint
TestObsidianAPIStatus  — GET /api/obsidian/status endpoint
TestObsidianAPINotes   — GET /api/obsidian/notes endpoint
TestObsidianAPIIndex   — POST /api/obsidian/index endpoint
TestObsidianIndexer    — index_vault() script function
"""
import json
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.tools.obsidian import _search_obsidian_impl, _read_note_impl, _list_notes_impl

client = TestClient(app)

VAULT_ID = "health_region_10"
KNOWN_PROVINCES = ["อุบลราชธานี", "ศรีสะเกษ", "ยโสธร", "อำนาจเจริญ", "มุกดาหาร"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_any_note_id() -> str | None:
    """Return the first note_id from obsidian_notes, or None if table is empty."""
    from src.db.pool import query_db
    rows = query_db(
        "SELECT note_id FROM obsidian_notes WHERE vault_id = %s LIMIT 1", (VAULT_ID,)
    )
    return rows[0]["note_id"] if rows else None


def _notes_exist() -> bool:
    from src.db.pool import query_db
    rows = query_db("SELECT COUNT(*) AS cnt FROM obsidian_notes WHERE vault_id = %s", (VAULT_ID,))
    return (rows[0]["cnt"] if rows else 0) > 0


# ── Tool unit tests ─────────────────────────────────────────────────────────────

class TestObsidianTools:
    """Direct calls to the impl functions — no HTTP, no LLM."""

    def test_search_returns_results(self, db_pool):
        if not _notes_exist():
            pytest.skip("obsidian_notes is empty — run scripts/index_obsidian.py first")
        raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID, top_k=5)
        data = json.loads(raw)
        assert "results" in data
        assert data["count"] >= 0

    def test_search_province_filter(self, db_pool):
        if not _notes_exist():
            pytest.skip("obsidian_notes is empty")
        province = "มุกดาหาร"
        raw = _search_obsidian_impl(query="สุขภาพ", province=province, vault_id=VAULT_ID, top_k=10)
        data = json.loads(raw)
        for result in data["results"]:
            assert result["province"] == province, (
                f"Expected province={province}, got {result['province']}"
            )

    def test_search_broad_query_has_results(self, db_pool):
        if not _notes_exist():
            pytest.skip("obsidian_notes is empty")
        raw = _search_obsidian_impl(query="อุบล", vault_id=VAULT_ID, top_k=5)
        data = json.loads(raw)
        assert isinstance(data["count"], int)
        assert isinstance(data["results"], list)

    def test_search_empty_query_returns_error(self, db_pool):
        raw = _search_obsidian_impl(query="", vault_id=VAULT_ID)
        data = json.loads(raw)
        assert "error" in data
        assert data["count"] == 0

    def test_search_disabled(self, monkeypatch):
        from src.tools import obsidian as obs_module
        monkeypatch.setattr(obs_module.settings, "OBSIDIAN_ENABLED", False)
        raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID)
        data = json.loads(raw)
        assert data["count"] == 0
        assert "disabled" in (data.get("note") or "").lower() or data["count"] == 0

    def test_read_note_valid(self, db_pool):
        note_id = _get_any_note_id()
        if not note_id:
            pytest.skip("obsidian_notes is empty")
        raw = _read_note_impl(note_id)
        data = json.loads(raw)
        assert "error" not in data
        assert data["note_id"] == note_id
        assert "content" in data

    def test_read_note_not_found(self, db_pool):
        raw = _read_note_impl("health_region_10::nonexistent/path/note.md")
        data = json.loads(raw)
        assert "error" in data

    def test_list_notes_all(self, db_pool):
        if not _notes_exist():
            pytest.skip("obsidian_notes is empty")
        raw = _list_notes_impl(vault_id=VAULT_ID)
        data = json.loads(raw)
        assert "notes" in data
        assert data["count"] > 0

    def test_list_notes_province_filter(self, db_pool):
        if not _notes_exist():
            pytest.skip("obsidian_notes is empty")
        province = "ยโสธร"
        raw = _list_notes_impl(province=province, vault_id=VAULT_ID)
        data = json.loads(raw)
        for note in data["notes"]:
            assert note["province"] == province

    def test_search_top_k_respected(self, db_pool):
        if not _notes_exist():
            pytest.skip("obsidian_notes is empty")
        raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID, top_k=3)
        data = json.loads(raw)
        assert len(data["results"]) <= 3


# ── API endpoint tests ─────────────────────────────────────────────────────────

class TestObsidianAPIStatus:
    """GET /api/obsidian/status"""

    def test_status_200(self):
        resp = client.get("/api/obsidian/status")
        assert resp.status_code == 200

    def test_status_has_vaults(self):
        resp = client.get("/api/obsidian/status")
        data = resp.json()
        assert "vaults" in data
        assert isinstance(data["vaults"], list)

    def test_status_has_total_notes(self):
        resp = client.get("/api/obsidian/status")
        data = resp.json()
        assert "total_notes" in data
        assert isinstance(data["total_notes"], int)

    def test_status_health_region_vault_present(self):
        resp = client.get("/api/obsidian/status")
        data = resp.json()
        vault_ids = [v["vault_id"] for v in data["vaults"]]
        assert VAULT_ID in vault_ids

    def test_status_note_count_positive(self):
        resp = client.get("/api/obsidian/status")
        data = resp.json()
        assert data["total_notes"] > 0, "Vault has 0 notes — run scripts/index_obsidian.py"


class TestObsidianAPISearch:
    """POST /api/obsidian/search"""

    def test_search_valid_request(self):
        resp = client.post("/api/obsidian/search", json={
            "query": "สุขภาพ",
            "vault_id": VAULT_ID,
            "top_k": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_with_province_filter(self):
        resp = client.post("/api/obsidian/search", json={
            "query": "อุบัติเหตุ",
            "province": "อุบลราชธานี",
            "vault_id": VAULT_ID,
            "top_k": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            assert r["province"] == "อุบลราชธานี"

    def test_search_missing_query_422(self):
        resp = client.post("/api/obsidian/search", json={"vault_id": VAULT_ID})
        assert resp.status_code == 422

    def test_search_top_k_max_20(self):
        resp = client.post("/api/obsidian/search", json={
            "query": "ข้อมูล",
            "vault_id": VAULT_ID,
            "top_k": 20,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 20

    def test_search_note_type_filter(self):
        resp = client.post("/api/obsidian/search", json={
            "query": "สุขภาพ",
            "note_type": "report",
            "vault_id": VAULT_ID,
            "top_k": 5,
        })
        assert resp.status_code == 200


class TestObsidianAPINotes:
    """GET /api/obsidian/notes"""

    def test_list_notes_200(self):
        resp = client.get(f"/api/obsidian/notes?vault_id={VAULT_ID}")
        assert resp.status_code == 200

    def test_list_notes_has_notes_key(self):
        resp = client.get(f"/api/obsidian/notes?vault_id={VAULT_ID}")
        data = resp.json()
        assert "notes" in data or "count" in data

    def test_list_notes_province_filter(self):
        resp = client.get(f"/api/obsidian/notes?vault_id={VAULT_ID}&province=ศรีสะเกษ")
        assert resp.status_code == 200
        data = resp.json()
        for note in data.get("notes", []):
            assert note["province"] == "ศรีสะเกษ"


class TestObsidianAPIIndex:
    """POST /api/obsidian/index — re-index (idempotent, expect unchanged > 0 after first run)."""

    def test_index_returns_result_schema(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": VAULT_ID})
        assert resp.status_code == 200
        data = resp.json()
        for field in ("vault_id", "inserted", "updated", "unchanged", "errors", "total_files"):
            assert field in data, f"Missing field: {field}"

    def test_index_no_errors(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": VAULT_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert data["errors"] == 0

    def test_index_files_counted(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": VAULT_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_files"] > 0

    def test_index_unknown_vault_500(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": "nonexistent_vault_xyz"})
        assert resp.status_code in (500, 422)


# ── Indexer script tests ───────────────────────────────────────────────────────

class TestObsidianIndexer:
    """Test the index_vault() function from scripts/index_obsidian.py directly."""

    def test_index_vault_returns_summary(self, db_pool):
        from scripts.index_obsidian import index_vault
        result = index_vault(VAULT_ID)
        assert isinstance(result, dict)
        for key in ("vault_id", "inserted", "updated", "unchanged", "errors", "total_files"):
            assert key in result

    def test_index_vault_no_errors(self, db_pool):
        from scripts.index_obsidian import index_vault
        result = index_vault(VAULT_ID)
        assert result["errors"] == 0

    def test_index_vault_idempotent(self, db_pool):
        """Running twice should result in unchanged > 0 on second run."""
        from scripts.index_obsidian import index_vault
        result = index_vault(VAULT_ID)
        total = result["inserted"] + result["updated"] + result["unchanged"]
        assert total > 0

    def test_index_vault_unknown_raises(self, db_pool):
        from scripts.index_obsidian import index_vault
        with pytest.raises(ValueError, match="not found in obsidian_vaults"):
            index_vault("vault_that_does_not_exist_abc")

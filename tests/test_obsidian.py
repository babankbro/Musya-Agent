"""Tests for Obsidian Knowledge Vault — hybrid search edition.

Test Classes
────────────
TestChunkParser         Pure unit tests for split_chunks() — no DB, no fixtures.
TestWikilinkParser      Pure unit tests for parse_wikilinks() — no DB, no fixtures.
TestSearchTierSelection Unit tests for _chunks_indexed() detection logic (mocked DB).
TestHybridSearchInteg   Integration tests: chunk search + graph expansion (real DB).
TestFullNoteFallback    Integration test: fallback to full-note LIKE search.
TestObsidianTools       Existing tool impl tests (real DB, skip if empty).
TestObsidianAPISearch   POST /api/obsidian/search endpoint.
TestObsidianAPIStatus   GET /api/obsidian/status endpoint.
TestObsidianAPINotes    GET /api/obsidian/notes endpoint.
TestObsidianAPIIndex    POST /api/obsidian/index endpoint.
TestObsidianIndexer     index_vault() script: notes + chunks + links.
"""
import json
import sys
import os
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.main import app
from src.tools.obsidian import (
    _search_obsidian_impl,
    _read_note_impl,
    _list_notes_impl,
    _chunks_indexed,
    _search_chunks,
    _search_full_notes,
)
from scripts.index_obsidian import split_chunks, parse_wikilinks

client = TestClient(app)

VAULT_ID = "health_region_10"
KNOWN_PROVINCES = ["อุบลราชธานี", "ศรีสะเกษ", "ยโสธร", "อำนาจเจริญ", "มุกดาหาร"]


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _notes_exist() -> bool:
    from src.db.pool import query_db
    rows = query_db(
        "SELECT COUNT(*) AS cnt FROM obsidian_notes WHERE vault_id = %s", (VAULT_ID,)
    )
    return (rows[0]["cnt"] if rows else 0) > 0


def _chunks_exist() -> bool:
    from src.db.pool import query_db
    try:
        rows = query_db(
            """SELECT COUNT(*) AS cnt FROM obsidian_note_chunks c
               JOIN obsidian_notes n ON n.note_id = c.note_id
               WHERE n.vault_id = %s""",
            (VAULT_ID,),
        )
        return (rows[0]["cnt"] if rows else 0) > 0
    except Exception:
        return False  # table doesn't exist (migration 026 not applied)


def _links_exist() -> bool:
    from src.db.pool import query_db
    try:
        rows = query_db(
            """SELECT COUNT(*) AS cnt FROM obsidian_note_links lnk
               JOIN obsidian_notes n ON n.note_id = lnk.source_note_id
               WHERE n.vault_id = %s""",
            (VAULT_ID,),
        )
        return (rows[0]["cnt"] if rows else 0) > 0
    except Exception:
        return False  # table doesn't exist (migration 026 not applied)


def _migration_026_applied() -> bool:
    """Return True only if both hybrid tables exist in the DB."""
    from src.db.pool import query_db
    try:
        query_db("SELECT 1 FROM obsidian_note_chunks LIMIT 1", ())
        query_db("SELECT 1 FROM obsidian_note_links LIMIT 1", ())
        return True
    except Exception:
        return False


def _get_any_note_id() -> str | None:
    from src.db.pool import query_db
    rows = query_db(
        "SELECT note_id FROM obsidian_notes WHERE vault_id = %s LIMIT 1", (VAULT_ID,)
    )
    return rows[0]["note_id"] if rows else None


# ══════════════════════════════════════════════════════════════════════════════
# TestChunkParser — pure unit tests, no DB needed
# ══════════════════════════════════════════════════════════════════════════════

class TestChunkParser:
    """split_chunks() — deterministic parsing, no I/O."""

    FULL_NOTE = """\
# สรุปผลการดำเนินงาน คปสอ.เมืองมุกดาหาร

**สถานที่:** คปสอ.เมืองมุกดาหาร จังหวัด[[มุกดาหาร]]

## 📊 ภาพรวมผลการประเมิน

### 3. สุขภาพจิตและยาเสพติด
- อัตราการฆ่าตัวตายสำเร็จ: 11.03 ต่อแสนประชากร ⚠️

### 4. คนไทยห่างไกลโรค
- NCDs remission: 34.2%
- วัณโรค อัตราสำเร็จ 86.15%

## 🚀 แผนพัฒนาปี 2569
1. ปรับยาตาม Tele-Health
2. โครงการ CBTx"""

    def test_returns_list_of_tuples(self):
        chunks = split_chunks(self.FULL_NOTE)
        assert isinstance(chunks, list)
        assert all(isinstance(c, tuple) and len(c) == 3 for c in chunks)

    def test_intro_chunk_has_no_header(self):
        chunks = split_chunks(self.FULL_NOTE)
        assert chunks[0][0] == 0          # index 0
        assert chunks[0][1] is None       # no header

    def test_intro_chunk_contains_title_text(self):
        chunks = split_chunks(self.FULL_NOTE)
        assert "สรุปผลการดำเนินงาน" in chunks[0][2]

    def test_correct_number_of_chunks(self):
        # 1 intro + 2 ## sections = 3 chunks
        chunks = split_chunks(self.FULL_NOTE)
        assert len(chunks) == 3

    def test_h2_headers_extracted(self):
        chunks = split_chunks(self.FULL_NOTE)
        headers = [c[1] for c in chunks]
        assert any("ภาพรวม" in (h or "") for h in headers)
        assert any("แผนพัฒนา" in (h or "") for h in headers)

    def test_section_content_is_preserved(self):
        chunks = split_chunks(self.FULL_NOTE)
        # "อัตราการฆ่าตัวตาย" lives inside the ภาพรวม section (H2 index 1)
        section_texts = [c[2] for c in chunks]
        combined = " ".join(section_texts)
        assert "อัตราการฆ่าตัวตายสำเร็จ" in combined

    def test_kpi_in_section_chunk_not_just_intro(self):
        """The KPI must be in a non-intro chunk, not buried in file start."""
        chunks = split_chunks(self.FULL_NOTE)
        non_intro = [c for c in chunks if c[0] > 0]
        texts = " ".join(c[2] for c in non_intro)
        assert "11.03" in texts, "KPI number must appear in a named section chunk"

    def test_chunk_indices_are_sequential(self):
        chunks = split_chunks(self.FULL_NOTE)
        for expected_idx, (actual_idx, _, _) in enumerate(chunks):
            assert actual_idx == expected_idx

    def test_empty_body_returns_single_chunk(self):
        chunks = split_chunks("")
        assert len(chunks) == 1
        assert chunks[0][1] is None  # intro chunk

    def test_body_with_no_h2_is_single_intro_chunk(self):
        body = "# Title\n\nSome content\n### Sub\nmore"
        chunks = split_chunks(body)
        assert len(chunks) == 1
        assert chunks[0][0] == 0

    def test_emoji_in_header_handled(self):
        body = "intro\n\n## 📊 Section One\ncontent one\n\n## 🚀 Section Two\ncontent two"
        chunks = split_chunks(body)
        assert len(chunks) == 3
        assert "📊 Section One" in chunks[1][1]
        assert "🚀 Section Two" in chunks[2][1]

    def test_strips_hash_prefix_from_header(self):
        # Body must have intro text before ## so the H2 split regex fires.
        body = "intro text\n\n## My Header\nsome text"
        chunks = split_chunks(body)
        header = chunks[1][1]
        assert not header.startswith("#")
        assert "My Header" in header


# ══════════════════════════════════════════════════════════════════════════════
# TestWikilinkParser — pure unit tests, no DB needed
# ══════════════════════════════════════════════════════════════════════════════

class TestWikilinkParser:
    """parse_wikilinks() — deterministic extraction, no I/O."""

    def test_simple_wikilink(self):
        stems = parse_wikilinks("see [[มุกดาหาร]] for details")
        assert "มุกดาหาร" in stems

    def test_pipe_alias_uses_stem(self):
        stems = parse_wikilinks("[[สรุปผลการดำเนินงาน_คปสอ_2568|รายงาน คปสอ]]")
        assert "สรุปผลการดำเนินงาน_คปสอ_2568" in stems
        assert "รายงาน คปสอ" not in stems  # display text must be excluded

    def test_multiple_links_all_extracted(self):
        body = "สังกัด [[อ.เมืองมุกดาหาร]] จังหวัด [[มุกดาหาร]] ดู [[Report|รายงาน]]"
        stems = parse_wikilinks(body)
        assert "อ.เมืองมุกดาหาร" in stems
        assert "มุกดาหาร" in stems
        assert "Report" in stems

    def test_duplicates_removed(self):
        body = "[[Note A]] and [[Note A]] again"
        stems = parse_wikilinks(body)
        assert stems.count("Note A") == 1

    def test_empty_body_returns_empty_list(self):
        assert parse_wikilinks("") == []

    def test_no_links_returns_empty_list(self):
        assert parse_wikilinks("normal text, no wikilinks here") == []

    def test_whitespace_trimmed(self):
        stems = parse_wikilinks("[[ Note With Spaces ]]")
        assert "Note With Spaces" in stems

    def test_path_style_link(self):
        stems = parse_wikilinks("[[Folder/SubNote]]")
        assert "Folder/SubNote" in stems

    def test_real_vault_note_excerpt(self):
        """Matches the actual คปสอ note frontmatter wikilinks."""
        body = (
            "**สถานที่:** คปสอ.เมืองมุกดาหาร จังหวัด[[มุกดาหาร]] "
            "(สังกัด [[อ.เมืองมุกดาหาร]])"
        )
        stems = parse_wikilinks(body)
        assert "มุกดาหาร" in stems
        assert "อ.เมืองมุกดาหาร" in stems
        assert len(stems) == 2

    def test_province_moc_links(self):
        """Matches the actual province MOC note with many ULTRA_DETAILED links."""
        body = (
            "- [[ULTRA_DETAILED_ตรวจราชการ_รอบ1_2569|ปี 2569 (รอบที่ 1)]]\n"
            "- [[ULTRA_DETAILED_ตรวจราชการ_รอบ2_2568|ปี 2568 (รอบที่ 2)]]\n"
            "- [[MASTER_นโยบาย_พิทักษ์พงษ์_2569|นโยบายแม่บท]]"
        )
        stems = parse_wikilinks(body)
        assert "ULTRA_DETAILED_ตรวจราชการ_รอบ1_2569" in stems
        assert "ULTRA_DETAILED_ตรวจราชการ_รอบ2_2568" in stems
        assert "MASTER_นโยบาย_พิทักษ์พงษ์_2569" in stems
        assert len(stems) == 3


# ══════════════════════════════════════════════════════════════════════════════
# TestSearchTierSelection — unit tests with mocked DB
# ══════════════════════════════════════════════════════════════════════════════

class TestSearchTierSelection:
    """_chunks_indexed() and tier selection logic — no real DB needed."""

    def test_chunks_indexed_returns_false_when_empty(self):
        # _chunks_indexed imports query_db locally (from src.db.pool import query_db),
        # so we must patch it at the source module, not at src.tools.obsidian.
        with patch("src.db.pool.query_db", return_value=[]):
            assert not _chunks_indexed(VAULT_ID)

    def test_search_uses_fallback_when_chunks_empty(self):
        """When chunks are empty, tier in result should indicate fallback."""
        with patch("src.tools.obsidian._chunks_indexed", return_value=False), \
             patch("src.tools.obsidian._search_full_notes", return_value=[]) as mock_fn:
            raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID)
            data = json.loads(raw)
            mock_fn.assert_called_once()
            assert data["tier"] == "full_note_fallback"

    def test_search_uses_chunks_when_indexed(self):
        """When chunks exist, tier should be chunk+graph."""
        with patch("src.tools.obsidian._chunks_indexed", return_value=True), \
             patch("src.tools.obsidian._search_chunks", return_value=[]) as mock_fn:
            raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID)
            data = json.loads(raw)
            mock_fn.assert_called_once()
            assert data["tier"] == "chunk+graph"

    def test_empty_query_returns_error_before_tier_check(self):
        raw = _search_obsidian_impl(query="  ", vault_id=VAULT_ID)
        data = json.loads(raw)
        assert "error" in data
        assert data["count"] == 0

    def test_disabled_returns_note_before_tier_check(self):
        import src.tools.obsidian as obs_mod
        with patch.object(obs_mod.settings, "OBSIDIAN_ENABLED", False):
            raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID)
            data = json.loads(raw)
            assert data["count"] == 0
            assert "disabled" in (data.get("note") or "").lower()


# ══════════════════════════════════════════════════════════════════════════════
# TestHybridSearchInteg — real DB, requires indexed vault
# ══════════════════════════════════════════════════════════════════════════════

class TestHybridSearchInteg:
    """Integration tests that run against the actual PostgreSQL DB.

    All tests are skipped when either obsidian_notes or obsidian_note_chunks
    are empty (i.e., before index_vault() has been run with migration 026).
    """

    @pytest.fixture(autouse=True)
    def require_chunks(self, db_pool):
        if not _chunks_exist():
            pytest.skip(
                "obsidian_note_chunks is empty — run migration 026 then "
                "scripts/index_obsidian.py to enable hybrid search tests"
            )

    def test_search_returns_results(self):
        raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID, top_k=5)
        data = json.loads(raw)
        assert data["count"] >= 0
        assert "results" in data

    def test_tier_is_chunk_graph(self):
        raw = _search_obsidian_impl(query="NCD", vault_id=VAULT_ID, top_k=3)
        data = json.loads(raw)
        assert data.get("tier") == "chunk+graph"

    def test_scores_are_real_not_flat(self):
        """Scores must vary — not all 1.0 (flat score indicates fallback)."""
        raw = _search_obsidian_impl(query="อัตราฆ่าตัวตาย", vault_id=VAULT_ID, top_k=10)
        data = json.loads(raw)
        if not data["results"]:
            pytest.skip("No results for test query")
        scores = [r["score"] for r in data["results"] if not r.get("is_graph_neighbor")]
        assert len(scores) > 0
        # At least one score must be < 1.0 to confirm real similarity scoring
        assert any(s < 1.0 for s in scores), (
            f"All scores are 1.0 — suggests full-note fallback, not chunk scoring. "
            f"Scores: {scores}"
        )

    def test_matched_section_field_present(self):
        """Direct matches must have matched_section set (not None)."""
        raw = _search_obsidian_impl(
            query="อัตราฆ่าตัวตาย", vault_id=VAULT_ID, top_k=5
        )
        data = json.loads(raw)
        direct = [r for r in data["results"] if not r.get("is_graph_neighbor")]
        if not direct:
            pytest.skip("No direct matches")
        # At least one direct match should have a matched_section
        sections = [r.get("matched_section") for r in direct]
        assert any(s is not None for s in sections), (
            "No direct match has matched_section — chunk indexing may be incomplete"
        )

    def test_snippet_not_always_file_start(self):
        """Snippet should come from the matching section, not always the intro."""
        raw = _search_obsidian_impl(
            query="อัตราฆ่าตัวตาย", vault_id=VAULT_ID, top_k=5
        )
        data = json.loads(raw)
        if not data["results"]:
            pytest.skip("No results")
        # If chunk search works, at least one snippet should contain the query term
        snippets = [r["snippet"] for r in data["results"]]
        assert any("ฆ่าตัวตาย" in s for s in snippets), (
            "No snippet contains the query term — chunk search may not be working. "
            "Full-note fallback would return file intro instead."
        )

    def test_province_filter_respected(self):
        province = "มุกดาหาร"
        raw = _search_obsidian_impl(
            query="สุขภาพ", province=province, vault_id=VAULT_ID, top_k=10
        )
        data = json.loads(raw)
        for r in data["results"]:
            if not r.get("is_graph_neighbor"):
                # Graph neighbors are linked notes, not filtered by province;
                # only direct matches must respect the province filter.
                assert r["province"] == province, (
                    f"Province filter broken: expected {province}, got {r['province']}"
                )

    def test_top_k_respected(self):
        raw = _search_obsidian_impl(query="ข้อมูล", vault_id=VAULT_ID, top_k=3)
        data = json.loads(raw)
        assert len(data["results"]) <= 3

    def test_note_type_filter(self):
        raw = _search_obsidian_impl(
            query="สุขภาพ", note_type="report", vault_id=VAULT_ID, top_k=10
        )
        data = json.loads(raw)
        for r in data["results"]:
            if not r.get("is_graph_neighbor"):
                assert r["note_type"] == "report", (
                    f"note_type filter broken: {r['note_type']}"
                )

    def test_ncd_query_finds_kpsow_report(self):
        """Searching 'NCD remission' should surface a คปสอ report with real content."""
        raw = _search_obsidian_impl(
            query="NCD remission", vault_id=VAULT_ID, top_k=5
        )
        data = json.loads(raw)
        if not data["results"]:
            pytest.skip("No NCD results — vault may not have คปสอ reports indexed")
        # At least one result should be a report type
        types = [r["note_type"] for r in data["results"]]
        assert "report" in types, f"Expected report note_type, got: {types}"

    def test_result_has_all_required_fields(self):
        raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID, top_k=3)
        data = json.loads(raw)
        required = {
            "note_id", "vault_id", "title", "province", "district",
            "note_type", "tags", "snippet", "score",
            "matched_section", "is_graph_neighbor",
        }
        for r in data["results"]:
            missing = required - set(r.keys())
            assert not missing, f"Missing fields in result: {missing}"


# ══════════════════════════════════════════════════════════════════════════════
# TestGraphExpansion — tests specifically for wikilink neighbor surfacing
# ══════════════════════════════════════════════════════════════════════════════

class TestGraphExpansion:
    """Verify that wikilink-linked notes surface alongside direct matches."""

    @pytest.fixture(autouse=True)
    def require_links(self, db_pool):
        if not _links_exist():
            pytest.skip(
                "obsidian_note_links is empty — run scripts/index_obsidian.py "
                "with migration 026 to enable graph expansion tests"
            )

    def test_graph_neighbors_appear_in_results(self):
        """At least some results should be graph neighbors (is_graph_neighbor=True)."""
        # Search for something with rich interconnection (KPI report → district → province)
        raw = _search_obsidian_impl(
            query="อัตราฆ่าตัวตาย NCD มุกดาหาร", vault_id=VAULT_ID, top_k=10
        )
        data = json.loads(raw)
        neighbors = [r for r in data["results"] if r.get("is_graph_neighbor")]
        assert len(neighbors) > 0, (
            "No graph neighbors returned — wikilink expansion may not be working. "
            "Check that obsidian_note_links has rows and search_chunks runs the link CTE."
        )

    def test_graph_neighbors_have_lower_score_than_direct(self):
        """Neighbor discount score must be lower than direct match scores.

        pg_trgm similarity on long Thai chunks is inherently low (short query /
        long document dilutes the score).  The neighbor discount is computed
        dynamically as max_direct × 0.5, so it is always strictly below the
        best direct match.
        """
        raw = _search_obsidian_impl(
            query="NCD remission คปสอ", vault_id=VAULT_ID, top_k=10
        )
        data = json.loads(raw)
        direct_scores = [r["score"] for r in data["results"] if not r.get("is_graph_neighbor")]
        neighbor_scores = [r["score"] for r in data["results"] if r.get("is_graph_neighbor")]

        if not direct_scores or not neighbor_scores:
            pytest.skip("Need both direct and neighbor results for this test")

        max_direct = max(direct_scores)
        max_neighbor = max(neighbor_scores)

        # Dynamic discount guarantees neighbor ≤ max_direct × 0.5 ≤ max_direct
        assert max_direct >= max_neighbor, (
            f"Neighbor score ({max_neighbor:.4f}) exceeds best direct score "
            f"({max_direct:.4f}) — dynamic discount may be broken"
        )

    def test_graph_neighbors_no_duplicates(self):
        """No note_id should appear twice in results."""
        raw = _search_obsidian_impl(
            query="สุขภาพ", vault_id=VAULT_ID, top_k=10
        )
        data = json.loads(raw)
        note_ids = [r["note_id"] for r in data["results"]]
        assert len(note_ids) == len(set(note_ids)), (
            "Duplicate note_ids in results — deduplication in _search_chunks is broken"
        )

    def test_district_search_can_surface_kpsow_via_graph(self):
        """Searching for a district stub should surface linked คปสอ reports."""
        raw = _search_obsidian_impl(
            query="เมืองมุกดาหาร", vault_id=VAULT_ID, top_k=10
        )
        data = json.loads(raw)
        if not data["results"]:
            pytest.skip("No results for district query")
        # The district note links to the คปสอ report — it should be in results
        all_titles = [r.get("title", "") for r in data["results"]]
        all_note_ids = [r["note_id"] for r in data["results"]]
        # At least one result should reference เมืองมุกดาหาร
        has_mukdahan = any("มุกดาหาร" in t for t in all_titles)
        assert has_mukdahan, f"Expected มุกดาหาร in results, got: {all_titles}"


# ══════════════════════════════════════════════════════════════════════════════
# TestObsidianTools — existing tool-level tests (kept compatible)
# ══════════════════════════════════════════════════════════════════════════════

class TestObsidianTools:
    """Direct calls to impl functions — no HTTP, no LLM."""

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
            if not result.get("is_graph_neighbor"):
                assert result["province"] == province

    def test_search_empty_query_returns_error(self, db_pool):
        raw = _search_obsidian_impl(query="", vault_id=VAULT_ID)
        data = json.loads(raw)
        assert "error" in data
        assert data["count"] == 0

    def test_search_disabled(self, monkeypatch):
        import src.tools.obsidian as obs_mod
        monkeypatch.setattr(obs_mod.settings, "OBSIDIAN_ENABLED", False)
        raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID)
        data = json.loads(raw)
        assert data["count"] == 0

    def test_search_top_k_respected(self, db_pool):
        if not _notes_exist():
            pytest.skip("obsidian_notes is empty")
        raw = _search_obsidian_impl(query="สุขภาพ", vault_id=VAULT_ID, top_k=3)
        data = json.loads(raw)
        assert len(data["results"]) <= 3

    def test_search_broad_query(self, db_pool):
        if not _notes_exist():
            pytest.skip("obsidian_notes is empty")
        raw = _search_obsidian_impl(query="อุบล", vault_id=VAULT_ID, top_k=5)
        data = json.loads(raw)
        assert isinstance(data["count"], int)
        assert isinstance(data["results"], list)

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


# ══════════════════════════════════════════════════════════════════════════════
# TestObsidianAPISearch — HTTP endpoint tests
# ══════════════════════════════════════════════════════════════════════════════

class TestObsidianAPISearch:
    """POST /api/obsidian/search"""

    def test_search_200(self):
        resp = client.post("/api/obsidian/search", json={"query": "สุขภาพ", "vault_id": VAULT_ID})
        assert resp.status_code == 200

    def test_search_response_has_required_keys(self):
        resp = client.post("/api/obsidian/search", json={"query": "สุขภาพ", "vault_id": VAULT_ID})
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert "query" in data
        assert "tier" in data  # new field from hybrid

    def test_search_result_has_new_fields(self):
        resp = client.post(
            "/api/obsidian/search",
            json={"query": "NCD", "vault_id": VAULT_ID, "top_k": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            assert "matched_section" in r
            assert "score" in r
            assert "is_graph_neighbor" in r

    def test_search_with_province_filter(self):
        resp = client.post("/api/obsidian/search", json={
            "query": "สุขภาพ",
            "province": "อุบลราชธานี",
            "vault_id": VAULT_ID,
            "top_k": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            if not r.get("is_graph_neighbor"):
                assert r["province"] == "อุบลราชธานี"

    def test_search_missing_query_422(self):
        resp = client.post("/api/obsidian/search", json={"vault_id": VAULT_ID})
        assert resp.status_code == 422

    def test_search_top_k_max_20(self):
        resp = client.post("/api/obsidian/search", json={
            "query": "ข้อมูล", "vault_id": VAULT_ID, "top_k": 20
        })
        assert resp.status_code == 200
        assert len(resp.json()["results"]) <= 20

    def test_search_note_type_filter(self):
        resp = client.post("/api/obsidian/search", json={
            "query": "สุขภาพ", "note_type": "report", "vault_id": VAULT_ID, "top_k": 5
        })
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# TestObsidianAPIStatus
# ══════════════════════════════════════════════════════════════════════════════

class TestObsidianAPIStatus:
    """GET /api/obsidian/status"""

    def test_status_200(self):
        assert client.get("/api/obsidian/status").status_code == 200

    def test_status_has_vaults(self):
        data = client.get("/api/obsidian/status").json()
        assert "vaults" in data and isinstance(data["vaults"], list)

    def test_status_health_region_vault_present(self):
        data = client.get("/api/obsidian/status").json()
        vault_ids = [v["vault_id"] for v in data["vaults"]]
        assert VAULT_ID in vault_ids

    def test_status_total_notes_int(self):
        data = client.get("/api/obsidian/status").json()
        assert isinstance(data["total_notes"], int)


# ══════════════════════════════════════════════════════════════════════════════
# TestObsidianAPINotes
# ══════════════════════════════════════════════════════════════════════════════

class TestObsidianAPINotes:
    """GET /api/obsidian/notes"""

    def test_list_200(self):
        assert client.get(f"/api/obsidian/notes?vault_id={VAULT_ID}").status_code == 200

    def test_list_has_notes_key(self):
        data = client.get(f"/api/obsidian/notes?vault_id={VAULT_ID}").json()
        assert "notes" in data

    def test_list_province_filter(self):
        resp = client.get(f"/api/obsidian/notes?vault_id={VAULT_ID}&province=ศรีสะเกษ")
        assert resp.status_code == 200
        for note in resp.json().get("notes", []):
            assert note["province"] == "ศรีสะเกษ"


# ══════════════════════════════════════════════════════════════════════════════
# TestObsidianAPIIndex
# ══════════════════════════════════════════════════════════════════════════════

class TestObsidianAPIIndex:
    """POST /api/obsidian/index"""

    def test_index_200(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": VAULT_ID})
        assert resp.status_code == 200

    def test_index_result_has_required_fields(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": VAULT_ID})
        data = resp.json()
        for field in ("vault_id", "inserted", "updated", "unchanged",
                      "errors", "total_files", "chunks_written", "links_written"):
            assert field in data, f"Missing field: {field}"

    def test_index_no_errors(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": VAULT_ID})
        assert resp.json()["errors"] == 0

    def test_index_files_counted(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": VAULT_ID})
        assert resp.json()["total_files"] > 0

    def test_index_chunks_written(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": VAULT_ID})
        data = resp.json()
        # On second run (idempotent), chunks_written may be 0 (unchanged notes skip reindex)
        # But total_files > 0 means the vault was scanned
        assert isinstance(data["chunks_written"], int)

    def test_index_unknown_vault_error(self):
        resp = client.post("/api/obsidian/index", json={"vault_id": "nonexistent_vault_xyz"})
        assert resp.status_code in (500, 422)


# ══════════════════════════════════════════════════════════════════════════════
# TestObsidianIndexer — script-level tests
# ══════════════════════════════════════════════════════════════════════════════

class TestObsidianIndexer:
    """index_vault() from scripts/index_obsidian.py — real DB."""

    @pytest.fixture(autouse=True)
    def require_migration_026(self, db_pool):
        """Skip all indexer tests if migration 026 tables don't exist yet."""
        if not _migration_026_applied():
            pytest.skip(
                "Migration 026 not applied — run database/026_obsidian_hybrid.sql "
                "before running indexer tests"
            )

    def test_returns_summary_dict(self, db_pool):
        from scripts.index_obsidian import index_vault
        result = index_vault(VAULT_ID)
        assert isinstance(result, dict)

    def test_summary_has_required_keys(self, db_pool):
        from scripts.index_obsidian import index_vault
        result = index_vault(VAULT_ID)
        for key in ("vault_id", "inserted", "updated", "unchanged",
                    "errors", "total_files", "chunks_written", "links_written"):
            assert key in result, f"Missing key: {key}"

    def test_no_errors(self, db_pool):
        from scripts.index_obsidian import index_vault
        result = index_vault(VAULT_ID)
        assert result["errors"] == 0

    def test_total_files_positive(self, db_pool):
        from scripts.index_obsidian import index_vault
        result = index_vault(VAULT_ID)
        assert result["total_files"] > 0

    def test_chunks_written_positive_on_first_run(self, db_pool):
        """chunks_written > 0 after the vault has been freshly indexed."""
        from src.db.pool import execute_db
        from scripts.index_obsidian import index_vault
        # Force re-index by clearing chunks (so they're not skipped as unchanged)
        execute_db(
            "DELETE FROM obsidian_note_chunks WHERE note_id IN "
            "(SELECT note_id FROM obsidian_notes WHERE vault_id = %s)",
            (VAULT_ID,),
        )
        result = index_vault(VAULT_ID)
        assert result["chunks_written"] > 0, (
            "No chunks were written — split_chunks() or chunk INSERT may be broken"
        )

    def test_chunks_in_db_after_index(self, db_pool):
        from scripts.index_obsidian import index_vault
        from src.db.pool import query_db
        index_vault(VAULT_ID)
        rows = query_db(
            "SELECT COUNT(*) AS cnt FROM obsidian_note_chunks c "
            "JOIN obsidian_notes n ON c.note_id = n.note_id "
            "WHERE n.vault_id = %s",
            (VAULT_ID,),
        )
        count = rows[0]["cnt"] if rows else 0
        assert count > 0, "obsidian_note_chunks is empty after indexing"

    def test_links_written_positive(self, db_pool):
        """links_written > 0 when vault has [[wikilinks]]."""
        from src.db.pool import execute_db
        from scripts.index_obsidian import index_vault
        execute_db(
            "DELETE FROM obsidian_note_links WHERE source_note_id IN "
            "(SELECT note_id FROM obsidian_notes WHERE vault_id = %s)",
            (VAULT_ID,),
        )
        result = index_vault(VAULT_ID)
        assert result["links_written"] > 0, (
            "No wikilink edges written — parse_wikilinks() or link INSERT may be broken"
        )

    def test_links_in_db_after_index(self, db_pool):
        from scripts.index_obsidian import index_vault
        from src.db.pool import query_db
        index_vault(VAULT_ID)
        rows = query_db(
            "SELECT COUNT(*) AS cnt FROM obsidian_note_links lnk "
            "JOIN obsidian_notes n ON lnk.source_note_id = n.note_id "
            "WHERE n.vault_id = %s",
            (VAULT_ID,),
        )
        count = rows[0]["cnt"] if rows else 0
        assert count > 0, "obsidian_note_links is empty after indexing"

    def test_idempotent_second_run(self, db_pool):
        """Running twice: second run should have unchanged > 0, errors == 0."""
        from scripts.index_obsidian import index_vault
        index_vault(VAULT_ID)          # first run
        result2 = index_vault(VAULT_ID)  # second run
        assert result2["errors"] == 0
        assert result2["inserted"] + result2["updated"] + result2["unchanged"] > 0

    def test_chunk_content_not_empty(self, db_pool):
        """Every chunk in the DB must have non-empty content."""
        from scripts.index_obsidian import index_vault
        from src.db.pool import query_db
        index_vault(VAULT_ID)
        rows = query_db(
            "SELECT COUNT(*) AS cnt FROM obsidian_note_chunks "
            "WHERE TRIM(chunk_content) = ''",
            (),
        )
        empty_count = rows[0]["cnt"] if rows else 0
        assert empty_count == 0, (
            f"{empty_count} chunks have empty content — "
            "the empty-chunk guard in index_vault() may be broken"
        )

    def test_all_links_have_valid_targets(self, db_pool):
        """Every target_note_id in note_links must exist in obsidian_notes."""
        from scripts.index_obsidian import index_vault
        from src.db.pool import query_db
        index_vault(VAULT_ID)
        rows = query_db(
            """
            SELECT COUNT(*) AS cnt
            FROM obsidian_note_links lnk
            LEFT JOIN obsidian_notes n ON n.note_id = lnk.target_note_id
            WHERE n.note_id IS NULL
            """,
            (),
        )
        dangling = rows[0]["cnt"] if rows else 0
        assert dangling == 0, (
            f"{dangling} note_links have dangling target_note_id — "
            "FK constraint should have caught these"
        )

    def test_unknown_vault_raises(self, db_pool):
        from scripts.index_obsidian import index_vault
        with pytest.raises(ValueError, match="not found in obsidian_vaults"):
            index_vault("vault_that_does_not_exist_abc")

    def test_vault_note_count_updated(self, db_pool):
        """obsidian_vaults.note_count must be updated after indexing."""
        from scripts.index_obsidian import index_vault
        from src.db.pool import query_db
        index_vault(VAULT_ID)
        rows = query_db(
            "SELECT note_count FROM obsidian_vaults WHERE vault_id = %s",
            (VAULT_ID,),
        )
        count = rows[0]["note_count"] if rows else 0
        assert count > 0, "vault note_count not updated after index_vault()"

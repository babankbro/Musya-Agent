"""Test cases for Citation & Evidence Agent — schemas, parsing, tools, RAG integration."""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from src.schemas.evidence import (
    EvidenceItem, Claim, ClaimEvidenceLink, EnhancedCitation,
    CoverageReport, EvidenceContext,
)
from src.agents.citation_evidence import parse_evidence_context


# ═══════════════════════════════════════════════════════════════════
# 1. Schema Tests
# ═══════════════════════════════════════════════════════════════════

class TestEvidenceItem:
    """Test EvidenceItem schema creation and validation."""

    def test_create_document_evidence(self):
        ev = EvidenceItem(
            evidence_id="EV-001",
            evidence_type="document",
            source_ref="road_safety_2025.pdf",
            title="นโยบายความปลอดภัยทางถนน 2025",
            page_ref="12",
            section_label="Section 3.2",
            trust_level="high",
            text_snippet="จังหวัดเชียงใหม่มีอัตราอุบัติเหตุสูงขึ้น 15%",
            original_url="minio://uploads/road_safety_2025.pdf",
            open_url="/api/documents/open/42?page=12",
        )
        assert ev.evidence_id == "EV-001"
        assert ev.evidence_type == "document"
        assert ev.trust_level == "high"
        assert ev.page_ref == "12"

    def test_create_database_evidence(self):
        ev = EvidenceItem(
            evidence_id="EV-002",
            evidence_type="database",
            source_ref="mart_province_year",
            title="สรุปรายจังหวัดรายปี",
            query_signature="abc123",
            query_params={"province": "เชียงใหม่", "year": 2025},
            trust_level="high",
            text_snippet="accident_count: 920, death_count: 28",
            original_url="postgresql://mart_province_year",
            open_url="/api/evidence/EV-002/query",
        )
        assert ev.evidence_type == "database"
        assert ev.query_params["province"] == "เชียงใหม่"

    def test_create_api_evidence(self):
        ev = EvidenceItem(
            evidence_id="EV-003",
            evidence_type="api",
            source_ref="open-meteo",
            title="Weather Forecast",
            trust_level="low",
        )
        assert ev.evidence_type == "api"
        assert ev.trust_level == "low"

    def test_defaults(self):
        ev = EvidenceItem(evidence_id="EV-X", evidence_type="document", source_ref="test.pdf")
        assert ev.topic == "general"
        assert ev.trust_level == "medium"
        assert ev.chunk_index == -1
        assert ev.text_snippet == ""


class TestClaim:
    """Test Claim schema."""

    def test_create_statistic_claim(self):
        cl = Claim(
            claim_id="CL-001",
            claim_text="จังหวัดเชียงใหม่มีอุบัติเหตุ 920 ครั้ง",
            claim_type="statistic",
            section_id="sec-situation",
        )
        assert cl.claim_id == "CL-001"
        assert cl.claim_type == "statistic"

    def test_create_trend_claim(self):
        cl = Claim(
            claim_id="CL-002",
            claim_text="อุบัติเหตุมีแนวโน้มลดลง",
            claim_type="trend",
        )
        assert cl.claim_type == "trend"
        assert cl.object_type == "text"  # default

    def test_defaults(self):
        cl = Claim(claim_id="CL-X", claim_text="test")
        assert cl.claim_type == "general_finding"
        assert cl.object_type == "text"


class TestClaimEvidenceLink:
    """Test ClaimEvidenceLink schema."""

    def test_create_supported_link(self):
        link = ClaimEvidenceLink(
            claim_id="CL-001",
            evidence_id="EV-001",
            support_level="supported",
            evidence_strength="strong",
        )
        assert link.support_level == "supported"
        assert link.evidence_strength == "strong"

    def test_create_insufficient_link(self):
        link = ClaimEvidenceLink(
            claim_id="CL-002",
            evidence_id="EV-003",
            support_level="insufficient",
            evidence_strength="weak",
            confidence_note="ข้อมูลจาก API ภายนอกที่ไม่ได้ verify",
        )
        assert link.support_level == "insufficient"


class TestEnhancedCitation:
    """Test EnhancedCitation schema."""

    def test_create_document_citation(self):
        cit = EnhancedCitation(
            citation_code="C-001",
            evidence_id="EV-001",
            source_type="document",
            source_ref="road_safety_2025.pdf",
            citation_text="นโยบายความปลอดภัยทางถนน 2025, ส่วนที่ 3.2, หน้า 12",
            bibliography_text="นโยบายความปลอดภัยทางถนน 2025. กรมทางหลวง. หน้า 12.",
            open_url="/api/documents/open/42?page=12",
            trust_level="high",
        )
        assert cit.citation_code == "C-001"
        assert "หน้า 12" in cit.citation_text
        assert cit.open_url.startswith("/api/documents/open/")

    def test_create_database_citation(self):
        cit = EnhancedCitation(
            citation_code="C-002",
            evidence_id="EV-002",
            source_type="database",
            source_ref="mart_province_year",
            citation_text="ฐานข้อมูลสรุปรายจังหวัดรายปี, 2025",
            bibliography_text="ฐานข้อมูลสรุปรายจังหวัดรายปี (mart_province_year). Musya Agent.",
            open_url="/api/evidence/EV-002/query",
        )
        assert cit.source_type == "database"


class TestCoverageReport:
    """Test CoverageReport schema."""

    def test_full_coverage(self):
        report = CoverageReport(
            total_claims=5,
            supported_claims=5,
            coverage_score=1.0,
        )
        assert report.coverage_score == 1.0
        assert report.unsupported_claims == 0

    def test_partial_coverage_with_flags(self):
        report = CoverageReport(
            total_claims=10,
            supported_claims=7,
            partially_supported=2,
            unsupported_claims=1,
            coverage_score=0.70,
            flags=[{"rule": "CV-01", "claim_id": "CL-008", "message": "ไม่มีหลักฐาน"}],
        )
        assert report.coverage_score == 0.70
        assert len(report.flags) == 1


class TestEvidenceContext:
    """Test EvidenceContext composite schema."""

    def test_empty_context(self):
        ctx = EvidenceContext()
        assert ctx.evidence_items == []
        assert ctx.citations == []
        assert ctx.coverage_report.total_claims == 0

    def test_populated_context(self):
        ctx = EvidenceContext(
            evidence_items=[
                EvidenceItem(evidence_id="EV-001", evidence_type="document", source_ref="test.pdf"),
            ],
            claims=[
                Claim(claim_id="CL-001", claim_text="test claim"),
            ],
            citations=[
                EnhancedCitation(
                    citation_code="C-001", evidence_id="EV-001",
                    source_type="document", source_ref="test.pdf",
                    citation_text="test", bibliography_text="test bib",
                ),
            ],
            coverage_report=CoverageReport(total_claims=1, supported_claims=1, coverage_score=1.0),
        )
        assert len(ctx.evidence_items) == 1
        assert len(ctx.citations) == 1
        assert ctx.coverage_report.coverage_score == 1.0


# ═══════════════════════════════════════════════════════════════════
# 2. parse_evidence_context Tests
# ═══════════════════════════════════════════════════════════════════

class TestParseEvidenceContext:
    """Test parsing the Citation Agent's JSON output."""

    SAMPLE_OUTPUT = json.dumps({
        "evidence_items": [
            {
                "evidence_id": "EV-001",
                "evidence_type": "document",
                "source_ref": "road_safety.pdf",
                "title": "Road Safety Policy",
                "page_ref": "12",
                "section_label": "Section 3",
                "trust_level": "high",
                "text_snippet": "Accident stats...",
                "original_url": "minio://uploads/road_safety.pdf",
                "open_url": "/api/documents/open/1?page=12",
            },
            {
                "evidence_id": "EV-002",
                "evidence_type": "database",
                "source_ref": "mart_province_year",
                "title": "Province Year Summary",
                "trust_level": "high",
                "query_signature": "sha256abc",
                "query_params": {"province": "เชียงใหม่"},
                "text_snippet": "920 accidents",
            },
        ],
        "claims": [
            {
                "claim_id": "CL-001",
                "claim_text": "เชียงใหม่มีอุบัติเหตุ 920 ครั้ง",
                "claim_type": "statistic",
                "evidence_ids": ["EV-001", "EV-002"],
                "support_level": "supported",
                "evidence_strength": "strong",
            },
            {
                "claim_id": "CL-002",
                "claim_text": "แนวโน้มลดลง 15%",
                "claim_type": "trend",
                "evidence_ids": ["EV-001"],
                "support_level": "supported",
                "evidence_strength": "moderate",
            },
        ],
        "citations": [
            {
                "citation_code": "C-001",
                "evidence_id": "EV-001",
                "source_type": "document",
                "source_ref": "road_safety.pdf",
                "citation_text": "Road Safety Policy, Section 3, p.12",
                "bibliography_text": "Road Safety Policy. Section 3, p.12.",
                "open_url": "/api/documents/open/1?page=12",
                "trust_level": "high",
            },
            {
                "citation_code": "C-002",
                "evidence_id": "EV-002",
                "source_type": "database",
                "source_ref": "mart_province_year",
                "citation_text": "ฐานข้อมูลสรุปรายจังหวัดรายปี",
                "bibliography_text": "mart_province_year. Musya Agent.",
                "open_url": "/api/evidence/EV-002/query",
                "trust_level": "high",
            },
        ],
        "coverage": {
            "total_claims": 2,
            "supported": 2,
            "unsupported": 0,
            "coverage_score": 1.0,
            "flags": [],
        },
    }, ensure_ascii=False)

    def test_parse_full_output(self):
        ctx = parse_evidence_context(self.SAMPLE_OUTPUT)
        assert len(ctx.evidence_items) == 2
        assert ctx.evidence_items[0].evidence_id == "EV-001"
        assert ctx.evidence_items[1].evidence_type == "database"

    def test_parse_claims(self):
        ctx = parse_evidence_context(self.SAMPLE_OUTPUT)
        assert len(ctx.claims) == 2
        assert ctx.claims[0].claim_type == "statistic"
        assert ctx.claims[1].claim_type == "trend"

    def test_parse_claim_evidence_links(self):
        ctx = parse_evidence_context(self.SAMPLE_OUTPUT)
        assert len(ctx.claim_links) == 3  # CL-001→EV-001, CL-001→EV-002, CL-002→EV-001

    def test_parse_citations(self):
        ctx = parse_evidence_context(self.SAMPLE_OUTPUT)
        assert len(ctx.citations) == 2
        assert ctx.citations[0].citation_code == "C-001"
        assert ctx.citations[1].source_type == "database"
        assert ctx.citations[0].open_url.startswith("/api/documents/open/")

    def test_parse_coverage(self):
        ctx = parse_evidence_context(self.SAMPLE_OUTPUT)
        assert ctx.coverage_report.total_claims == 2
        assert ctx.coverage_report.supported_claims == 2
        assert ctx.coverage_report.coverage_score == 1.0

    def test_parse_fenced_json(self):
        fenced = "Here is the result:\n```json\n" + self.SAMPLE_OUTPUT + "\n```\nDone."
        ctx = parse_evidence_context(fenced)
        assert len(ctx.evidence_items) == 2
        assert len(ctx.citations) == 2

    def test_parse_invalid_json(self):
        ctx = parse_evidence_context("this is not json at all")
        assert len(ctx.evidence_items) == 0
        assert len(ctx.citations) == 0

    def test_parse_empty_string(self):
        ctx = parse_evidence_context("")
        assert len(ctx.evidence_items) == 0

    def test_parse_partial_output(self):
        partial = json.dumps({
            "evidence_items": [
                {"evidence_id": "EV-001", "evidence_type": "document", "source_ref": "test.pdf"},
            ],
            "claims": [],
            "citations": [],
        })
        ctx = parse_evidence_context(partial)
        assert len(ctx.evidence_items) == 1
        assert len(ctx.citations) == 0


# ═══════════════════════════════════════════════════════════════════
# 3. search_documents Tool — Structured Output Tests
# ═══════════════════════════════════════════════════════════════════

class TestSearchDocumentsTool:
    """Test that search_documents returns structured JSON evidence items."""

    @patch("src.tools.common.doc_search")
    def test_returns_json_array(self, mock_search):
        mock_search.return_value = [
            {
                "text": "อุบัติเหตุทางถนนเป็นสาเหตุการเสียชีวิตอันดับต้นๆ...",
                "distance": 0.23,
                "id": "abc123",
                "metadata": {
                    "source": "folder1/road_safety_2025.pdf",
                    "chunk_index": 3,
                    "total_chunks": 20,
                    "title": "road safety 2025",
                    "page_ref": "12",
                    "section_label": "Section 3.2",
                    "total_pages": 45,
                },
            },
        ]

        from src.tools.common import search_documents
        result = search_documents.run(topic="accident", keywords="อุบัติเหตุเชียงใหม่", n_results=5)
        items = json.loads(result)

        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]["evidence_type"] == "document"
        assert items[0]["source_ref"] == "folder1/road_safety_2025.pdf"
        assert items[0]["page_ref"] == "12"
        assert items[0]["section_label"] == "Section 3.2"
        assert items[0]["chunk_id"] == "abc123"
        assert items[0]["trust_level"] == "high"
        assert items[0]["original_url"].startswith("minio://")

    @patch("src.tools.common.doc_search")
    def test_returns_empty_array_when_no_results(self, mock_search):
        mock_search.return_value = []

        from src.tools.common import search_documents
        result = search_documents.run(topic="accident", keywords="ไม่มีข้อมูล", n_results=5)
        items = json.loads(result)

        assert isinstance(items, list)
        assert len(items) == 0

    @patch("src.tools.common.doc_search")
    def test_handles_missing_metadata_gracefully(self, mock_search):
        mock_search.return_value = [
            {
                "text": "Some text content...",
                "distance": 0.5,
                "metadata": {"source": "simple.txt"},
            },
        ]

        from src.tools.common import search_documents
        result = search_documents.run(topic="all", keywords="test", n_results=3)
        items = json.loads(result)

        assert len(items) == 1
        assert items[0]["source_ref"] == "simple.txt"
        assert items[0]["page_ref"] == ""  # no page_ref for txt files
        assert items[0]["chunk_index"] == -1  # default when missing


# ═══════════════════════════════════════════════════════════════════
# 4. Document RAG Ingestion Metadata Tests
# ═══════════════════════════════════════════════════════════════════

class TestDocumentRagMetadata:
    """Test that document ingestion enriches metadata for citation."""

    def test_extract_title_from_name(self):
        from src.rag.document_rag import _extract_title_from_name
        assert _extract_title_from_name("road_safety_2025.pdf") == "road safety 2025"
        assert _extract_title_from_name("folder1/report-final.docx") == "report final"
        assert _extract_title_from_name("simple") == "simple"

    def test_detect_heading_thai(self):
        from src.rag.document_rag import _detect_heading
        assert _detect_heading("บทที่ 3 สถานการณ์อุบัติเหตุ\nเนื้อหา...") != ""
        assert _detect_heading("3.2 ผลการวิเคราะห์\nรายละเอียด...") != ""

    def test_detect_heading_english(self):
        from src.rag.document_rag import _detect_heading
        assert _detect_heading("Chapter 3: Road Safety\nContent...") != ""
        assert _detect_heading("3.2 Analysis Results\nDetails...") != ""

    def test_detect_heading_empty(self):
        from src.rag.document_rag import _detect_heading
        assert _detect_heading("") == ""
        assert _detect_heading("   ") == ""

    def test_detect_heading_long_line_not_heading(self):
        from src.rag.document_rag import _detect_heading
        long_text = "a" * 150 + "\nmore text"
        assert _detect_heading(long_text) == ""

    def test_extract_pages_from_pdf_mock(self):
        """Test that extract_pages_from_pdf returns per-page data."""
        from src.rag.document_rag import extract_pages_from_pdf
        # Create a minimal valid PDF in memory
        import fitz
        doc = fitz.open()
        page1 = doc.new_page()
        page1.insert_text((72, 72), "Page 1 content")
        page2 = doc.new_page()
        page2.insert_text((72, 72), "Page 2 content")
        pdf_bytes = doc.tobytes()
        doc.close()

        pages = extract_pages_from_pdf(pdf_bytes)
        assert len(pages) == 2
        assert pages[0]["page"] == 1
        assert pages[1]["page"] == 2
        assert "Page 1" in pages[0]["text"]


# ═══════════════════════════════════════════════════════════════════
# 5. Evidence Router API Tests
# ═══════════════════════════════════════════════════════════════════

class TestEvidenceRouterAPI:
    """Test evidence API endpoints using FastAPI test client."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.main import app
        return TestClient(app)

    @patch("src.routers.evidence.query_db")
    def test_get_evidence_found(self, mock_db, client):
        mock_db.return_value = [{
            "evidence_id": "EV-001",
            "evidence_type": "document",
            "source_ref": "road_safety.pdf",
            "trust_level": "high",
        }]
        resp = client.get("/api/evidence/EV-001")
        assert resp.status_code == 200
        assert resp.json()["evidence_id"] == "EV-001"

    @patch("src.routers.evidence.query_db")
    def test_get_evidence_not_found(self, mock_db, client):
        mock_db.return_value = []
        resp = client.get("/api/evidence/EV-999")
        assert resp.status_code == 404

    @patch("src.routers.evidence.query_db")
    def test_get_evidence_query_database_type(self, mock_db, client):
        mock_db.return_value = [{
            "evidence_id": "EV-002",
            "evidence_type": "database",
            "source_ref": "mart_province_year",
            "query_signature": "abc",
            "query_params": {"province": "เชียงใหม่"},
            "text_snippet": "920 accidents",
        }]
        resp = client.get("/api/evidence/EV-002/query")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_type"] == "database"
        assert data["source_ref"] == "mart_province_year"

    @patch("src.routers.evidence.query_db")
    def test_get_evidence_query_non_database_type(self, mock_db, client):
        mock_db.return_value = [{
            "evidence_id": "EV-001",
            "evidence_type": "document",
            "source_ref": "test.pdf",
            "query_signature": "",
            "query_params": {},
            "text_snippet": "text...",
        }]
        resp = client.get("/api/evidence/EV-001/query")
        assert resp.status_code == 200
        assert "ไม่ใช่ประเภท database" in resp.json()["message"]

    @patch("src.routers.evidence.query_db")
    def test_get_session_evidence(self, mock_db, client):
        mock_db.return_value = [
            {"evidence_id": "EV-001", "source_ref": "a.pdf"},
            {"evidence_id": "EV-002", "source_ref": "b.pdf"},
        ]
        resp = client.get("/api/evidence/session/test-session-123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_count"] == 2

    @patch("src.routers.evidence.query_db")
    def test_get_session_coverage(self, mock_db, client):
        mock_db.return_value = [
            {"claim_id": "CL-001", "claim_text": "test", "claim_type": "statistic",
             "support_level": "supported", "evidence_strength": "strong", "citation_code": "C-001"},
            {"claim_id": "CL-002", "claim_text": "test2", "claim_type": "trend",
             "support_level": "partially_supported", "evidence_strength": "moderate", "citation_code": "C-002"},
        ]
        resp = client.get("/api/evidence/session/test-session/coverage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_claims"] == 2
        assert data["supported"] == 1
        assert data["partially_supported"] == 1


# ═══════════════════════════════════════════════════════════════════
# 6. Integration: RAG + MinIO + Evidence Pipeline
# ═══════════════════════════════════════════════════════════════════

class TestRAGMinIOEvidenceIntegration:
    """Integration tests verifying the RAG → Evidence pipeline with MinIO documents."""

    @patch("src.rag.document_rag.download_document")
    @patch("src.rag.document_rag.list_documents")
    @patch("src.rag.document_rag.add_documents")
    def test_ingestion_enriches_metadata(self, mock_add, mock_list, mock_download):
        """Verify that document ingestion from MinIO adds page_ref, title, section_label."""
        mock_list.return_value = [{"name": "policy/road_safety_2025.txt", "size": 100}]
        mock_download.return_value = b"Chapter 1: Introduction\nThis is the intro content.\n\nChapter 2: Analysis\nDetailed analysis here."

        from src.rag.document_rag import ingest_all_documents
        count = ingest_all_documents(prefix="policy/")

        assert count > 0
        # Verify add_documents was called with enriched metadata
        call_args = mock_add.call_args
        metadatas = call_args.kwargs.get("metadatas") or call_args[1].get("metadatas") if call_args[1] else call_args.kwargs.get("metadatas")
        if metadatas is None and len(call_args.args) >= 3:
            metadatas = call_args.args[2]

        assert metadatas is not None
        assert len(metadatas) > 0
        first_meta = metadatas[0]
        assert "title" in first_meta
        assert "page_ref" in first_meta
        assert "section_label" in first_meta
        assert first_meta["title"] == "road safety 2025"

    @patch("src.rag.document_rag.download_document")
    @patch("src.rag.document_rag.list_documents")
    @patch("src.rag.document_rag.add_documents")
    def test_pdf_ingestion_extracts_page_refs(self, mock_add, mock_list, mock_download):
        """Verify PDF ingestion assigns page_ref from PyMuPDF page mapping."""
        import fitz
        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((72, 72), "Page 1: Introduction to road safety policy in Thailand.")
        p2 = doc.new_page()
        p2.insert_text((72, 72), "Page 2: Statistical analysis of accident data for 2025.")
        pdf_bytes = doc.tobytes()
        doc.close()

        mock_list.return_value = [{"name": "reports/analysis.pdf", "size": len(pdf_bytes)}]
        mock_download.return_value = pdf_bytes

        from src.rag.document_rag import ingest_all_documents
        count = ingest_all_documents(prefix="reports/")

        assert count > 0
        call_args = mock_add.call_args
        metadatas = call_args.kwargs.get("metadatas") or (call_args.args[2] if len(call_args.args) >= 3 else None)
        if metadatas is None:
            # Try positional
            metadatas = call_args[1].get("metadatas") if isinstance(call_args[1], dict) else None

        assert metadatas is not None
        # At least one chunk should have a page_ref
        page_refs = [m.get("page_ref", "") for m in metadatas]
        assert any(p != "" for p in page_refs), f"No page_ref found: {page_refs}"

    @patch("src.tools.common.doc_search")
    def test_search_returns_evidence_with_open_url(self, mock_search):
        """Verify search results include open_url for MinIO documents."""
        mock_search.return_value = [{
            "text": "Content about accidents...",
            "distance": 0.15,
            "id": "chunk123",
            "metadata": {
                "source": "policy/road_safety.pdf",
                "chunk_index": 5,
                "total_chunks": 30,
                "title": "road safety",
                "page_ref": "7",
                "section_label": "3.1 สถิติอุบัติเหตุ",
            },
        }]

        from src.tools.common import search_documents
        result_json = search_documents.run(topic="accident", keywords="อุบัติเหตุ", n_results=1)
        items = json.loads(result_json)

        assert len(items) == 1
        item = items[0]
        assert item["original_url"] == "minio://uploads/policy/road_safety.pdf"
        assert item["page_ref"] == "7"
        assert item["section_label"] == "3.1 สถิติอุบัติเหตุ"
        assert item["chunk_id"] == "chunk123"


# ═══════════════════════════════════════════════════════════════════
# 7. Orchestrator Integration — Citation Pipeline
# ═══════════════════════════════════════════════════════════════════

class TestOrchestratorCitationIntegration:
    """Test that orchestrator correctly integrates Citation & Evidence Agent."""

    def test_build_crew_includes_citation_agent(self):
        """Verify build_crew creates 7 agents including citation_evidence."""
        with patch("src.agents.orchestrator.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.return_value = mock_s

            from src.agents.orchestrator import build_crew
            agents = build_crew()

            assert "citation_evidence" in agents
            assert len(agents) == 7
            assert agents["citation_evidence"].role == "Citation & Evidence Specialist"

    def test_parse_evidence_context_from_crew_output(self):
        """Test that _parse_crew_result extracts citations from task output."""
        sample_citation_json = json.dumps({
            "evidence_items": [
                {"evidence_id": "EV-001", "evidence_type": "document", "source_ref": "test.pdf"},
            ],
            "claims": [
                {"claim_id": "CL-001", "claim_text": "test", "claim_type": "statistic",
                 "evidence_ids": ["EV-001"], "support_level": "supported"},
            ],
            "citations": [
                {"citation_code": "C-001", "evidence_id": "EV-001", "source_type": "document",
                 "source_ref": "test.pdf", "citation_text": "Test Doc, p.1",
                 "bibliography_text": "Test Document.", "open_url": "/api/documents/open/1"},
            ],
            "coverage": {"total_claims": 1, "supported": 1, "coverage_score": 1.0, "flags": []},
        })

        # Mock CrewAI result structure
        mock_task_output = MagicMock()
        mock_task_output.raw = sample_citation_json

        mock_result = MagicMock()
        mock_result.__str__ = lambda self: "Final report content"
        mock_result.tasks_output = [
            MagicMock(raw="interpret output"),    # 0: interpret
            MagicMock(raw="retrieval output"),    # 1: retrieve
            MagicMock(raw="sql output"),          # 2: sql
            mock_task_output,                     # 3: citation (this is what we parse)
            MagicMock(raw="analysis output"),     # 4: analyze
            MagicMock(raw="[]"),                  # 5: charts
            MagicMock(raw="report output"),       # 6: report
        ]

        from src.agents.orchestrator import _parse_crew_result
        response = _parse_crew_result(mock_result, elapsed=30.0)

        assert len(response.citations) == 1
        assert response.citations[0].citation_code == "C-001"
        assert response.metadata.get("citation_count") == 1
        assert response.metadata.get("total_evidence") == 1
        assert response.metadata.get("coverage_score") == 1.0

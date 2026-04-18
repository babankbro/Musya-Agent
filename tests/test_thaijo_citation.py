"""Integration tests for ThaiJO → Citation & Evidence pipeline.

Tests:
  - EvidenceItem normalization from ThaiJO results
  - Citation code range C-200 to C-299
  - APA from reference field vs. fallback when null
  - Mixed sources (C-001 doc + C-100 db + C-200 thaijo)
  - Deduplication by pdf_url
  - parse_evidence_context handling of thaijo_article evidence_type
  - _enrich_citations_from_db does not overwrite ThaiJO open_url (no document_registry row)
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from src.schemas.evidence import EvidenceItem, EnhancedCitation, EvidenceContext
from src.agents.citation_evidence import parse_evidence_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_thaijo_evidence_item(
    ev_id: str = "EV-001",
    pdf_url: str = "https://he01.tci-thaijo.org/index.php/jnhs/article/view/12345/9999",
    reference: str | None = "สมชาย ใจดี. (2567). ปัจจัยเสี่ยง. *วารสารสาธารณสุขศาสตร์*, 54(2), 123-135.",
    summary: str = "งานวิจัยนี้ศึกษาปัจจัยเสี่ยงต่ออุบัติเหตุทางถนน...",
    search_term: str = "อุบัติเหตุทางถนน ปัจจัยเสี่ยง",
    topic: str = "accident",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=ev_id,
        evidence_type="thaijo_article",
        topic=topic,
        source_ref=pdf_url,
        title="ปัจจัยเสี่ยงต่อการเกิดอุบัติเหตุทางถนน",
        trust_level="medium",
        apa_type="article",
        apa_authors="สมชาย ใจดี",
        apa_year="2567",
        apa_publisher="วารสารสาธารณสุขศาสตร์",
        open_url=pdf_url,
        original_url=pdf_url,
        text_snippet=summary[:500],
        thaijo_pdf_url=pdf_url,
        thaijo_reference=reference or "",
        thaijo_summary=summary,
        thaijo_search_term=search_term,
    )


def _make_citation_json_output(
    evidence_items: list[dict],
    citations: list[dict],
    claims: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            "evidence_items": evidence_items,
            "claims": claims or [],
            "citations": citations,
            "coverage": {
                "total_claims": 0,
                "supported": 0,
                "unsupported": 0,
                "coverage_score": 1.0,
                "flags": [],
            },
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# 1. EvidenceItem schema accepts thaijo_article
# ---------------------------------------------------------------------------

class TestThaiJOEvidenceItem:
    def test_evidence_type_thaijo_article_accepted(self):
        """EvidenceItem schema accepts thaijo_article evidence_type."""
        item = _make_thaijo_evidence_item()
        assert item.evidence_type == "thaijo_article"

    def test_thaijo_fields_populated(self):
        """ThaiJO-specific fields are stored correctly."""
        pdf_url = "https://he01.tci-thaijo.org/test/view/1"
        ref = "ผู้แต่ง. (2566). ชื่อบทความ. *วารสาร*, 1(1), 1-10."
        item = _make_thaijo_evidence_item(pdf_url=pdf_url, reference=ref)

        assert item.thaijo_pdf_url == pdf_url
        assert item.thaijo_reference == ref
        assert item.open_url == pdf_url
        assert item.apa_type == "article"
        assert item.trust_level == "medium"

    def test_thaijo_fields_default_empty_string(self):
        """ThaiJO fields default to empty string (not None) for safe string ops."""
        item = EvidenceItem(
            evidence_id="EV-001",
            evidence_type="document",
            source_ref="some_file.pdf",
        )
        assert item.thaijo_pdf_url == ""
        assert item.thaijo_reference == ""
        assert item.thaijo_summary == ""
        assert item.thaijo_search_term == ""

    def test_null_reference_stored_as_empty_string(self):
        """When reference is None, thaijo_reference defaults to empty string."""
        item = _make_thaijo_evidence_item(reference=None)
        assert item.thaijo_reference == ""


# ---------------------------------------------------------------------------
# 2. Citation code range C-200 to C-299
# ---------------------------------------------------------------------------

class TestThaiJOCitationCodeRange:
    def _build_output_with_n_thaijo_citations(self, n: int) -> str:
        ev_items = [
            {
                "evidence_id": f"EV-{i+1:03d}",
                "evidence_type": "thaijo_article",
                "source_ref": f"https://he01.tci-thaijo.org/article/{i}",
                "title": f"บทความที่ {i+1}",
                "trust_level": "medium",
                "apa_type": "article",
                "open_url": f"https://he01.tci-thaijo.org/article/{i}",
            }
            for i in range(n)
        ]
        citations = [
            {
                "citation_code": f"C-{200 + i:03d}",
                "evidence_id": f"EV-{i+1:03d}",
                "source_type": "thaijo_article",
                "source_ref": f"https://he01.tci-thaijo.org/article/{i}",
                "citation_text": f"(ThaiJO, 256{i})",
                "bibliography_text": f"ผู้แต่ง {i+1}. (256{i}). บทความ {i+1}. *วารสาร*, 1(1), 1-5.",
                "open_url": f"https://he01.tci-thaijo.org/article/{i}",
                "trust_level": "medium",
            }
            for i in range(n)
        ]
        return _make_citation_json_output(ev_items, citations)

    def test_single_thaijo_citation_starts_at_c200(self):
        """First ThaiJO citation must have code C-200."""
        raw = self._build_output_with_n_thaijo_citations(1)
        ctx = parse_evidence_context(raw)
        assert len(ctx.citations) == 1
        assert ctx.citations[0].citation_code == "C-200"

    def test_multiple_thaijo_citations_sequential(self):
        """ThaiJO citations are C-200, C-201, C-202, ..."""
        raw = self._build_output_with_n_thaijo_citations(5)
        ctx = parse_evidence_context(raw)
        codes = [c.citation_code for c in ctx.citations]
        assert codes == ["C-200", "C-201", "C-202", "C-203", "C-204"]

    def test_thaijo_citation_code_not_in_doc_range(self):
        """ThaiJO citations must not use C-001 to C-099 range."""
        raw = self._build_output_with_n_thaijo_citations(3)
        ctx = parse_evidence_context(raw)
        for c in ctx.citations:
            num = int(c.citation_code.split("-")[1])
            assert num >= 200, f"ThaiJO citation {c.citation_code} is in wrong range"

    def test_thaijo_citation_code_not_in_db_range(self):
        """ThaiJO citations must not use C-100 to C-199 range."""
        raw = self._build_output_with_n_thaijo_citations(3)
        ctx = parse_evidence_context(raw)
        for c in ctx.citations:
            num = int(c.citation_code.split("-")[1])
            assert not (100 <= num <= 199), f"ThaiJO citation {c.citation_code} conflicts with DB range"


# ---------------------------------------------------------------------------
# 3. APA from reference field
# ---------------------------------------------------------------------------

class TestThaiJOAPA:
    def test_apa_from_reference_field(self):
        """When reference is present, bibliography_text uses it directly."""
        ref_text = "สมชาย ใจดี, & สมหญิง รักเรียน. (2567). ปัจจัยเสี่ยง. *วารสารสาธารณสุข*, 54(2), 123."
        raw = _make_citation_json_output(
            evidence_items=[{
                "evidence_id": "EV-001",
                "evidence_type": "thaijo_article",
                "source_ref": "https://he01.tci-thaijo.org/article/1",
                "title": "ปัจจัยเสี่ยง",
                "open_url": "https://he01.tci-thaijo.org/article/1",
            }],
            citations=[{
                "citation_code": "C-200",
                "evidence_id": "EV-001",
                "source_type": "thaijo_article",
                "source_ref": "https://he01.tci-thaijo.org/article/1",
                "citation_text": "(สมชาย, 2567)",
                "bibliography_text": ref_text,
                "open_url": "https://he01.tci-thaijo.org/article/1",
                "trust_level": "medium",
            }],
        )
        ctx = parse_evidence_context(raw)
        assert ctx.citations[0].bibliography_text == ref_text

    def test_apa_fallback_when_reference_null(self):
        """When reference is None, bibliography_text contains ThaiJO and pdf_url."""
        pdf_url = "https://he01.tci-thaijo.org/index.php/test/article/view/99"
        fallback_bib = f"[ไม่ระบุผู้แต่ง]. (ไม่ระบุปี). *[ไม่ระบุชื่อ]*. ThaiJO. {pdf_url}"
        raw = _make_citation_json_output(
            evidence_items=[{
                "evidence_id": "EV-001",
                "evidence_type": "thaijo_article",
                "source_ref": pdf_url,
                "title": "",
                "open_url": pdf_url,
            }],
            citations=[{
                "citation_code": "C-200",
                "evidence_id": "EV-001",
                "source_type": "thaijo_article",
                "source_ref": pdf_url,
                "citation_text": "(ThaiJO, ไม่ระบุปี)",
                "bibliography_text": fallback_bib,
                "open_url": pdf_url,
                "trust_level": "medium",
            }],
        )
        ctx = parse_evidence_context(raw)
        bib = ctx.citations[0].bibliography_text
        assert "ThaiJO" in bib
        assert pdf_url in bib

    def test_open_url_is_thaijo_pdf_url(self):
        """open_url for ThaiJO citations must be TCI-THAIJO URL, not /api/documents/open/."""
        pdf_url = "https://he01.tci-thaijo.org/index.php/jnhs/article/view/12345/9999"
        raw = _make_citation_json_output(
            evidence_items=[{
                "evidence_id": "EV-001",
                "evidence_type": "thaijo_article",
                "source_ref": pdf_url,
                "title": "บทความ",
                "open_url": pdf_url,
            }],
            citations=[{
                "citation_code": "C-200",
                "evidence_id": "EV-001",
                "source_type": "thaijo_article",
                "source_ref": pdf_url,
                "citation_text": "(ผู้แต่ง, 2567)",
                "bibliography_text": "ผู้แต่ง. (2567). บทความ. *วารสาร*.",
                "open_url": pdf_url,
                "trust_level": "medium",
            }],
        )
        ctx = parse_evidence_context(raw)
        url = ctx.citations[0].open_url
        assert url.startswith("https://")
        assert "tci-thaijo.org" in url
        assert "/api/documents/open/" not in url


# ---------------------------------------------------------------------------
# 4. Mixed sources: doc + db + thaijo
# ---------------------------------------------------------------------------

class TestMixedSources:
    def _build_mixed_output(self) -> str:
        ev_items = [
            {
                "evidence_id": "EV-001",
                "evidence_type": "document",
                "source_ref": "mental_health/M_การพัฒนาแนวทาง.pdf",
                "title": "การพัฒนาแนวทาง",
                "open_url": "/api/documents/open/10",
            },
            {
                "evidence_id": "EV-002",
                "evidence_type": "database",
                "source_ref": "mart_accident_summary",
                "title": "Accident Summary",
                "open_url": "",
            },
            {
                "evidence_id": "EV-003",
                "evidence_type": "thaijo_article",
                "source_ref": "https://he01.tci-thaijo.org/article/42",
                "title": "งานวิจัยอุบัติเหตุ",
                "open_url": "https://he01.tci-thaijo.org/article/42",
            },
        ]
        citations = [
            {
                "citation_code": "C-001",
                "evidence_id": "EV-001",
                "source_type": "document",
                "source_ref": "mental_health/M_การพัฒนาแนวทาง.pdf",
                "citation_text": "(บุญกระจาง et al., 2557)",
                "bibliography_text": "บุญกระจาง, ท. et al. (2557). *การพัฒนาแนวทาง*. วารสาร.",
                "open_url": "/api/documents/open/10",
                "trust_level": "high",
            },
            {
                "citation_code": "C-100",
                "evidence_id": "EV-002",
                "source_type": "database",
                "source_ref": "mart_accident_summary",
                "citation_text": "(Musya Agent Database, 2568)",
                "bibliography_text": "Musya Agent. (2568). *mart_accident_summary* [Data set]. Musya Agent Database.",
                "open_url": "",
                "trust_level": "high",
            },
            {
                "citation_code": "C-200",
                "evidence_id": "EV-003",
                "source_type": "thaijo_article",
                "source_ref": "https://he01.tci-thaijo.org/article/42",
                "citation_text": "(ผู้แต่ง, 2566)",
                "bibliography_text": "ผู้แต่ง. (2566). งานวิจัยอุบัติเหตุ. *วารสาร*, 1(1), 1-10.",
                "open_url": "https://he01.tci-thaijo.org/article/42",
                "trust_level": "medium",
            },
        ]
        return _make_citation_json_output(ev_items, citations)

    def test_mixed_sources_all_parsed(self):
        """All three citation types (doc/db/thaijo) are parsed correctly."""
        ctx = parse_evidence_context(self._build_mixed_output())
        assert len(ctx.citations) == 3

    def test_mixed_sources_correct_codes(self):
        """Each source type gets its correct citation code range."""
        ctx = parse_evidence_context(self._build_mixed_output())
        codes = {c.citation_code: c.source_type for c in ctx.citations}
        assert codes["C-001"] == "document"
        assert codes["C-100"] == "database"
        assert codes["C-200"] == "thaijo_article"

    def test_mixed_sources_open_url_preserved(self):
        """ThaiJO open_url (TCI-THAIJO) is preserved; document open_url uses /api/documents/open/."""
        ctx = parse_evidence_context(self._build_mixed_output())
        thaijo_cit = next(c for c in ctx.citations if c.citation_code == "C-200")
        doc_cit = next(c for c in ctx.citations if c.citation_code == "C-001")

        assert thaijo_cit.open_url.startswith("https://he01.tci-thaijo.org")
        assert doc_cit.open_url.startswith("/api/documents/open/")


# ---------------------------------------------------------------------------
# 5. Deduplication by pdf_url
# ---------------------------------------------------------------------------

class TestThaiJODeduplication:
    def test_duplicate_pdf_url_produces_single_citation(self):
        """Two ThaiJO results with the same pdf_url should become one citation."""
        pdf_url = "https://he01.tci-thaijo.org/article/dup"
        raw = _make_citation_json_output(
            evidence_items=[
                {
                    "evidence_id": "EV-001",
                    "evidence_type": "thaijo_article",
                    "source_ref": pdf_url,
                    "title": "บทความซ้ำ",
                    "open_url": pdf_url,
                },
                {
                    "evidence_id": "EV-002",
                    "evidence_type": "thaijo_article",
                    "source_ref": pdf_url,
                    "title": "บทความซ้ำ (copy)",
                    "open_url": pdf_url,
                },
            ],
            citations=[
                {
                    "citation_code": "C-200",
                    "evidence_id": "EV-001",
                    "source_type": "thaijo_article",
                    "source_ref": pdf_url,
                    "citation_text": "(ผู้แต่ง, 2567)",
                    "bibliography_text": "ผู้แต่ง. (2567). บทความ. *วารสาร*.",
                    "open_url": pdf_url,
                    "trust_level": "medium",
                },
                {
                    "citation_code": "C-201",
                    "evidence_id": "EV-002",
                    "source_type": "thaijo_article",
                    "source_ref": pdf_url,
                    "citation_text": "(ผู้แต่ง, 2567)",
                    "bibliography_text": "ผู้แต่ง. (2567). บทความ. *วารสาร*.",
                    "open_url": pdf_url,
                    "trust_level": "medium",
                },
            ],
        )
        from src.agents.orchestrator import _dedup_citations
        from src.schemas.response import Citation

        ctx = parse_evidence_context(raw)
        raw_citations = [
            Citation(
                citation_code=c.citation_code,
                source_type=c.source_type,
                source_ref=c.source_ref,
                citation_text=c.citation_text,
                open_url=c.open_url,
                bibliography_text=c.bibliography_text,
            )
            for c in ctx.citations
        ]
        deduped = _dedup_citations(raw_citations)
        assert len(deduped) == 1
        assert deduped[0].citation_code == "C-200"


# ---------------------------------------------------------------------------
# 6. _enrich_citations_from_db does not overwrite ThaiJO open_url
# ---------------------------------------------------------------------------

class TestThaiJOEnrichment:
    def test_thaijo_open_url_not_overwritten_by_db_enrichment(self):
        """ThaiJO citations have external URLs — db enrichment must not overwrite them."""
        from src.agents.orchestrator import _enrich_citations_from_db
        from src.schemas.response import Citation

        thaijo_url = "https://he01.tci-thaijo.org/index.php/jnhs/article/view/99999/12345"
        citations = [
            Citation(
                citation_code="C-200",
                source_type="thaijo_article",
                source_ref=thaijo_url,
                citation_text="(ผู้แต่ง, 2567)",
                bibliography_text="ผู้แต่ง. (2567). บทความ. *วารสาร*, 1(1), 1-10.",
                open_url=thaijo_url,
            )
        ]
        enriched = _enrich_citations_from_db(citations)

        assert len(enriched) == 1
        assert enriched[0].open_url == thaijo_url, (
            "ThaiJO open_url should not be replaced by db enrichment"
        )

    def test_thaijo_bibliography_not_overwritten_by_db_enrichment(self):
        """ThaiJO bibliography from TCI-THAIJO reference should survive db enrichment."""
        from src.agents.orchestrator import _enrich_citations_from_db
        from src.schemas.response import Citation

        thaijo_url = "https://he01.tci-thaijo.org/index.php/jnhs/article/view/55555/9876"
        original_bib = "สมหมาย สุขดี. (2565). ชื่อบทความวิจัย. *วารสารสาธารณสุข*, 54(2), 100-112."
        citations = [
            Citation(
                citation_code="C-201",
                source_type="thaijo_article",
                source_ref=thaijo_url,
                citation_text="(สมหมาย, 2565)",
                bibliography_text=original_bib,
                open_url=thaijo_url,
            )
        ]
        enriched = _enrich_citations_from_db(citations)
        assert enriched[0].bibliography_text == original_bib


# ---------------------------------------------------------------------------
# 7. parse_evidence_context round-trip for thaijo evidence_type
# ---------------------------------------------------------------------------

class TestParseEvidenceContextThaijo:
    def test_thaijo_evidence_type_survives_parse(self):
        """evidence_type='thaijo_article' is preserved through parse_evidence_context."""
        raw = _make_citation_json_output(
            evidence_items=[{
                "evidence_id": "EV-001",
                "evidence_type": "thaijo_article",
                "source_ref": "https://he01.tci-thaijo.org/article/1",
                "title": "บทความ",
                "open_url": "https://he01.tci-thaijo.org/article/1",
            }],
            citations=[{
                "citation_code": "C-200",
                "evidence_id": "EV-001",
                "source_type": "thaijo_article",
                "source_ref": "https://he01.tci-thaijo.org/article/1",
                "citation_text": "(ผู้แต่ง, 2567)",
                "bibliography_text": "ผู้แต่ง. (2567). บทความ. *วารสาร*.",
                "open_url": "https://he01.tci-thaijo.org/article/1",
                "trust_level": "medium",
            }],
        )
        ctx = parse_evidence_context(raw)
        assert len(ctx.evidence_items) == 1
        assert ctx.evidence_items[0].evidence_type == "thaijo_article"
        assert len(ctx.citations) == 1
        assert ctx.citations[0].source_type == "thaijo_article"

    def test_malformed_thaijo_json_returns_empty_context(self):
        """Malformed JSON returns empty EvidenceContext without raising."""
        ctx = parse_evidence_context("not valid json {{{{")
        assert ctx.evidence_items == []
        assert ctx.citations == []

    def test_empty_string_returns_empty_context(self):
        """Empty string input returns empty EvidenceContext."""
        ctx = parse_evidence_context("")
        assert ctx.evidence_items == []
        assert ctx.citations == []

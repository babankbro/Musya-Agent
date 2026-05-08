import pytest
import json
from src.agents.citation_evidence import parse_evidence_context
from unittest.mock import patch

class TestParseEvidenceContext:

    def test_a_valid_full_json(self):
        json_data = {
            "evidence_items": [{"evidence_id": "EV-001", "source_ref": "doc.pdf"}],
            "claims": [{"claim_id": "CL-001", "claim_text": "test claim"}],
            "citations": [{"citation_code": "C-001", "evidence_id": "EV-001", "source_type": "document"}],
            "coverage": {"coverage_score": 1.0, "total_claims": 1}
        }
        ctx = parse_evidence_context(json.dumps(json_data))
        assert len(ctx.evidence_items) == 1
        assert ctx.evidence_items[0].evidence_id == "EV-001"
        assert len(ctx.claims) == 1
        assert ctx.claims[0].claim_id == "CL-001"
        assert len(ctx.citations) == 1
        assert ctx.citations[0].citation_code == "C-001"
        assert ctx.coverage_report.coverage_score == 1.0

    def test_b_fenced_json_block(self):
        json_data = {
            "evidence_items": [{"evidence_id": "EV-002", "source_ref": "doc2.pdf"}]
        }
        raw_text = f"Here is the result:\n```json\n{json.dumps(json_data)}\n```\nDone."
        ctx = parse_evidence_context(raw_text)
        assert len(ctx.evidence_items) == 1
        assert ctx.evidence_items[0].evidence_id == "EV-002"

    def test_c_raw_text_no_json(self):
        raw_text = "This is a response without any JSON."
        ctx = parse_evidence_context(raw_text)
        assert len(ctx.evidence_items) == 0
        assert len(ctx.claims) == 0
        assert len(ctx.citations) == 0

    def test_d_missing_required_fields_skip(self):
        # Using an invalid evidence item (e.g. missing evidence_id which is required in Pydantic)
        # It should skip it and process valid ones.
        json_data = {
            "evidence_items": [
                {"source_ref": "doc.pdf"},  # missing evidence_id
                {"evidence_id": "EV-003", "source_ref": "doc3.pdf", "evidence_type": "document"}
            ]
        }
        ctx = parse_evidence_context(json.dumps(json_data))
        assert len(ctx.evidence_items) == 1
        assert ctx.evidence_items[0].evidence_id == "EV-003"

    def test_e_cross_reference_overwrite_open_url(self):
        json_data = {
            "evidence_items": [
                {
                    "evidence_id": "EV-004", 
                    "source_ref": "doc4.pdf", 
                    "open_url": "/api/documents/open/123",
                    "evidence_type": "document"
                }
            ],
            "citations": [
                {
                    "citation_code": "C-004", 
                    "evidence_id": "EV-004", 
                    "source_type": "document",
                    "open_url": "" # Empty, should be overwritten
                }
            ]
        }
        # In parse_evidence_context, open_url is overwritten by the evidence item's open_url
        ctx = parse_evidence_context(json.dumps(json_data))
        assert len(ctx.citations) == 1
        assert ctx.citations[0].open_url == "/api/documents/open/123"

    @patch('src.utils.apa_formatter.format_apa_reference')
    def test_f_cross_reference_overwrite_bibliography(self, mock_format):
        mock_format.return_value = "Correct DB APA"
        json_data = {
            "evidence_items": [
                {
                    "evidence_id": "EV-005", 
                    "source_ref": "doc5.pdf", 
                    "open_url": "/api/documents/open/123", # Set to trigger rewrite
                    "apa_authors": "DB Author",
                    "apa_year": "2025",
                    "apa_publisher": "DB Publisher",
                    "apa_type": "report",
                    "title": "DB Title",
                    "evidence_type": "document"
                }
            ],
            "citations": [
                {
                    "citation_code": "C-005", 
                    "evidence_id": "EV-005", 
                    "source_type": "document",
                    "bibliography_text": "Hallucinated APA text"
                }
            ]
        }
        ctx = parse_evidence_context(json.dumps(json_data))
        assert len(ctx.citations) == 1
        assert ctx.citations[0].bibliography_text == "Correct DB APA"
        mock_format.assert_called_once()

    def test_g_thaijo_evidence_no_overwrite(self):
        json_data = {
            "evidence_items": [
                {
                    "evidence_id": "EV-006", 
                    "source_ref": "https://thaijo.org/123", 
                    "evidence_type": "thaijo_article",
                    "open_url": "https://thaijo.org/123",
                    "apa_authors": "ThaiJO Author"
                }
            ],
            "citations": [
                {
                    "citation_code": "C-006", 
                    "evidence_id": "EV-006", 
                    "source_type": "thaijo_article",
                    "bibliography_text": "Original ThaiJO APA"
                }
            ]
        }
        ctx = parse_evidence_context(json.dumps(json_data))
        assert len(ctx.citations) == 1
        # It should not have been overwritten since evidence_type == "thaijo_article"
        assert ctx.citations[0].bibliography_text == "Original ThaiJO APA"

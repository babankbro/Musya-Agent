"""Evidence & Citation schemas for the Citation & Evidence Agent."""
from pydantic import BaseModel, Field
from datetime import datetime


class EvidenceItem(BaseModel):
    """Normalized evidence from any source (document, database, API)."""
    evidence_id: str = Field(..., description="Unique ID, e.g. EV-001")
    evidence_type: str = Field(..., description="document | database | api | notebooklm_pdf | thaijo_article")
    topic: str = Field("general", description="accident | mental_health | nutrition")

    # Source identification
    source_ref: str = Field(..., description="Document name or table/view name")
    title: str = Field("", description="Human-readable title")
    section_label: str = Field("", description="Section/heading within document")
    page_ref: str = Field("", description="Page number for documents")
    chunk_id: str = Field("", description="ChromaDB chunk ID")
    chunk_index: int = Field(-1, description="Chunk position in document")

    # For database evidence
    query_signature: str = Field("", description="SHA-256 of the SQL query")
    query_params: dict = Field(default_factory=dict, description="Query parameters")

    # Context
    geography_ref: str = Field("", description="Province/district referenced")
    time_range_ref: str = Field("", description="Year/month/period referenced")
    text_snippet: str = Field("", description="Key text excerpt (max 500 chars)")

    # Trust & provenance
    extracted_at: str = Field("", description="ISO timestamp of extraction")
    trust_level: str = Field("medium", description="high | medium | low")

    # URLs for traceability
    original_url: str = Field("", description="Original source URL (MinIO, PostgreSQL, API)")
    open_url: str = Field("", description="Clickable URL for frontend: /api/documents/open/{id}")

    # APA 7th Edition metadata
    apa_type: str = Field("report", description="report | book | article | website | dataset | law")
    apa_authors: str = Field("", description="Author/organization name for APA reference")
    apa_year: str = Field("", description="Publication year (พ.ศ. or ค.ศ.)")
    apa_publisher: str = Field("", description="Publisher or organization")

    # ThaiJO-specific fields (only populated for thaijo_article evidence)
    thaijo_pdf_url: str = Field("", description="Direct PDF URL on TCI-THAIJO portal")
    thaijo_reference: str = Field("", description="Raw APA citation text extracted from TCI-THAIJO HTML (null-safe)")
    thaijo_summary: str = Field("", description="AI-generated Thai summary of the PDF (from ThaiJO microservice)")
    thaijo_search_term: str = Field("", description="Original search keyword used to find this article")


class Claim(BaseModel):
    """A single factual claim that needs evidence backing."""
    claim_id: str = Field(..., description="Unique ID, e.g. CL-001")
    claim_text: str = Field(..., description="The claim statement")
    claim_type: str = Field("general_finding", description="statistic | comparison | trend | recommendation | general_finding")
    section_id: str = Field("", description="Report section this claim belongs to")
    object_type: str = Field("text", description="text | chart | table")
    object_id: str = Field("", description="ID of the chart/table/paragraph")


class ClaimEvidenceLink(BaseModel):
    """Maps a claim to its supporting evidence."""
    claim_id: str = Field(...)
    evidence_id: str = Field(...)
    support_level: str = Field("supported", description="supported | partially_supported | insufficient | conflicting")
    evidence_strength: str = Field("moderate", description="strong | moderate | weak")
    confidence_note: str = Field("", description="Human-readable explanation")


class EnhancedCitation(BaseModel):
    """Enhanced citation for display in UI and DOCX — extends the base Citation."""
    citation_code: str = Field(..., description="e.g. C-001")
    evidence_id: str = Field(..., description="Link to EvidenceItem")
    source_type: str = Field(..., description="document | database | api")
    source_ref: str = Field("", description="Document name or table name")
    citation_text: str = Field("", description="Short display citation (inline)")
    bibliography_text: str = Field("", description="Full bibliography entry for reference list")
    open_url: str = Field("", description="Clickable URL: /api/documents/open/{id}")
    trust_level: str = Field("medium", description="Inherited from evidence")


class CoverageReport(BaseModel):
    """Quality report from Coverage Validator."""
    total_claims: int = Field(0)
    supported_claims: int = Field(0)
    partially_supported: int = Field(0)
    unsupported_claims: int = Field(0)
    total_charts: int = Field(0)
    charts_with_source: int = Field(0)
    total_tables: int = Field(0)
    tables_with_source: int = Field(0)
    coverage_score: float = Field(0.0)
    flags: list[dict] = Field(default_factory=list)


class EvidenceContext(BaseModel):
    """Complete evidence context passed to downstream agents."""
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    claim_links: list[ClaimEvidenceLink] = Field(default_factory=list)
    citations: list[EnhancedCitation] = Field(default_factory=list)
    coverage_report: CoverageReport = Field(default_factory=CoverageReport)

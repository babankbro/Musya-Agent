"""Pydantic schemas for the Policy Brief API endpoint."""
from pydantic import BaseModel, Field
from typing import Any


class PolicyBriefRequest(BaseModel):
    """Request body for POST /api/policy-brief."""
    province: str = Field(..., description="Province name in Thai (เขตสุขภาพที่ 10)")
    topics: list[str] = Field(
        default=["rti", "mental", "ncd"],
        description="Topics to analyze: 'rti', 'mental', 'ncd'",
    )
    year: int = Field(2564, description="Thai Buddhist year (พ.ศ.), e.g. 2564")
    format: str = Field("markdown", description="Output format: 'markdown'")


class PolicyBriefCitation(BaseModel):
    """A single citation entry in the policy brief."""
    citation_code: str = Field("", description="e.g. C-001")
    source_type: str = Field("", description="notebooklm_pdf | database | document")
    source_ref: str = Field("", description="Source reference string")
    citation_text: str = Field("", description="Human-readable citation")


class PolicyBriefSection(BaseModel):
    """Analysis result for a single topic."""
    situation: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    raw: str = Field("", description="Raw JSON or text from analyst agent")


class PolicyBriefMetadata(BaseModel):
    """Pipeline execution metadata."""
    elapsed_seconds: float = Field(0.0)
    agent_count: int = Field(6)
    pipeline: str = Field("phase3_policy_brief")
    notebook_id: str = Field("")
    topics_analyzed: list[str] = Field(default_factory=list)
    year: int = Field(2564)
    error: str = Field("", description="Error message if pipeline failed")


class PolicyBriefResponse(BaseModel):
    """Response body for POST /api/policy-brief."""
    province: str = Field(..., description="Province that was analyzed")
    policy_brief: str = Field(..., description="Full Policy Brief in Markdown format")
    sections: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured analysis per topic: {'rti': {...}, 'mental': {...}, 'ncd': {...}}",
    )
    cross_topic_links: list[str] = Field(
        default_factory=list,
        description="Cross-topic linkage findings",
    )
    charts: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvincesResponse(BaseModel):
    """Response for GET /api/policy-brief/provinces."""
    provinces: list[str] = Field(description="Supported province names")
    notebook_id: str = Field(description="Shared notebook UUID for all provinces")
    health_zone: str = Field("เขตสุขภาพที่ 10", description="Health zone name")

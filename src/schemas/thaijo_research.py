"""Schemas for the ThaiJO Research Report pipeline (SRS FR-TJR)."""
from pydantic import BaseModel, Field
from typing import Any


class ThaiJOResearchRequest(BaseModel):
    """Request schema for POST /api/thaijo/research."""
    topic: str = Field(..., description="Research topic in Thai or English")
    max_articles: int = Field(15, ge=5, le=40, description="Max articles to include in report")
    max_queries: int = Field(4, ge=1, le=6, description="Max search queries to generate")
    min_relevance: float = Field(5.0, ge=0, le=10, description="Min relevance score (0-10) to include article")
    session_id: str | None = Field(None, description="Optional session ID")
    user_id: str | None = Field(None, description="Optional user ID")


class SearchQueryItem(BaseModel):
    """A single search query produced by the Topic Parser agent."""
    term: str
    size: int = Field(5, ge=1, le=10)
    priority: int = Field(1, ge=1)


class TopicParserOutput(BaseModel):
    """Structured output from Agent 1 (Research Topic Parser)."""
    main_topic: str
    domain: str = "general"
    search_queries: list[SearchQueryItem] = []
    inclusion_criteria: str = ""
    exclusion_criteria: str = ""


class ScreenedArticle(BaseModel):
    """An article after relevance screening (Agent 3 output)."""
    pdf_url: str
    summary: str
    reference: str | None = None
    relevance_score: float = Field(0.0, ge=0, le=10)
    relevance_reason: str = ""
    themes: list[str] = []
    included: bool = True
    source_queries: list[str] = []


class ThaiJOResearchResponse(BaseModel):
    """Response schema for POST /api/thaijo/research."""
    content: str = Field("", description="Markdown literature review report (1,500-3,000 words)")
    topic: str = Field("general", description="Detected domain")
    articles_found: int = Field(0, description="Total articles from ThaiJO search")
    articles_selected: int = Field(0, description="Articles after screening")
    charts: list[dict[str, Any]] = Field(default_factory=list, description="ChartSpec objects")
    tables: list[dict[str, Any]] = Field(default_factory=list, description="TableSpec objects")
    citations: list[dict[str, Any]] = Field(default_factory=list, description="Citation objects (C-200+)")
    follow_ups: list[str] = Field(default_factory=list, description="3 follow-up research questions")
    metadata: dict[str, Any] = Field(default_factory=dict, description="elapsed_seconds, pipeline, queries, coverage")

from pydantic import BaseModel, Field
from typing import Any


class ChartDataset(BaseModel):
    """A single dataset within a ChartSpec — mirrors Chart.js dataset shape."""
    label: str = Field("ข้อมูล", description="Dataset label shown in legend")
    data: list[float | int | None] = Field(default_factory=list, description="Numeric data points")
    backgroundColor: list[str] | str | None = Field(None, description="Bar/pie fill colour(s)")
    borderColor: list[str] | str | None = Field(None, description="Line/bar border colour(s)")


class ChartSpec(BaseModel):
    """Chart specification that maps 1-to-1 with ChartRenderer's chartData prop.

    The frontend's normalizeChartData() accepts this exact shape:
      { type, title, data: { labels, datasets: [...] }, options }

    Supported types: bar | line | pie | doughnut
    """
    type: str = Field(..., description="Chart type: bar | line | pie | doughnut")
    title: str = Field(..., description="Chart title in Thai")
    data: dict[str, Any] = Field(
        ...,
        description='Chart.js data object: { "labels": [...], "datasets": [...] }',
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional Chart.js options overrides",
    )
    source_note: str = Field("", description="Data source citation shown below chart")


class TableSpec(BaseModel):
    """Specification for a table to be rendered by the frontend."""
    table_name: str = Field(..., description="Table title in Thai")
    columns: list[str] = Field(default_factory=list, description="Column headers")
    rows: list[list] = Field(default_factory=list, description="Row data")
    source_note: str = Field("", description="Data source citation")


class Citation(BaseModel):
    """A single citation reference."""
    citation_code: str = Field(..., description="e.g. C-001")
    source_type: str = Field(..., description="document | database | api")
    source_ref: str = Field("", description="Document name or table name")
    citation_text: str = Field("", description="Human-readable citation text")
    open_url: str = Field("", description="URL to open source document, e.g. /api/documents/open/123")
    bibliography_text: str = Field("", description="Full APA 7th Edition reference text")


class AgentResponse(BaseModel):
    """Structured response from the agent pipeline."""
    content: str = Field(..., description="Main response text in Thai (markdown)")
    topic: str = Field("general", description="Detected domain topic")
    charts: list[ChartSpec] = Field(default_factory=list)
    tables: list[TableSpec] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list, description="Suggested follow-up questions")
    metadata: dict = Field(default_factory=dict, description="Extra metadata (timing, agent trace, etc.)")

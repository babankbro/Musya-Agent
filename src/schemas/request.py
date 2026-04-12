from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""
    message: str = Field(..., description="User message text")
    session_id: str | None = Field(None, description="Chat session ID for context")
    user_id: str | None = Field(None, description="User ID from ChatV1 auth")


class ReportRequest(BaseModel):
    """Request body for full report generation."""
    topic: str = Field(..., description="Domain topic: accident, mental_health, nutrition, or all")
    geography: str = Field("", description="Province/district name in Thai")
    time_range_start: str = Field("", description="Start date YYYY-MM-DD")
    time_range_end: str = Field("", description="End date YYYY-MM-DD")
    report_type: str = Field("health_plan", description="Report type: health_plan, executive_summary, action_plan")
    focus_areas: list[str] = Field(default_factory=list, description="Specific focus areas for the report")

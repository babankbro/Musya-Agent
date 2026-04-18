"""Schemas for the Short Chat pipeline — lightweight Q&A (~30-60s)."""
from pydantic import BaseModel, Field


class ShortChatRequest(BaseModel):
    """Request body for the short chat endpoint."""
    message: str = Field(..., description="User message text")
    session_id: str | None = Field(None, description="Chat session ID for context")
    mode: str | None = Field("short", description="Chat mode: 'short' for quick answers")


class ShortChatCitation(BaseModel):
    """A single citation in a short chat response."""
    code: str = Field("", description="Citation code e.g. C-101")
    bibliography_text: str = Field("", description="APA-style bibliography text")
    open_url: str = Field("", description="URL to source document")


class ShortChatResponse(BaseModel):
    """Response from the Short Chat pipeline."""
    pipeline_used: str = "short_chat"
    content: str = Field("", description="Markdown answer (500-1,000 words)")
    citations: list[ShortChatCitation] = Field(default_factory=list)
    elapsed_seconds: float = Field(0.0, description="Processing time in seconds")
    follow_up_questions: list[str] = Field(default_factory=list)
    disclaimer: str = Field(
        "อ้างอิงเบื้องต้น — ใช้ 'รายงานเต็ม' สำหรับรายงานที่ผ่าน APA validation เต็มรูปแบบ",
        description="Disclaimer about citation completeness",
    )

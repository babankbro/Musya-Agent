"""Pydantic schemas for the Zone 10 Accident Policy API."""
from typing import Any
from pydantic import BaseModel, Field, model_validator

from src.tools.zone10_accident import ZONE10_PROVINCES

VALID_QUESTIONS = {"all", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}


class AccidentPolicyRequest(BaseModel):
    """Request body for POST /api/accident-policy/zone10."""
    provinces: list[str] = Field(
        default_factory=lambda: list(ZONE10_PROVINCES),
        description="Zone 10 province names in Thai. Defaults to all 5.",
    )
    questions: list[str] = Field(
        default=["all"],
        description="Question IDs to answer: 'all' or subset of Q1-Q7.",
    )
    year_range: list[int] = Field(
        default=[2021, 2026],
        description="[start_year, end_year] in CE. Must have exactly 2 elements.",
    )
    format: str = Field(
        default="markdown",
        description="Output format: 'markdown'",
    )

    @model_validator(mode="after")
    def validate_fields(self) -> "AccidentPolicyRequest":
        # Validate provinces
        valid = set(ZONE10_PROVINCES)
        invalid = [p for p in self.provinces if p not in valid]
        if invalid:
            raise ValueError(
                f"จังหวัดไม่ถูกต้อง: {invalid}. "
                f"จังหวัดที่รองรับ: {list(ZONE10_PROVINCES)}"
            )
        if not self.provinces:
            raise ValueError("ต้องระบุอย่างน้อย 1 จังหวัด")

        # Validate questions
        invalid_q = [q for q in self.questions if q not in VALID_QUESTIONS]
        if invalid_q:
            raise ValueError(
                f"คำถามไม่ถูกต้อง: {invalid_q}. "
                f"ค่าที่รองรับ: {sorted(VALID_QUESTIONS)}"
            )

        # Validate year_range
        if len(self.year_range) != 2:
            raise ValueError("year_range ต้องมีค่า 2 ตัว: [start_year, end_year]")
        if self.year_range[0] > self.year_range[1]:
            raise ValueError("year_range[0] ต้องน้อยกว่าหรือเท่ากับ year_range[1]")

        return self


class AccidentPolicyResponse(BaseModel):
    """Response body for POST /api/accident-policy/zone10."""
    zone: str = Field(default="เขตสุขภาพที่ 10")
    provinces: list[str] = Field(description="Provinces that were analyzed")
    policy_brief: str = Field(description="Full policy report in Markdown")
    sections: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured analysis: {hotspot, human_behavior, environment, kpi}",
    )
    charts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Zone10DataResponse(BaseModel):
    """Response body for GET /api/accident-policy/zone10/data (no LLM)."""
    zone: str = Field(default="เขตสุขภาพที่ 10")
    provinces: list[str]
    questions: dict[str, str] = Field(
        description="Raw SQL results per question key (Q1_hotspot_roads … Q7_monthly_risk)"
    )
    errors: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

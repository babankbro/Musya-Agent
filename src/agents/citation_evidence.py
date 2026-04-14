"""Citation & Evidence Agent — trust layer that normalizes evidence,
generates citations, and validates coverage before downstream agents."""
import json
import logging
from hashlib import sha256
from datetime import datetime, timezone

from crewai import Agent
from crewai.tools import tool

from src.db.pool import query_db
from src.schemas.evidence import (
    EvidenceItem, Claim, ClaimEvidenceLink, EnhancedCitation,
    CoverageReport, EvidenceContext,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

CITATION_EVIDENCE_PROMPT = """คุณคือ Citation & Evidence Agent — ผู้เชี่ยวชาญด้านการตรวจสอบหลักฐานและการอ้างอิง

จากข้อมูลที่ได้จาก Retrieval Agent และ SQL Specialist ให้ดำเนินการดังนี้:

1. **Normalize Evidence**: แปลงผลลัพธ์ทั้งหมดให้เป็น evidence items ที่มี metadata ครบถ้วน
   - ระบุ evidence_type (document / database / api)
   - ระบุ source_ref, title, page_ref, section_label
   - กำหนด trust_level (high / medium / low)
   - สร้าง original_url และ open_url

2. **Map Claims to Evidence**: วิเคราะห์ข้อสรุปทั้งหมดและเชื่อมกับหลักฐาน
   - ระบุว่าแต่ละข้อสรุปเป็น statistic / comparison / trend / recommendation / general_finding
   - กำหนด support_level: supported / partially_supported / insufficient / conflicting
   - กำหนด evidence_strength: strong / moderate / weak

3. **Generate Citations**: สร้าง citation code (C-001, C-002, ...)
   - สร้าง citation_text สำหรับแสดง inline ในรายงาน
   - สร้าง bibliography_text สำหรับ reference list ท้ายรายงาน
   - ระบุ open_url สำหรับคลิกกลับไปดูเอกสารต้นฉบับ

4. **Prepare Source Notes**: เตรียม source_note สำหรับกราฟและตาราง
   - แต่ละกราฟ/ตารางต้องมี source_note ที่ระบุแหล่งข้อมูล + citation code

5. **Coverage Check**: ตรวจสอบความครอบคลุม
   - ข้อสรุปเชิงตัวเลขทุกข้อต้องมี citation
   - กราฟ/ตารางทุกชิ้นต้องมี source_note
   - flag ข้อสรุปที่ไม่มีหลักฐานรองรับ

**Output Format**: ตอบเป็น JSON object ที่มีโครงสร้างดังนี้:
```json
{
  "evidence_items": [
    {
      "evidence_id": "EV-001",
      "evidence_type": "document|database|api",
      "source_ref": "filename or table name",
      "title": "readable title",
      "page_ref": "12",
      "section_label": "Section 3.2",
      "trust_level": "high|medium|low",
      "text_snippet": "key excerpt...",
      "original_url": "minio://uploads/...",
      "open_url": "/api/documents/open/..."
    }
  ],
  "claims": [
    {
      "claim_id": "CL-001",
      "claim_text": "statement...",
      "claim_type": "statistic|comparison|trend|recommendation|general_finding",
      "evidence_ids": ["EV-001"],
      "support_level": "supported",
      "evidence_strength": "strong"
    }
  ],
  "citations": [
    {
      "citation_code": "C-001",
      "evidence_id": "EV-001",
      "source_type": "document|database",
      "source_ref": "filename",
      "citation_text": "short display text",
      "bibliography_text": "full reference text",
      "open_url": "/api/documents/open/...",
      "trust_level": "high"
    }
  ],
  "source_notes": {
    "charts": "ที่มา: ... [C-001]",
    "tables": "ที่มา: ... [C-001]"
  },
  "coverage": {
    "total_claims": 5,
    "supported": 4,
    "unsupported": 1,
    "coverage_score": 0.80,
    "flags": ["CL-005: ข้อสรุปไม่มีหลักฐานรองรับ"]
  }
}
```

**สำคัญ**: ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่นนอก JSON"""


# ---------------------------------------------------------------------------
# CrewAI tools for the Citation Agent
# ---------------------------------------------------------------------------

@tool("register_evidence")
def register_evidence(evidence_json: str) -> str:
    """Register evidence items in the database for traceability.

    Args:
        evidence_json: JSON array of evidence items to register.

    Returns:
        Confirmation message with count of registered items.
    """
    try:
        items = json.loads(evidence_json) if isinstance(evidence_json, str) else evidence_json
    except (json.JSONDecodeError, TypeError):
        return "Error: invalid JSON for evidence registration"

    if not isinstance(items, list):
        items = [items]

    registered = 0
    for item in items:
        ev_id = item.get("evidence_id", "")
        if not ev_id:
            continue
        try:
            query_db(
                """INSERT INTO evidence_registry
                   (evidence_id, evidence_type, topic, source_ref, title,
                    section_label, page_ref, chunk_id, chunk_index,
                    query_signature, query_params, geography_ref, time_range_ref,
                    text_snippet, trust_level, original_url, open_url)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (evidence_id) DO NOTHING""",
                (
                    ev_id,
                    item.get("evidence_type", "document"),
                    item.get("topic", "general"),
                    item.get("source_ref", ""),
                    item.get("title", ""),
                    item.get("section_label", ""),
                    item.get("page_ref", ""),
                    item.get("chunk_id", ""),
                    item.get("chunk_index", -1),
                    item.get("query_signature", ""),
                    json.dumps(item.get("query_params", {})),
                    item.get("geography_ref", ""),
                    item.get("time_range_ref", ""),
                    item.get("text_snippet", "")[:500],
                    item.get("trust_level", "medium"),
                    item.get("original_url", ""),
                    item.get("open_url", ""),
                ),
            )
            registered += 1
        except Exception as e:
            logger.warning("Failed to register evidence %s: %s", ev_id, e)

    return f"ลงทะเบียน evidence สำเร็จ {registered} รายการ จากทั้งหมด {len(items)} รายการ"


@tool("register_claim_links")
def register_claim_links(links_json: str) -> str:
    """Register claim-evidence links in the database.

    Args:
        links_json: JSON array of {claim_id, claim_text, claim_type,
                    evidence_id, support_level, evidence_strength, citation_code}.

    Returns:
        Confirmation message.
    """
    try:
        links = json.loads(links_json) if isinstance(links_json, str) else links_json
    except (json.JSONDecodeError, TypeError):
        return "Error: invalid JSON for claim links"

    if not isinstance(links, list):
        links = [links]

    registered = 0
    for lnk in links:
        try:
            query_db(
                """INSERT INTO claim_evidence_link
                   (claim_id, claim_text, claim_type, evidence_id,
                    support_level, evidence_strength, confidence_note, citation_code)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    lnk.get("claim_id", ""),
                    lnk.get("claim_text", ""),
                    lnk.get("claim_type", ""),
                    lnk.get("evidence_id", ""),
                    lnk.get("support_level", "supported"),
                    lnk.get("evidence_strength", "moderate"),
                    lnk.get("confidence_note", ""),
                    lnk.get("citation_code", ""),
                ),
            )
            registered += 1
        except Exception as e:
            logger.warning("Failed to register claim link: %s", e)

    return f"ลงทะเบียน claim-evidence link สำเร็จ {registered} รายการ"


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def create_citation_evidence_agent(llm: str) -> Agent:
    """Create the Citation & Evidence Agent."""
    return Agent(
        role="Citation & Evidence Specialist",
        goal=(
            "Normalize all retrieved data into traceable evidence items, "
            "generate proper citations (C-001, C-002, ...) with open_url links, "
            "map every claim to supporting evidence, prepare source notes for charts/tables, "
            "and validate citation coverage before the report is written."
        ),
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญด้านการจัดการหลักฐานและการอ้างอิงทางวิชาการ "
            "คุณรู้วิธีแปลงข้อมูลดิบจากหลายแหล่ง (เอกสาร, ฐานข้อมูล, API) "
            "ให้เป็นหลักฐานที่ตรวจสอบย้อนกลับได้ "
            "คุณสร้าง citation code ที่สม่ำเสมอ, เชื่อม claim กับ evidence, "
            "เติม source note ให้กราฟและตาราง, และตรวจ coverage "
            "เพื่อให้รายงานสุดท้ายมีความน่าเชื่อถือ ลด hallucination "
            "และผู้ใช้สามารถคลิกกลับไปดูเอกสารต้นฉบับได้จริง"
        ),
        tools=[register_evidence, register_claim_links],
        llm=llm,
        verbose=True,
        max_iter=8,
    )


# ---------------------------------------------------------------------------
# Utility: parse the Citation Agent's JSON output
# ---------------------------------------------------------------------------

def parse_evidence_context(raw_output: str) -> EvidenceContext:
    """Parse the Citation & Evidence Agent's JSON output into an EvidenceContext."""
    ctx = EvidenceContext()

    # Try to extract JSON from the raw output
    json_str = raw_output.strip()

    # Handle ```json ... ``` fenced blocks
    import re
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", json_str, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Try to find the outermost { }
        start = json_str.find("{")
        end = json_str.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = json_str[start:end + 1]

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse Citation Agent output as JSON: %s", e)
        return ctx

    now = datetime.now(timezone.utc).isoformat()

    # Parse evidence items
    for item in data.get("evidence_items", []):
        try:
            ctx.evidence_items.append(EvidenceItem(
                evidence_id=item.get("evidence_id", ""),
                evidence_type=item.get("evidence_type", "document"),
                topic=item.get("topic", "general"),
                source_ref=item.get("source_ref", ""),
                title=item.get("title", ""),
                section_label=item.get("section_label", ""),
                page_ref=str(item.get("page_ref", "")),
                chunk_id=item.get("chunk_id", ""),
                chunk_index=item.get("chunk_index", -1),
                query_signature=item.get("query_signature", ""),
                query_params=item.get("query_params", {}),
                geography_ref=item.get("geography_ref", ""),
                time_range_ref=item.get("time_range_ref", ""),
                text_snippet=item.get("text_snippet", "")[:500],
                extracted_at=now,
                trust_level=item.get("trust_level", "medium"),
                original_url=item.get("original_url", ""),
                open_url=item.get("open_url", ""),
            ))
        except Exception as e:
            logger.warning("Skipping malformed evidence item: %s", e)

    # Parse claims and build links
    for claim_data in data.get("claims", []):
        try:
            claim = Claim(
                claim_id=claim_data.get("claim_id", ""),
                claim_text=claim_data.get("claim_text", ""),
                claim_type=claim_data.get("claim_type", "general_finding"),
                section_id=claim_data.get("section_id", ""),
                object_type=claim_data.get("object_type", "text"),
                object_id=claim_data.get("object_id", ""),
            )
            ctx.claims.append(claim)

            # Build claim-evidence links
            ev_ids = claim_data.get("evidence_ids", [])
            for ev_id in ev_ids:
                ctx.claim_links.append(ClaimEvidenceLink(
                    claim_id=claim.claim_id,
                    evidence_id=ev_id,
                    support_level=claim_data.get("support_level", "supported"),
                    evidence_strength=claim_data.get("evidence_strength", "moderate"),
                ))
        except Exception as e:
            logger.warning("Skipping malformed claim: %s", e)

    # Parse citations
    for cit in data.get("citations", []):
        try:
            ctx.citations.append(EnhancedCitation(
                citation_code=cit.get("citation_code", ""),
                evidence_id=cit.get("evidence_id", ""),
                source_type=cit.get("source_type", "document"),
                source_ref=cit.get("source_ref", ""),
                citation_text=cit.get("citation_text", ""),
                bibliography_text=cit.get("bibliography_text", ""),
                open_url=cit.get("open_url", ""),
                trust_level=cit.get("trust_level", "medium"),
            ))
        except Exception as e:
            logger.warning("Skipping malformed citation: %s", e)

    # Parse coverage
    cov = data.get("coverage", {})
    if cov:
        ctx.coverage_report = CoverageReport(
            total_claims=cov.get("total_claims", len(ctx.claims)),
            supported_claims=cov.get("supported", 0),
            partially_supported=cov.get("partially_supported", 0),
            unsupported_claims=cov.get("unsupported", 0),
            coverage_score=cov.get("coverage_score", 0.0),
            flags=[{"message": f} if isinstance(f, str) else f for f in cov.get("flags", [])],
        )

    return ctx

"""Request Router Agent: decides which pipeline to use (chat vs policy-brief)."""
import json
import logging
import re

from crewai import Agent, Task, Crew, Process

from src.config import get_settings
from src.tools.notebooklm import SUPPORTED_PROVINCES

logger = logging.getLogger(__name__)


def create_request_router(llm) -> Agent:
    return Agent(
        role="Request Router",
        goal=(
            "วิเคราะห์คำขอของผู้ใช้แล้วตัดสินใจว่าควรใช้ pipeline ไหน: "
            "chat_pipeline (ค้นหา/วิเคราะห์ข้อมูลอุบัติเหตุทั่วไป) หรือ "
            "policy_brief_pipeline (สร้าง Policy Brief สาธารณสุขเชิงนโยบาย)"
        ),
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญในการจำแนกประเภทคำขอด้านสาธารณสุข "
            "คุณสามารถแยกแยะได้ว่าคำขอเป็น:\n"
            "1) **chat_pipeline** — คำถามทั่วไปเกี่ยวกับข้อมูลอุบัติเหตุ สถิติ กราฟ แนวโน้ม "
            "   หรือคำถามสนทนาทั่วไป\n"
            "2) **policy_brief_pipeline** — คำขอสร้าง Policy Brief, รายงานเชิงนโยบาย, "
            "   รายงานตรวจราชการ, วิเคราะห์ข้อมูลสุขภาพจิต/โภชนาการ/NCD เชิงนโยบาย "
            f"   สำหรับจังหวัดในเขตสุขภาพที่ 10 ({', '.join(SUPPORTED_PROVINCES)})\n\n"
            "**กฎการตัดสินใจ:**\n"
            "- ถ้ามีคำว่า 'policy brief', 'นโยบาย', 'ตรวจราชการ', 'เขตสุขภาพ' → policy_brief_pipeline\n"
            "- ถ้าถามเกี่ยวกับสุขภาพจิต/โภชนาการ/NCD ของจังหวัดในเขต 10 และต้องการรายงานเชิงนโยบาย → policy_brief_pipeline\n"
            "- ถ้าถามสถิติอุบัติเหตุทั่วไป, จุดเสี่ยง, แนวโน้ม, กราฟ → chat_pipeline\n"
            "- ถ้าเป็นคำถามสนทนาทั่วไป, ทักทาย → chat_pipeline\n"
            "- ถ้าไม่แน่ใจ → chat_pipeline (default)"
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


REQUEST_ROUTER_PROMPT = """
วิเคราะห์คำขอของผู้ใช้แล้วตัดสินใจว่าควรใช้ pipeline ไหน

## Pipeline ที่มี

### 1. chat_pipeline
- สำหรับ: คำถามทั่วไปเกี่ยวกับอุบัติเหตุ, สถิติ, กราฟ, แนวโน้ม, จุดเสี่ยง
- สำหรับ: คำถามสนทนาทั่วไป, ทักทาย, ถามข้อมูลเบื้องต้น
- Data sources: PostgreSQL + pgvector (Document RAG)
- Output: รายงาน Markdown + กราฟ + citations

### 2. policy_brief_pipeline
- สำหรับ: สร้าง Policy Brief เชิงนโยบายสาธารณสุข
- สำหรับ: รายงานตรวจราชการ, วิเคราะห์เชิงระบบ 3 หัวข้อ (RTI/สุขภาพจิต/NCD)
- จังหวัดที่รองรับ: มุกดาหาร, ยโสธร, ศรีสะเกษ, อำนาจเจริญ, อุบลราชธานี (เขตสุขภาพที่ 10)
- Data sources: NotebookLM (PDF inspection reports) + PostgreSQL
- Output: Policy Brief ฉบับสมบูรณ์ + cross-topic analysis

## คำสำคัญที่ช่วยตัดสินใจ

**→ policy_brief_pipeline:**
- "policy brief", "นโยบาย", "ตรวจราชการ", "เขตสุขภาพ"
- "สร้างรายงาน...เชิงนโยบาย", "วิเคราะห์เชิงระบบ"
- ถ้าระบุจังหวัดในเขต 10 + ถามเรื่องสุขภาพจิตหรือ NCD เชิงนโยบาย
- "executive summary", "บทสรุปผู้บริหาร", "ข้อเสนอแนะเชิงนโยบาย"

**→ chat_pipeline:**
- "สถิติ", "จำนวน", "กราฟ", "แนวโน้ม", "จุดเสี่ยง"
- คำถามทั่วไป, สนทนา, ถามข้อมูลเบื้องต้น
- จังหวัดนอกเขต 10

## ตอบเป็น JSON เท่านั้น:

```json
{{
    "pipeline": "chat_pipeline หรือ policy_brief_pipeline",
    "confidence": 0.0-1.0,
    "reason": "เหตุผลสั้นๆ ที่เลือก pipeline นี้",
    "extracted_params": {{
        "province": "ชื่อจังหวัด (ถ้ามี)",
        "topics": ["rti", "mental", "ncd"],
        "year": 2564,
        "report_type": "data_query หรือ policy_brief"
    }}
}}
```

ข้อความผู้ใช้: {user_message}
"""


def route_request(user_message: str) -> dict:
    """Run the Request Router Agent to decide which pipeline to use.

    Returns:
        dict with keys: pipeline, confidence, reason, extracted_params
    """
    s = get_settings()
    llm = f"gemini/{s.GEMINI_MODEL}"
    router_agent = create_request_router(llm)

    prompt = REQUEST_ROUTER_PROMPT.replace("{user_message}", user_message)

    task = Task(
        description=prompt,
        expected_output="JSON object with pipeline, confidence, reason, extracted_params",
        agent=router_agent,
    )

    crew = Crew(
        agents=[router_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )

    logger.info("🔀 [ROUTER] Routing request: %s", user_message[:100])

    try:
        result = crew.kickoff()
        raw = str(result)
        return _parse_router_output(raw, user_message)
    except Exception as exc:
        logger.warning("Router failed, defaulting to chat_pipeline: %s", exc)
        return {
            "pipeline": "chat_pipeline",
            "confidence": 0.5,
            "reason": f"Router error — defaulting to chat: {exc}",
            "extracted_params": {},
        }


def _parse_router_output(raw: str, user_message: str) -> dict:
    """Parse the router agent's JSON output."""
    # Try to find JSON in the output
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            # Validate pipeline value
            pipeline = parsed.get("pipeline", "chat_pipeline")
            if pipeline not in ("chat_pipeline", "policy_brief_pipeline"):
                pipeline = "chat_pipeline"
            parsed["pipeline"] = pipeline
            return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: keyword-based detection
    return _keyword_fallback(user_message)


def _keyword_fallback(user_message: str) -> dict:
    """Fallback keyword-based routing when LLM parsing fails."""
    msg = user_message.lower()

    policy_keywords = [
        "policy brief", "นโยบาย", "ตรวจราชการ", "เขตสุขภาพ",
        "บทสรุปผู้บริหาร", "executive summary", "เชิงนโยบาย",
    ]

    for kw in policy_keywords:
        if kw in msg:
            return {
                "pipeline": "policy_brief_pipeline",
                "confidence": 0.7,
                "reason": f"keyword match: '{kw}'",
                "extracted_params": {},
            }

    # Check if message mentions supported provinces + policy topics
    for province in SUPPORTED_PROVINCES:
        if province in msg:
            policy_topics = ["สุขภาพจิต", "โภชนาการ", "ncd", "rti", "mental"]
            if any(t in msg for t in policy_topics):
                return {
                    "pipeline": "policy_brief_pipeline",
                    "confidence": 0.6,
                    "reason": f"province '{province}' + policy topic detected",
                    "extracted_params": {"province": province},
                }

    return {
        "pipeline": "chat_pipeline",
        "confidence": 0.8,
        "reason": "default: general chat/data query",
        "extracted_params": {},
    }

"""Request Router Agent: decides which pipeline to use (chat vs policy-brief)."""
import json
import logging
import re

from crewai import Agent, Task, Crew, Process
from src.agents.agent_defaults import agent_retry_kwargs

from src.config import get_settings
from src.tools.notebooklm import SUPPORTED_PROVINCES

logger = logging.getLogger(__name__)


def create_request_router(llm) -> Agent:
    return Agent(
        role="Request Router",
        goal=(
            "วิเคราะห์คำขอของผู้ใช้แล้วตัดสินใจว่าควรใช้ pipeline ไหน: "
            "chat_pipeline (ค้นหา/วิเคราะห์ข้อมูลอุบัติเหตุทั่วไป), "
            "policy_brief_pipeline (สร้าง Policy Brief สาธารณสุขเชิงนโยบาย), หรือ "
            "thaijo_research_pipeline (ทบทวนวรรณกรรมจาก ThaiJO)"
        ),
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญในการจำแนกประเภทคำขอด้านสาธารณสุข "
            "คุณสามารถแยกแยะได้ว่าคำขอเป็น:\n"
            "1) **chat_pipeline** — คำถามทั่วไปเกี่ยวกับข้อมูลอุบัติเหตุ สถิติ กราฟ แนวโน้ม "
            "   หรือคำถามสนทนาทั่วไป\n"
            "2) **policy_brief_pipeline** — คำขอสร้าง Policy Brief, รายงานเชิงนโยบาย, "
            "   รายงานตรวจราชการ, วิเคราะห์ข้อมูลสุขภาพจิต/โภชนาการ/NCD เชิงนโยบาย "
            f"   สำหรับจังหวัดในเขตสุขภาพที่ 10 ({', '.join(SUPPORTED_PROVINCES)})\n"
            "3) **thaijo_research_pipeline** — คำขอทบทวนวรรณกรรม, สืบค้นบทความวิชาการ, "
            "   สรุปงานวิจัยจาก ThaiJO (TCI-THAIJO)\n\n"
            "**กฎการตัดสินใจ:**\n"
            "- ถ้ามีคำว่า 'policy brief', 'นโยบาย', 'ตรวจราชการ', 'เขตสุขภาพ' → policy_brief_pipeline\n"
            "- ถ้าถามเกี่ยวกับสุขภาพจิต/โภชนาการ/NCD ของจังหวัดในเขต 10 และต้องการรายงานเชิงนโยบาย → policy_brief_pipeline\n"
            "- ถ้ามีคำว่า 'ทบทวนวรรณกรรม', 'review งานวิจัย', 'สืบค้นบทความ', 'ค้นหางานวิจัย', 'literature review', 'research synthesis', 'หาบทความวิชาการ', 'สรุปงานวิจัย', 'ThaiJO' → thaijo_research_pipeline\n"
            "- ถ้าถามสถิติอุบัติเหตุทั่วไป, จุดเสี่ยง, แนวโน้ม, กราฟ → chat_pipeline\n"
            "- ถ้าเป็นคำถามสนทนาทั่วไป, ทักทาย → chat_pipeline\n"
            "- ถ้าไม่แน่ใจ → chat_pipeline (default)"
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        **agent_retry_kwargs(),
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

### 3. thaijo_research_pipeline
- สำหรับ: ทบทวนวรรณกรรม, สืบค้นบทความวิชาการ, สรุปงานวิจัย
- สำหรับ: Literature review, research synthesis จาก TCI-THAIJO
- Data sources: TCI-THAIJO (Thai Journals Online)
- Output: รายงานทบทวนวรรณกรรม Markdown + APA citations + charts

## คำสำคัญที่ช่วยตัดสินใจ

**→ policy_brief_pipeline:**
- "policy brief", "นโยบาย", "ตรวจราชการ", "เขตสุขภาพ"
- "สร้างรายงาน...เชิงนโยบาย", "วิเคราะห์เชิงระบบ"
- ถ้าระบุจังหวัดในเขต 10 + ถามเรื่องสุขภาพจิตหรือ NCD เชิงนโยบาย
- "executive summary", "บทสรุปผู้บริหาร", "ข้อเสนอแนะเชิงนโยบาย"
- **"แผนการลด", "แผนลด", "แผนป้องกัน", "มาตรการลด", "ลดอุบัติเหตุ ร้อยละ"**
- **ถ้าขอ "แผน" หรือ "มาตรการ" สำหรับจังหวัดในเขต 10 → policy_brief_pipeline เสมอ**

**→ thaijo_research_pipeline:**
- "ทบทวนวรรณกรรม", "review งานวิจัย", "สืบค้นบทความ"
- "ค้นหางานวิจัย", "literature review", "research synthesis"
- "หาบทความวิชาการ", "สรุปงานวิจัย", "ThaiJO"
- ถ้าขอ "ทบทวน", "รวบรวมงานวิจัย", "บทความวิชาการ" → thaijo_research_pipeline

**→ chat_pipeline:**
- "สถิติ", "จำนวน", "กราฟ", "แนวโน้ม", "จุดเสี่ยง"
- คำถามทั่วไป, สนทนา, ถามข้อมูลเบื้องต้น
- จังหวัดนอกเขต 10

**topic mapping ใน extracted_params.topics:**
- มีคำว่า "อุบัติเหตุ", "rti", "ลดอุบัติเหตุ", "การจราจร" → topics: ["rti"]
- มีคำว่า "สุขภาพจิต", "mental", "ซึมเศร้า", "ฆ่าตัวตาย" → topics: ["mental"]
- มีคำว่า "ncd", "โรคไม่ติดต่อ", "เบาหวาน", "โภชนาการ" → topics: ["ncd"]
- ถ้ามีหลาย topic → ระบุทุก topic ที่เกี่ยวข้อง

## ตอบเป็น JSON เท่านั้น:

```json
{{
    "pipeline": "chat_pipeline หรือ policy_brief_pipeline หรือ thaijo_research_pipeline",
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


def route_request(user_message: str, mode: str | None = None) -> dict:
    """Run the Request Router Agent to decide which pipeline to use.

    Args:
        user_message: The user's message text
        mode: Optional mode flag from UI ('short' for short chat)
              If set, bypasses LLM routing and returns the mode directly.

    Returns:
        dict with keys: pipeline, confidence, reason, extracted_params
    """
    # 1. Mode flag bypass: if UI explicitly sets mode, skip LLM routing
    if mode == "short":
        logger.info("🔀 [ROUTER] mode=short → bypassing LLM, using short_chat pipeline")
        return _keyword_fallback(user_message, override_pipeline="short_chat")

    # 2. Auto-detection for short messages (e.g. length <= 60 chars)
    # If the message is very short and doesn't contain "report" or "policy" keywords,
    # we can optionally route to short_chat for speed.
    msg_clean = user_message.strip()
    if len(msg_clean) <= 60 and len(msg_clean) > 0:
        # Check if it's NOT asking for a complex report
        report_keywords = ["รายงาน", "policy brief", "สรุปผู้บริหาร", "วิเคราะห์", "กราฟ", "ตาราง"]
        if not any(kw in msg_clean.lower() for kw in report_keywords):
            logger.info("🔀 [ROUTER] Short message detected (%s chars) → using short_chat", len(msg_clean))
            return {
                "pipeline": "short_chat",
                "confidence": 1.0,
                "reason": f"Short message detected ({len(msg_clean)} chars)",
                "extracted_params": {"topics": _extract_topics_from_message(msg_clean)},
            }

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
        result = kickoff_with_retry(crew)
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
            if pipeline not in ("chat_pipeline", "policy_brief_pipeline", "thaijo_research_pipeline", "short_chat"):
                pipeline = "chat_pipeline"
            parsed["pipeline"] = pipeline
            return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: keyword-based detection
    return _keyword_fallback(user_message)


def _extract_topics_from_message(msg: str) -> list[str]:
    """Map Thai keywords in message to topic codes [rti, mental, ncd]."""
    topics = []
    rti_kw = ["อุบัติเหตุ", "rti", "road traffic", "เสียชีวิต", "ลดอุบัติเหตุ",
              "จุดเสี่ยง", "แผนลด", "การจราจร", "black spot", "haddon"]
    mental_kw = ["สุขภาพจิต", "mental", "ซึมเศร้า", "ฆ่าตัวตาย", "จิตเวช",
                 "ความเครียด", "วิตกกังวล"]
    ncd_kw = ["ncd", "โรคไม่ติดต่อ", "เบาหวาน", "ความดัน", "โรคอ้วน",
              "โภชนาการ", "dm", "ht", "ckd", "อ้วน", "น้ำหนัก"]
    if any(k in msg for k in rti_kw):
        topics.append("rti")
    if any(k in msg for k in mental_kw):
        topics.append("mental")
    if any(k in msg for k in ncd_kw):
        topics.append("ncd")
    return topics or ["rti", "mental", "ncd"]


def _keyword_fallback(user_message: str, override_pipeline: str | None = None) -> dict:
    """Fallback keyword-based routing when LLM parsing fails.

    Args:
        override_pipeline: If set, return this pipeline directly (used by mode flag bypass)
    """
    msg = user_message.lower()

    # Mode flag override (e.g. mode="short" from UI)
    if override_pipeline:
        topics = _extract_topics_from_message(msg)
        return {
            "pipeline": override_pipeline,
            "confidence": 1.0,
            "reason": f"mode flag override: {override_pipeline}",
            "extracted_params": {"topics": topics},
        }

    # Check ThaiJO research keywords first (most specific)
    thaijo_keywords = [
        "ทบทวนวรรณกรรม", "review งานวิจัย", "สืบค้นบทความ",
        "ค้นหางานวิจัย", "literature review", "research synthesis",
        "หาบทความวิชาการ", "สรุปงานวิจัย", "thaijo",
        "ทบทวน", "รวบรวมงานวิจัย", "บทความวิชาการ",
    ]
    for kw in thaijo_keywords:
        if kw in msg:
            topics = _extract_topics_from_message(msg)
            return {
                "pipeline": "thaijo_research_pipeline",
                "confidence": 0.75,
                "reason": f"keyword match: '{kw}'",
                "extracted_params": {"topics": topics},
            }

    policy_keywords = [
        "policy brief", "นโยบาย", "ตรวจราชการ", "เขตสุขภาพ",
        "บทสรุปผู้บริหาร", "executive summary", "เชิงนโยบาย",
        # Planning / reduction plan keywords
        "แผนการลด", "เเผนการลด", "แผนลด", "แผนป้องกัน", "แผนการป้องกัน",
        "ลดลง", "ร้อยละ", "มาตรการ", "ข้อเสนอแนะ",
    ]

    for kw in policy_keywords:
        if kw in msg:
            # Extract province and topics
            province = ""
            for p in SUPPORTED_PROVINCES:
                if p in msg:
                    province = p
                    break
            topics = _extract_topics_from_message(msg)
            return {
                "pipeline": "policy_brief_pipeline",
                "confidence": 0.7,
                "reason": f"keyword match: '{kw}'",
                "extracted_params": {
                    "province": province,
                    "topics": topics,
                },
            }

    # Check if message mentions supported provinces + policy topics
    for province in SUPPORTED_PROVINCES:
        if province in msg:
            topics = _extract_topics_from_message(msg)
            # If any specific health topic detected, route to policy
            policy_topic_kw = ["สุขภาพจิต", "โภชนาการ", "ncd", "rti", "mental",
                                "อุบัติเหตุ", "ลดอุบัติเหตุ", "แผน", "มาตรการ"]
            if any(t in msg for t in policy_topic_kw):
                return {
                    "pipeline": "policy_brief_pipeline",
                    "confidence": 0.65,
                    "reason": f"province '{province}' + policy topic detected",
                    "extracted_params": {"province": province, "topics": topics},
                }

    return {
        "pipeline": "chat_pipeline",
        "confidence": 0.8,
        "reason": "default: general chat/data query",
        "extracted_params": {},
    }

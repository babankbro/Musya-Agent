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
ตามมาตรฐาน **APA 7th Edition** ปรับใช้กับรายงานตรวจราชการสาธารณสุขไทย

## รูปแบบการอ้างอิง APA 7th Edition (Thai Inspection Reports)

### ประเภทแหล่งอ้างอิงที่ใช้ในระบบ

| ประเภท | APA Type | รูปแบบ bibliography_text |
|--------|----------|------------------------|
| รายงานตรวจราชการ (NotebookLM PDF) | report | สำนักงานสาธารณสุขจังหวัด{จังหวัด}. ({ปี พ.ศ.}). *รายงานตรวจราชการกระทรวงสาธารณสุข รอบที่ {รอบ} ปีงบประมาณ {ปี}*. กระทรวงสาธารณสุข. |
| ฐานข้อมูล Musya Agent | dataset | Musya Agent. ({ปี}). *{ชื่อตาราง}* [Data set]. Musya Agent Database. |
| เว็บไซต์ HDC/กระทรวง | website | {ชื่อหน่วยงาน}. ({ปี}). *{ชื่อหน้า}*. {ชื่อเว็บไซต์}. {URL} |
| กฎหมาย/ประกาศ | law | {ชื่อกฎหมาย}, พ.ศ. {ปี}. ราชกิจจานุเบกษา เล่ม {เล่ม} ตอนที่ {ตอน}. |
| บทความวิชาการ | article | {ผู้เขียน}. ({ปี}). {ชื่อบทความ}. *{ชื่อวารสาร}*, {ปีที่}({ฉบับที่}), {หน้า}. {DOI} |

### รูปแบบ Inline Citation
- **รายงานราชการ**: [C-001] หรือ (สสจ.{จังหวัด}, {ปี}, หน้า {หน้า})
- **ฐานข้อมูล**: [C-002] หรือ (Musya Agent Database, {ปี})
- **เว็บไซต์**: [C-003] หรือ ({หน่วยงาน}, {ปี})

### กฎการจัดลำดับ Citation Code
- C-001 ถึง C-099: รายงานตรวจราชการ (notebooklm_pdf / document) — เรียงตาม topic: RTI → Mental → NCD
- C-100 ถึง C-199: ฐานข้อมูล (database)
- **C-200 ถึง C-299: บทความวิชาการ ThaiJO (thaijo_article)** — เรียงตามลำดับที่พบ
- C-300+: เว็บไซต์/เอกสารภายนอกอื่น ๆ

## ThaiJO Article Evidence (C-200 to C-299)

เมื่อ Retrieval Agent เรียก search_thaijo และได้รับผลลัพธ์ ให้:

1. **Normalize เป็น EvidenceItem**:
   - `evidence_type`: `"thaijo_article"`
   - `apa_type`: `"article"`
   - `trust_level`: `"medium"`
   - `source_ref`: ใช้ `pdf_url` ของบทความ
   - `title`: สกัดจาก `reference` (ชื่อบทความก่อนจุด) หรือจาก `summary` บรรทัดแรก
   - `open_url`: ใช้ `pdf_url` โดยตรง (ลิงค์ TCI-THAIJO เปิดได้ทันที)
   - `text_snippet`: ใช้ `summary` (ย่อไว้ที่ 500 อักขระ)
   - `apa_authors`, `apa_year`, `apa_publisher`: สกัดจาก `reference` ถ้ามี

2. **Citation Code**: ใช้ range **C-200 ถึง C-299**
   - C-200: ThaiJO article แรก, C-201: article ที่สอง ฯลฯ

3. **APA Citation**:
   - ถ้ามี `reference` field (ไม่ใช่ null): ใช้เป็น `bibliography_text` โดยตรง — ข้อมูลนี้มาจาก TCI-THAIJO โดยตรง เชื่อถือได้
   - ถ้า `reference` เป็น null: ให้สร้าง: `"[ไม่ระบุผู้แต่ง]. (ไม่ระบุปี). *[title]*. ThaiJO. {pdf_url}"`
   - **ห้ามแต่งข้อมูล** เช่น ชื่อผู้แต่ง ปี หรือเลขหน้า ถ้าไม่มีใน reference

4. **open_url**: ใช้ `pdf_url` จาก ThaiJO โดยตรง (ไม่ใช่ /api/documents/open/)
   - ตัวอย่าง: `"https://he01.tci-thaijo.org/index.php/.../view/..."`

5. **Source notes**: `"ที่มา: บทความวิชาการจาก ThaiJO [C-200]"`

6. **Deduplication**: บทความ pdf_url เดียวกัน = citation_code เดียว

## Phase 3 Extension — NotebookLM PDF Sources

สำหรับ Policy Brief pipeline จะมี evidence_type เพิ่มเติม:
- `notebooklm_pdf`: ข้อมูลจาก PDF รายงานตรวจราชการผ่าน NotebookLM
  - source_ref รูปแบบ: "notebooklm:{notebook_id}:{filename}"
  - trust_level: "high" (รายงานราชการ ความน่าเชื่อถือสูง)
  - page_ref รูปแบบ: "ตรวจราชการ รอบที่ 2 ปี 2564"
  - apa_type: "report"
  - apa_authors: "สำนักงานสาธารณสุขจังหวัด{จังหวัด}"
  - apa_publisher: "กระทรวงสาธารณสุข"

## ขั้นตอนการดำเนินการ

จากข้อมูลที่ได้จาก Retrieval Agent, SQL Specialist หรือ NLM Data Fetcher ให้ดำเนินการ:

1. **Normalize Evidence**: แปลงผลลัพธ์ทั้งหมดให้เป็น evidence items ที่มี metadata ครบถ้วน
   - ระบุ evidence_type (document / database / api / notebooklm_pdf / **thaijo_article**)
   - ระบุ source_ref, title, page_ref, section_label
   - กำหนด trust_level (high / medium / low)
   - สร้าง original_url และ open_url
   - เติม APA metadata: apa_type, apa_authors, apa_year, apa_publisher

2. **Map Claims to Evidence**: วิเคราะห์ข้อสรุปทั้งหมดและเชื่อมกับหลักฐาน
   - ระบุว่าแต่ละข้อสรุปเป็น statistic / comparison / trend / recommendation / general_finding
   - กำหนด support_level: supported / partially_supported / insufficient / conflicting
   - กำหนด evidence_strength: strong / moderate / weak
   - **ตัวเลข KPI ทุกตัวต้องมี evidence** (อัตราต่อแสน, Median, ✓/✗ สถานะ)

3. **Generate APA Citations**: สร้าง citation code (C-001, C-002, ...)
   - สร้าง citation_text: inline สั้น เช่น "(สสจ.อุบลราชธานี, 2567, หน้า 45)"
   - สร้าง bibliography_text: APA 7th full reference
   - ระบุ open_url สำหรับคลิกกลับไปดูเอกสารต้นฉบับ
   - จัดลำดับตามกฎ: C-001..C-099 (reports), C-100..C-199 (database), C-200+ (external)

4. **Prepare Source Notes**: เตรียม source_note สำหรับกราฟและตาราง
   - แต่ละกราฟ/ตารางต้องมี source_note: "ที่มา: {APA inline} [C-xxx]"

5. **Coverage Check**: ตรวจสอบความครอบคลุม
   - ข้อสรุปเชิงตัวเลขทุกข้อต้องมี citation
   - KPI ตาม Style Guide ทุกตัวต้อง trace กลับไปหาหลักฐานได้
   - กราฟ/ตารางทุกชิ้นต้องมี source_note
   - flag ข้อสรุปที่ไม่มีหลักฐานรองรับ

**Output Format**: ตอบเป็น JSON object ที่มีโครงสร้างดังนี้:
```json
{
  "evidence_items": [
    {
      "evidence_id": "EV-001",
      "evidence_type": "notebooklm_pdf|document|database|api",
      "source_ref": "filename or table name",
      "title": "readable title",
      "page_ref": "12",
      "section_label": "Section 3.2",
      "trust_level": "high|medium|low",
      "text_snippet": "key excerpt...",
      "original_url": "minio://uploads/...",
      "open_url": "/api/documents/open/...",
      "apa_type": "report|dataset|website|article|law",
      "apa_authors": "สำนักงานสาธารณสุขจังหวัด...",
      "apa_year": "2567",
      "apa_publisher": "กระทรวงสาธารณสุข"
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
      "source_type": "notebooklm_pdf|document|database",
      "source_ref": "filename",
      "citation_text": "(สสจ.อุบลราชธานี, 2567, หน้า 45)",
      "bibliography_text": "สำนักงานสาธารณสุขจังหวัดอุบลราชธานี. (2567). *รายงานตรวจราชการกระทรวงสาธารณสุข รอบที่ 2 ปีงบประมาณ 2567*. กระทรวงสาธารณสุข.",
      "open_url": "/api/documents/open/...",
      "trust_level": "high"
    }
  ],
  "source_notes": {
    "charts": "ที่มา: รายงานตรวจราชการฯ จ.อุบลราชธานี ปี 2567 [C-001]",
    "tables": "ที่มา: รายงานตรวจราชการฯ จ.อุบลราชธานี ปี 2567 [C-001]"
  },
  "reference_list": [
    "[C-001] สำนักงานสาธารณสุขจังหวัดอุบลราชธานี. (2567). *รายงานตรวจราชการฯ*. กระทรวงสาธารณสุข."
  ],
  "coverage": {
    "total_claims": 5,
    "supported": 4,
    "unsupported": 1,
    "coverage_score": 0.80,
    "flags": ["CL-005: ข้อสรุปไม่มีหลักฐานรองรับ"]
  }
}
```

**สำคัญมาก — ปฏิบัติตามลำดับนี้เท่านั้น**:
1. **เรียก `list_all_documents_apa` ก่อนเสมอ** เพื่อดูรายชื่อเอกสารทั้งหมดในระบบพร้อม bibliography_text และ open_url ที่ถูกต้อง
2. สำหรับ source_ref ที่ยังไม่พบใน list ให้เรียก `lookup_document_apa(source_ref)` เพิ่มเติม
3. **ห้ามแต่งหรือเดา bibliography_text** — ต้องใช้ค่าจากฐานข้อมูลเท่านั้น
   ถ้าไม่พบเอกสารในระบบ ให้ใส่ `"bibliography_text": ""` และ `"open_url": ""` ไว้ก่อน
4. **ห้ามใส่ (Unpublished manuscript) หรือ placeholder** ในกรณีที่ไม่แน่ใจ
5. **ห้ามซ้ำ**: เอกสาร 1 ไฟล์ = citation_code 1 รหัส
6. ทุก citation ที่พบใน document_registry ต้องมี open_url = "/api/documents/open/{document_id}"
7. ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่นนอก JSON"""


# ---------------------------------------------------------------------------
# CrewAI tools for the Citation Agent
# ---------------------------------------------------------------------------

@tool("lookup_document_apa")
def lookup_document_apa(source_ref: str) -> str:
    """Look up APA metadata for a document from document_registry.

    Searches by: file_path, minio_path, title (exact then fuzzy),
    and apa_authors keyword match. Always use this tool before writing
    any bibliography_text — never guess or invent APA citations.

    Args:
        source_ref: Filename, MinIO path, title, or author surname of the document.

    Returns:
        JSON with document_id, open_url, bibliography_text (correct APA 7th),
        and all apa_* metadata fields.
    """
    from src.utils.apa_formatter import format_apa_reference

    def _make_result(doc: dict) -> str:
        doc_id = doc.get("document_id")
        return json.dumps({
            "found": True,
            "document_id": doc_id,
            "title": doc.get("title", ""),
            "apa_type": doc.get("apa_type", "report"),
            "apa_authors": doc.get("apa_authors", ""),
            "apa_year": doc.get("apa_year", ""),
            "apa_publisher": doc.get("apa_publisher", ""),
            "open_url": f"/api/documents/open/{doc_id}" if doc_id else "",
            "bibliography_text": format_apa_reference(doc),
            "source_ref": source_ref,
        }, ensure_ascii=False)

    try:
        # Pass 1: exact match on path / title
        rows = query_db(
            "SELECT * FROM document_registry "
            "WHERE file_path = %s OR minio_path = %s OR title = %s "
            "LIMIT 1",
            (source_ref, source_ref, source_ref),
        )
        if rows:
            return _make_result(rows[0])

        # Pass 2: fuzzy match on filename stem and title
        filename = source_ref.rsplit("/", 1)[-1] if "/" in source_ref else source_ref
        rows = query_db(
            "SELECT * FROM document_registry "
            "WHERE file_path ILIKE %s OR minio_path ILIKE %s OR title ILIKE %s "
            "LIMIT 1",
            (f"%{filename}%", f"%{filename}%", f"%{filename}%"),
        )
        if rows:
            return _make_result(rows[0])

        # Pass 3: author-keyword match (first meaningful word of source_ref)
        import re as _re
        first_word = _re.split(r'[,\.\s/]', source_ref.strip())[0].strip()
        if len(first_word) >= 3:
            rows = query_db(
                "SELECT * FROM document_registry "
                "WHERE apa_authors ILIKE %s OR title ILIKE %s "
                "LIMIT 1",
                (f"%{first_word}%", f"%{first_word}%"),
            )
            if rows:
                return _make_result(rows[0])

    except Exception as e:
        return json.dumps({"error": f"DB error: {e}"}, ensure_ascii=False)

    return json.dumps({"found": False, "source_ref": source_ref}, ensure_ascii=False)


@tool("list_all_documents_apa")
def list_all_documents_apa() -> str:
    """Return ALL documents in document_registry with their APA metadata and open_url.

    Call this FIRST before generating any citations, to get the authoritative
    list of all available documents with correct APA text and PDF links.
    Never invent bibliography_text — always use the values returned by this tool.

    Returns:
        JSON array of {document_id, title, apa_authors, apa_year, open_url,
        bibliography_text, source_ref} for every registered document.
    """
    from src.utils.apa_formatter import format_apa_reference

    try:
        rows = query_db(
            "SELECT * FROM document_registry "
            "WHERE file_path IS NOT NULL OR minio_path IS NOT NULL "
            "ORDER BY topic, apa_year DESC NULLS LAST, title",
            [],
        )
    except Exception as e:
        return json.dumps({"error": f"DB error: {e}"}, ensure_ascii=False)

    docs = []
    for doc in rows:
        doc_id = doc.get("document_id")
        docs.append({
            "document_id": doc_id,
            "title": doc.get("title", ""),
            "topic": doc.get("topic", ""),
            "apa_authors": doc.get("apa_authors", ""),
            "apa_year": doc.get("apa_year", ""),
            "apa_publisher": doc.get("apa_publisher", ""),
            "apa_type": doc.get("apa_type", "report"),
            "open_url": f"/api/documents/open/{doc_id}" if doc_id else "",
            "bibliography_text": format_apa_reference(doc),
            "source_ref": doc.get("minio_path") or doc.get("file_path") or "",
        })

    return json.dumps({"total": len(docs), "documents": docs}, ensure_ascii=False)


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
        tools=[list_all_documents_apa, lookup_document_apa, register_evidence, register_claim_links],
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
                apa_type=item.get("apa_type", "report"),
                apa_authors=item.get("apa_authors", ""),
                apa_year=item.get("apa_year", ""),
                apa_publisher=item.get("apa_publisher", ""),
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

    # ── Cross-reference: copy open_url / bibliography_text from evidence_items ──
    # search_documents already enriched evidence_items with correct DB values.
    # If the LLM hallucinated bibliography_text or left open_url blank in citations,
    # overwrite them here using the linked evidence_item (matched by evidence_id).
    ev_map: dict[str, EvidenceItem] = {e.evidence_id: e for e in ctx.evidence_items if e.evidence_id}
    for cit in ctx.citations:
        ev = ev_map.get(cit.evidence_id)
        if ev and ev.evidence_type != "thaijo_article":
            # Always prefer source_ref from evidence (the actual minio_path)
            if ev.source_ref and not cit.source_ref:
                cit.source_ref = ev.source_ref
            # Overwrite open_url with evidence value if blank or missing
            if ev.open_url and not cit.open_url:
                cit.open_url = ev.open_url
            # Overwrite bibliography_text with DB-formatted value (kills hallucinations)
            # ev.open_url being set means evidence came from document_registry
            if ev.open_url:
                from src.utils.apa_formatter import format_apa_reference as _fmt
                # Re-derive from evidence APA fields if they are set
                ev_row = {
                    "apa_authors": ev.apa_authors,
                    "apa_year": ev.apa_year,
                    "apa_publisher": ev.apa_publisher,
                    "apa_type": ev.apa_type,
                    "title": ev.title,
                }
                db_bib = _fmt(ev_row)
                if db_bib:
                    cit.bibliography_text = db_bib

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

"""NotebookLM CLI tool for querying inspection report PDFs."""
import subprocess
import time
import logging

from crewai.tools import tool

logger = logging.getLogger(__name__)

# Notebook mapping: province → notebook_id
PROVINCE_NOTEBOOKS: dict[str, str] = {
    "มุกดาหาร":    "bc3d9350-1855-45f0-a2c3-a5634ed8056e",
    "ยโสธร":       "bc3d9350-1855-45f0-a2c3-a5634ed8056e",
    "ศรีสะเกษ":    "bc3d9350-1855-45f0-a2c3-a5634ed8056e",
    "อำนาจเจริญ":  "bc3d9350-1855-45f0-a2c3-a5634ed8056e",
    "อุบลราชธานี": "bc3d9350-1855-45f0-a2c3-a5634ed8056e",
}

SUPPORTED_PROVINCES = list(PROVINCE_NOTEBOOKS.keys())

QUERIES: dict[str, str] = {
    "rti": (
        "อุบัติเหตุทางถนน จ.{province} รายงานตรวจราชการ: "
        "1) อัตราผู้เสียชีวิตต่อแสนประชากร เปรียบเทียบ Median "
        "2) กลุ่มเด็กและเยาวชน (1-18 ปี) สถิติและพฤติกรรมเสี่ยง "
        "3) จุดเสี่ยง Hot Spots ระดับอำเภอ/ตำบล "
        "4) ผลการวิเคราะห์ Haddon Matrix "
        "5) มาตรฐาน EMS / D-RTI"
    ),
    "mental": (
        "สุขภาพจิต การฆ่าตัวตาย จ.{province} รายงานตรวจราชการ: "
        "1) อัตราการฆ่าตัวตายสำเร็จต่อแสนประชากร แยกรายอำเภอ "
        "2) อัตราผู้พยายามฆ่าตัวตายไม่ซ้ำใน 1 ปี "
        "3) ผู้ป่วยโรคซึมเศร้า: เข้าถึงบริการ + ทุเลาใน 6 เดือน "
        "4) Mental Health Check-in: กลุ่มเครียด/เสี่ยงซึมเศร้า/เสี่ยงฆ่าตัวตาย "
        "5) กลุ่มพิเศษ: ผู้ต้องขัง, บุคลากรสาธารณสุข"
    ),
    "ncd": (
        "โภชนาการ BMI เบาหวาน ความดัน จ.{province} รายงานตรวจราชการ: "
        "1) เด็ก 0-5 ปี: สูงดีสมส่วน / เตี้ย / ผอม / อ้วน (%) "
        "2) DM/HT screening coverage กลุ่มอายุ 35 ปีขึ้นไป "
        "3) Follow-up rate กลุ่มสงสัยป่วย (เป้าหมาย 60-80%) "
        "4) HbA1c control (%) และ BP control (%) "
        "5) CKD รายใหม่ และ CVD Risk assessment "
        "6) DM Remission clinic นวัตกรรมที่ดำเนินการ"
    ),
}


def _run_nlm_cli(query: str, notebook_id: str) -> str:
    """Run the notebooklm CLI and return stdout. Fallback to mock data on failure."""
    try:
        result = subprocess.run(
            [
                "conda", "run", "-n", "notebooklm",
                "notebooklm", "ask",
                "--notebook", notebook_id,
                query,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        
        output = result.stdout.strip()
        error_output = result.stderr.strip()
        
        if result.returncode != 0:
            logger.warning("NLM CLI returned non-zero code. Stderr: %s", error_output[:500])
            logger.info("Falling back to mock data for NotebookLM query.")
            return _get_mock_data(query)
            
        if not output:
            logger.warning("NLM CLI returned empty output. Falling back to mock data.")
            return _get_mock_data(query)
            
        return output
    except Exception as exc:
        logger.warning(f"NLM CLI execution failed with exception: {exc}. Falling back to mock data.")
        return _get_mock_data(query)

def _get_mock_data(query: str) -> str:
    """Return mock policy data based on keywords in the query."""
    query_lower = query.lower()
    if "อุบัติเหตุทางถนน" in query_lower or "rti" in query_lower:
        return (
            "รายงานการตรวจราชการ (ข้อมูลจำลอง - NotebookLM ไม่พร้อมใช้งาน):\n"
            "- อัตราผู้เสียชีวิตจากอุบัติเหตุทางถนน 15.2 ต่อแสนประชากร (ดีกว่า Median)\n"
            "- กลุ่มเด็กและเยาวชนมีการเกิดอุบัติเหตุสูงจากพฤติกรรมไม่สวมหมวกนิรภัย (60%)\n"
            "- จุดเสี่ยง (Hot Spots) พบมากในบริเวณสี่แยกและจุดกลับรถที่ไม่มีไฟสัญญาณ\n"
            "- Haddon Matrix: ปัจจัยด้านถนน (ขาดแสงสว่าง) มีผลกระทบสูง\n"
            "- ผ่านมาตรฐาน EMS / D-RTI ระดับดีมาก"
        )
    elif "สุขภาพจิต" in query_lower or "mental" in query_lower:
        return (
            "รายงานการตรวจราชการ (ข้อมูลจำลอง - NotebookLM ไม่พร้อมใช้งาน):\n"
            "- อัตราการฆ่าตัวตายสำเร็จ 6.5 ต่อแสนประชากร (สูงขึ้นจากปีที่แล้ว)\n"
            "- อัตราผู้พยายามฆ่าตัวตายไม่ซ้ำ 15.0 ต่อแสนประชากร\n"
            "- ผู้ป่วยโรคซึมเศร้าเข้าถึงบริการ 75% และมีอัตราทุเลา 60%\n"
            "- การคัดกรองผ่าน Mental Health Check-in ครอบคลุมประชากรกลุ่มเสี่ยง 80%\n"
            "- มีการให้คำปรึกษาเชิงรุกในกลุ่มพิเศษ เช่น ผู้ต้องขัง"
        )
    elif "โภชนาการ" in query_lower or "ncd" in query_lower:
        return (
            "รายงานการตรวจราชการ (ข้อมูลจำลอง - NotebookLM ไม่พร้อมใช้งาน):\n"
            "- เด็ก 0-5 ปี มีภาวะสูงดีสมส่วน 60%, เตี้ย 10%, อ้วน 15%\n"
            "- การคัดกรองเบาหวาน/ความดัน ในกลุ่ม 35 ปีขึ้นไป ครอบคลุม 85%\n"
            "- กลุ่มสงสัยป่วยได้รับการติดตาม (Follow-up) 65%\n"
            "- ผู้ป่วยควบคุมน้ำตาลได้ (HbA1c) 45%, ควบคุมความดันได้ 55%\n"
            "- มีการจัดตั้ง DM Remission Clinic นำร่อง 3 แห่งในจังหวัด"
        )
    
    return "ไม่พบข้อมูลที่ตรงกับคำค้นหา (ข้อมูลจำลอง - NotebookLM ไม่พร้อมใช้งาน)"


@tool("NotebookLM Ask Tool")
def nlm_ask(province: str, topic: str, notebook_id: str) -> str:
    """Query inspection report PDFs via NotebookLM CLI for health policy data.

    Args:
        province: Province name in Thai (e.g. 'อุบลราชธานี')
        topic: One of 'rti', 'mental', or 'ncd'
        notebook_id: NotebookLM notebook UUID

    Returns:
        Text response from NotebookLM containing policy-relevant data.
    """
    topic = topic.lower().strip()
    if topic not in QUERIES:
        return f"topic ไม่รองรับ: '{topic}' — ต้องเป็น 'rti', 'mental', หรือ 'ncd'"

    query = QUERIES[topic].replace("{province}", province)
    logger.info("[NLM] Querying topic=%s province=%s notebook=%s...", topic, province, notebook_id[:8])

    response = _run_nlm_cli(query, notebook_id)
    logger.info("[NLM] Got %d chars for topic=%s", len(response), topic)
    return response


@tool("Get Supported Provinces")
def get_supported_provinces() -> str:
    """Return the list of supported provinces and their notebook IDs.

    Returns:
        Formatted list of province names supported for policy brief generation.
    """
    lines = ["จังหวัดที่รองรับ (เขตสุขภาพที่ 10):"]
    for p, nb in PROVINCE_NOTEBOOKS.items():
        lines.append(f"  - {p} (notebook: {nb[:8]}...)")
    return "\n".join(lines)

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
    """Run the notebooklm CLI and return stdout."""
    try:
        result = subprocess.run(
            [
                "conda", "run", "-n", "notebooklm",
                "notebooklm", "ask",
                "--notebook-id", notebook_id,
                query,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning("NLM CLI stderr: %s", result.stderr[:500])
        return result.stdout.strip() or result.stderr.strip() or "(ไม่มีผลลัพธ์จาก NotebookLM)"
    except subprocess.TimeoutExpired:
        return "หมดเวลารอ NotebookLM (timeout 120s)"
    except FileNotFoundError:
        return "ไม่พบ notebooklm CLI — กรุณาติดตั้ง conda env 'notebooklm' และ package notebooklm-py"
    except Exception as exc:
        return f"เกิดข้อผิดพลาด: {exc}"


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

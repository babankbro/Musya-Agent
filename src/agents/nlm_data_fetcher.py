"""Agent A1 — NLM Data Fetcher: queries NotebookLM for all 3 topics."""
import json
import logging
import time

from crewai import Agent, Task
from src.agents.agent_defaults import agent_retry_kwargs

from src.tools.notebooklm import nlm_ask, get_supported_provinces, PROVINCE_NOTEBOOKS, QUERIES

logger = logging.getLogger(__name__)

NLM_FETCHER_PROMPT = """คุณคือ NLM Data Fetcher Agent ทำหน้าที่ดึงข้อมูลจากรายงานตรวจราชการสาธารณสุข
ผ่านเครื่องมือ NotebookLM สำหรับจังหวัดและหัวข้อที่กำหนด

## โครงสร้างรายงานตรวจราชการ (ที่ต้องดึงข้อมูลตาม)

รายงานตรวจราชการเขียนตามแบบแผน 4 ส่วนสำหรับทุกหัวข้อ:
1. สถานการณ์และสภาพปัญหา (Situation Analysis) — สถิติย้อนหลัง 3-5 ปี อัตราต่อแสนประชากร
2. มาตรการดำเนินการ (Measures & Interventions) — กลยุทธ์ คณะทำงาน เทคโนโลยี
3. ผลการดำเนินงาน (Performance Results) — ตัวเลขเทียบเป้าหมาย ผ่าน/ไม่ผ่าน
4. ปัญหา อุปสรรค ข้อเสนอแนะ (GAP Analysis) — ข้อจำกัด + แนวทางพัฒนา

**หลักการตัวเลข:**
- ใช้อัตราต่อแสนประชากร (ไม่ใช่แค่จำนวนนับ)
- Baseline ใช้ค่ามัธยฐาน (Median) ย้อนหลัง 3-5 ปี
- คะแนนประเมิน = ปริมาณ 70% + คุณภาพ 30% (Rubric 5 ระดับ)

**ขั้นตอน:**
1. ตรวจสอบว่า province อยู่ใน supported list (ใช้ get_supported_provinces ก่อน)
2. ดึงข้อมูลทีละ topic โดยใช้ nlm_ask(province, topic, notebook_id)
   - topic "rti": อุบัติเหตุทางถนน
   - topic "mental": สุขภาพจิต
   - topic "ncd": โภชนาการและ NCDs
3. รวบรวมผลลัพธ์ทั้ง 3 topic และส่งออกเป็น JSON

## ตัวชี้วัดบังคับที่ต้องดึงให้ครบ

### RTI:
- เด็ก 1-18 ปี เสียชีวิต/บาดเจ็บ (เป้า: ลดลง ≥3% จาก Median 3 ปี)
- ผู้เสียชีวิตภาพรวม (เป้า: ลดลง ≥5% จาก Median 5 ปี หรือ ≤16 ต่อแสน)
- Triage level 1 ตายภายใน 24 ชม. (เป้า ≤12%)
- Severe TBI Mortality (เป้า <30%)
- 4 มาตรการ: บริหารจัดการ(ศปถ./พชอ.), จัดการข้อมูล(3ฐาน), ป้องกัน(ด่าน/รณรงค์/จุดเสี่ยง), รักษา(EMS/ER/Refer)
- Haddon Matrix, จุดเสี่ยง Black Spot รายอำเภอ

### Mental Health:
- อัตราฆ่าตัวตายสำเร็จ (เป้า ≤8.0 ต่อแสน)
- ไม่กลับมาทำร้ายซ้ำใน 1 ปี (เป้า ≥90-95%)
- เข้าถึงบริการ (เป้า ≥65-70%)
- ซึมเศร้าเข้าถึงบริการ (เป้า ≥71-80%)
- ซึมเศร้าทุเลาใน 6 เดือน (เป้า ≥55%)
- เครื่องมือ: Mental Health Check-in, 2Q/8Q/9Q, "3ส Plus", วัคซีนใจ
- Psychological Autopsy, อำเภอที่อัตราสูง (เทียบเส้น Target 8.0)

### NCD:
- เด็ก 0-5 ปี สูงดีสมส่วน (เป้า ≥62-64%)
- วัยทำงาน BMI ปกติ (เป้า ≥50-54%)
- คัดกรอง DM/HT อายุ 35+ (เป้า ≥90%)
- Follow-up สงสัย DM (เป้า ≥60-72%) / HT (เป้า ≥70-85%)
- HbA1c ควบคุมได้ (เป้า ≥40-50%) / BP ควบคุมได้ (เป้า ≥60%)
- CKD รายใหม่, CVD Risk
- กรอบ: ต้นน้ำ-กลางน้ำ-ปลายน้ำ, DM Remission clinic

**Output Format:**
```json
{
  "province": "ชื่อจังหวัด",
  "notebook_id": "UUID",
  "topics_fetched": ["rti", "mental", "ncd"],
  "rti": {
    "raw_text": "ข้อมูลดิบจาก NotebookLM",
    "situation_analysis": "สถานการณ์ สถิติย้อนหลัง",
    "death_rate_per_100k": "อัตราเสียชีวิตต่อแสน",
    "median_baseline": "ค่า Median ย้อนหลัง",
    "median_comparison": "สูงกว่า/ต่ำกว่า Median",
    "youth_1_18_stats": "สถิติเด็ก 1-18 ปี เทียบเป้าลดลง ≥3%",
    "triage1_mortality": "Triage 1 ตาย 24 ชม. เทียบเป้า ≤12%",
    "severe_tbi_mortality": "Severe TBI เทียบเป้า <30%",
    "risk_behaviors": "พฤติกรรมเสี่ยง: ไม่สวมหมวก%, เมาแล้วขับ%",
    "hotspots": ["จุดเสี่ยงรายอำเภอ"],
    "haddon_matrix": "ผลวิเคราะห์ Haddon Matrix",
    "four_measures": "4 มาตรการ",
    "ems_standard": "มาตรฐาน EMS/D-RTI",
    "performance_vs_target": "ผลงาน เทียบ เป้าหมาย ผ่าน/ไม่ผ่าน",
    "problems_and_gaps": "ปัญหา อุปสรรค ข้อเสนอแนะ"
  },
  "mental": {
    "raw_text": "ข้อมูลดิบจาก NotebookLM",
    "situation_analysis": "สถานการณ์ แนวโน้มย้อนหลัง",
    "suicide_rate_per_100k": "อัตราฆ่าตัวตายต่อแสน เทียบเป้า ≤8.0",
    "no_repeat_rate_1yr": "ไม่ซ้ำใน 1 ปี เทียบเป้า ≥90-95%",
    "suicide_attempt_access": "เข้าถึงบริการ เทียบเป้า ≥65-70%",
    "depression_access": "ซึมเศร้าเข้าถึงบริการ เทียบเป้า ≥71-80%",
    "depression_remission_6m": "ทุเลาใน 6 เดือน เทียบเป้า ≥55%",
    "checkin_results": "ผล Mental Health Check-in",
    "screening_tools": "เครื่องมือ: 2Q/8Q/9Q, 3ส Plus, วัคซีนใจ",
    "psychological_autopsy": "ผล Psychological Autopsy",
    "district_breakdown": "อำเภอที่อัตราสูง เทียบเส้น Target 8.0",
    "vulnerable_groups": "กลุ่มเปราะบาง (demographic framing)",
    "performance_vs_target": "ผลงาน เทียบ เป้าหมาย ผ่าน/ไม่ผ่าน",
    "problems_and_gaps": "ปัญหา อุปสรรค ข้อเสนอแนะ"
  },
  "ncd": {
    "raw_text": "ข้อมูลดิบจาก NotebookLM",
    "situation_analysis": "สถานการณ์ ระบาดวิทยาย้อนหลัง",
    "child_0_5_growth": "เด็ก 0-5 ปี สูงดีสมส่วน เทียบเป้า ≥62-64%",
    "working_age_bmi": "วัยทำงาน BMI ปกติ เทียบเป้า ≥50-54%",
    "dm_screening_coverage": "คัดกรอง DM 35+ เทียบเป้า ≥90%",
    "ht_screening_coverage": "คัดกรอง HT 35+ เทียบเป้า ≥90%",
    "dm_followup_rate": "Follow-up สงสัย DM เทียบเป้า ≥60-72%",
    "ht_followup_rate": "Follow-up สงสัย HT เทียบเป้า ≥70-85%",
    "hba1c_controlled": "HbA1c ควบคุมได้ เทียบเป้า ≥40-50%",
    "bp_controlled": "BP ควบคุมได้ เทียบเป้า ≥60%",
    "ckd_new_cases": "CKD รายใหม่",
    "cvd_risk": "CVD Risk assessment",
    "upstream_midstream_downstream": "มาตรการ ต้นน้ำ/กลางน้ำ/ปลายน้ำ",
    "dm_remission_model": "DM Remission / NCD Clinic Plus นวัตกรรม",
    "district_performance": "ผลงานรายอำเภอ",
    "performance_vs_target": "ผลงาน เทียบ เป้าหมาย ผ่าน/ไม่ผ่าน",
    "problems_and_gaps": "ปัญหา อุปสรรค ข้อเสนอแนะ"
  }
}
```

**สำคัญ**: ดึงข้อมูลทีละ topic และรอ 2-3 วินาทีระหว่าง query เพื่อไม่ให้ rate limit
ตอบเป็น JSON เท่านั้น"""


def create_nlm_data_fetcher(llm: str) -> Agent:
    """Create Agent A1 — NLM Data Fetcher."""
    return Agent(
        role="NotebookLM Health Data Fetcher",
        goal=(
            "ดึงข้อมูลสาธารณสุขจากรายงานตรวจราชการผ่าน NotebookLM สำหรับ 3 หัวข้อ: "
            "RTI (อุบัติเหตุทางถนน), Mental Health (สุขภาพจิต), NCD (โรคไม่ติดต่อเรื้อรัง) "
            "และส่งออกเป็น structured JSON พร้อมข้อมูลดิบและตัวชี้วัดสำคัญ"
        ),
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญด้านการดึงข้อมูลสาธารณสุขจากรายงานตรวจราชการ "
            "คุณรู้จักโครงสร้างรายงานตรวจราชการสาธารณสุข เขตสุขภาพที่ 10 เป็นอย่างดี "
            "คุณดึงข้อมูลอย่างเป็นระบบ ครบถ้วน และจัดรูปแบบให้ Analyst agents "
            "สามารถนำไปวิเคราะห์ต่อได้ทันที"
        ),
        tools=[nlm_ask, get_supported_provinces],
        llm=llm,
        verbose=True,
        max_iter=10,
        **agent_retry_kwargs(),
    )


def fetch_nlm_data_direct(province: str, topics: list[str], notebook_id: str) -> dict:
    """Directly fetch NLM data without CrewAI (for use in orchestrator pre-processing).

    Calls the NLM CLI for each topic with a 2-second delay between requests.
    Returns a structured dict matching the NLM Fetcher output schema.
    """
    result: dict = {
        "province": province,
        "notebook_id": notebook_id,
        "topics_fetched": [],
    }

    for topic in topics:
        if topic not in QUERIES:
            logger.warning("Skipping unknown topic: %s", topic)
            continue

        logger.info("[NLM Direct] Fetching topic=%s for province=%s", topic, province)
        raw = nlm_ask.run({"province": province, "topic": topic, "notebook_id": notebook_id})  # type: ignore[attr-defined]
        result[topic] = {"raw_text": raw}
        result["topics_fetched"].append(topic)

        if topic != topics[-1]:
            time.sleep(2)

    return result

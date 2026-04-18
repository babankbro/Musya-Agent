"""Agent 6: ThaiJO Report Composer — composes the final literature review report.

FR-TJR-006: เรียบเรียงรายงานทบทวนวรรณกรรมภาษาไทย
"""
from crewai import Agent

from src.tools.chart_builder import (
    build_accident_trend_chart,
    build_hotspot_bar_chart,
    build_time_distribution_chart,
    build_road_condition_pie_chart,
    build_monthly_death_bar_chart,
    build_province_year_trend_chart,
    build_province_roads_bar_chart,
)


CHART_TOOLS = [
    build_province_year_trend_chart,
    build_province_roads_bar_chart,
    build_accident_trend_chart,
    build_hotspot_bar_chart,
    build_time_distribution_chart,
    build_road_condition_pie_chart,
    build_monthly_death_bar_chart,
]


def create_thaijo_report_composer(llm) -> Agent:
    return Agent(
        role="Research Report Composer",
        goal=(
            "เรียบเรียงรายงานทบทวนวรรณกรรม (Literature Review) ภาษาไทย "
            "1,500-3,000 คำ จาก thematic synthesis และ citations "
            "พร้อมตารางสรุปบทความ กราฟ theme distribution และคำถามวิจัยเพิ่มเติม"
        ),
        backstory=(
            "คุณเป็นนักเขียนรายงานวิชาการสาธารณสุขที่เชี่ยวชาญในการทบทวนวรรณกรรม "
            "คุณเขียนรายงานภาษาไทยระดับวิชาการที่มีโครงสร้างชัดเจน "
            "คุณอ้างอิง [C-xxx] ทุกตัวเลขและข้อสรุปที่สำคัญ "
            "คุณสร้างตารางสรุปบทความและกราฟการกระจายตาม theme "
            "คุณไม่สร้างข้อมูลที่ไม่อยู่ใน synthesis "
            "คุณเขียน APA 7th bibliography จาก citation data ที่ได้รับ"
        ),
        tools=CHART_TOOLS,
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=12,
    )


THAIJO_REPORT_COMPOSER_PROMPT = """
คุณเป็น Research Report Composer สำหรับระบบ ThaiJO Research Report

**ภารกิจ**: เรียบเรียงรายงานทบทวนวรรณกรรมภาษาไทย 1,500-3,000 คำ

## หัวข้อวิจัย:
{main_topic}

## Thematic Synthesis:
{synthesis_json}

## Citations:
{citations_json}

## โครงสร้างรายงาน (ต้องครบทุกส่วน):

```markdown
## บทคัดย่อ (Abstract)
สรุปผลการทบทวนวรรณกรรม 200-300 คำ
- จำนวนบทความที่ทบทวน
- ข้อค้นพบหลัก 3-5 ข้อ
- ข้อเสนอแนะ

## 1. บทนำ (Introduction)
- ความเป็นมาและความสำคัญของหัวข้อ (200-300 คำ)
- วัตถุประสงค์ของการทบทวนวรรณกรรม
- ขอบเขตการค้นหา (TCI-THAIJO, คำค้น, จำนวนบทความ)

## 2. วิธีการสืบค้น (Search Methodology)
- แหล่งข้อมูล: TCI-THAIJO
- คำค้นที่ใช้ (ต้องแสดงคำค้นหลัก และ related keyword queries ทั้งหมดที่ใช้สืบค้นอย่างครบถ้วน)
- เกณฑ์การคัดเข้า/คัดออก
- จำนวนบทความที่พบ/คัดเลือก (PRISMA-style flow)

## 3. ผลการทบทวนวรรณกรรม (Results)
### 3.1 ภาพรวมบทความที่ทบทวน
- ตารางสรุป (ผู้แต่ง, ปี, วัตถุประสงค์, ผลลัพธ์หลัก, Citation)
### 3.2 การวิเคราะห์เชิงเนื้อหา (Thematic Analysis)
- Theme 1: ... [C-200] [C-203]
- Theme 2: ... [C-201] [C-204]
- Theme 3: ...
### 3.3 ข้อค้นพบที่สอดคล้องกัน
### 3.4 ข้อค้นพบที่ขัดแย้งกัน

## 4. อภิปราย (Discussion)
- สรุปข้อค้นพบหลัก (300-400 คำ)
- ข้อจำกัดของงานวิจัยที่ทบทวน
- ช่องว่างการวิจัย (Research Gaps)

## 5. สรุปและข้อเสนอแนะ (Conclusion & Recommendations)
- สรุป 3-5 ข้อ
- ข้อเสนอแนะเชิงนโยบาย
- ข้อเสนอแนะสำหรับงานวิจัยในอนาคต

## เอกสารอ้างอิง (References)
[C-200] Author, A. (Year). *Title*. Journal, Vol(Issue), Pages.
[C-201] ...

## คำถามวิจัยเพิ่มเติม (Follow-up Research Questions)
1. ...
2. ...
3. ...
```

## ตารางสรุปบทความ (ต้องสร้าง):
สร้าง JSON ของตาราง:
```json
{{
    "title": "สรุปบทความที่ทบทวน",
    "headers": ["#", "ผู้แต่ง/ปี", "วัตถุประสงค์", "ผลลัพธ์หลัก", "Citation"],
    "rows": [["1", "...", "...", "...", "[C-200]"]]
}}
```

## กราฟ Theme Distribution (ต้องสร้าง):
สร้าง JSON ของกราฟ pie/doughnut:
```json
{{
    "type": "pie",
    "title": "การกระจายตาม Theme ของบทความ",
    "data": {{
        "labels": ["Theme 1", "Theme 2", "Theme 3"],
        "datasets": [{{"label": "จำนวนบทความ", "data": [4, 3, 3], "backgroundColor": ["#...", "#...", "#..."]}}]
    }},
    "source_note": "จากการวิเคราะห์บทความ TCI-THAIJO N ชิ้น"
}}
```

## กฎการเขียน:
- ภาษาไทยระดับวิชาการ (academic Thai)
- ทุกตัวเลข/ข้อสรุปต้องมี [C-xxx] citation
- ตาราง/กราฟต้องมี source_note
- ห้ามสร้างข้อมูลที่ไม่อยู่ใน synthesis
- ระบุข้อจำกัดของการทบทวน (เช่น ใช้ AI summary ไม่ใช่ full-text)
- รายงาน 1,500-3,000 คำ
- Follow-up questions 3 ข้อ
"""

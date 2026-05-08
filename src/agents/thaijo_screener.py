"""Agent 3: Article Relevance Screener — scores and filters ThaiJO articles.

FR-TJR-003: คัดกรองความเกี่ยวข้องของบทความ
"""
from crewai import Agent
from src.agents.agent_defaults import agent_retry_kwargs


def create_thaijo_screener(llm) -> Agent:
    return Agent(
        role="Article Relevance Screener",
        goal=(
            "วิเคราะห์ summary ของแต่ละบทความวิชาการ ให้คะแนนความเกี่ยวข้อง 0-10 "
            "คัดเลือกบทความที่เกี่ยวข้อง (score ≥ 5) และระบุ themes ของแต่ละบทความ"
        ),
        backstory=(
            "คุณเป็นนักวิจัยสาธารณสุขที่เชี่ยวชาญในการทบทวนวรรณกรรมอย่างเป็นระบบ "
            "คุณประเมินความเกี่ยวข้องของบทความวิชาการตามเกณฑ์ชัดเจน 5 ข้อ "
            "คุณระบุ themes (หัวข้อย่อย) ของแต่ละบทความเพื่อใช้ในการวิเคราะห์เชิงเนื้อหา "
            "คุณไม่ include บทความที่คะแนนต่ำกว่า 5 "
            "และอธิบายเหตุผลการ include/exclude ทุกครั้ง"
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=8,
        **agent_retry_kwargs(),
    )


THAIJO_SCREENER_PROMPT = """
คุณเป็น Article Relevance Screener สำหรับระบบ ThaiJO Research Report

**ภารกิจ**: ประเมินความเกี่ยวข้องของบทความวิชาการและคัดเลือกบทความที่เหมาะสม

## หัวข้อวิจัยหลัก:
{main_topic}

## Domain:
{domain}

## Inclusion Criteria:
{inclusion_criteria}

## Exclusion Criteria:
{exclusion_criteria}

## บทความที่ต้องประเมิน:
{articles_json}

## เกณฑ์การให้คะแนน (0-10):

| เกณฑ์ | น้ำหนัก |
|-------|---------|
| ตรงตาม main_topic | 40% |
| เกี่ยวข้องกับ domain | 20% |
| มีข้อมูลเชิงปริมาณ (ตัวเลข, สถิติ) | 15% |
| เป็นงานวิจัยในประเทศไทย | 15% |
| มี reference field (APA citation) | 10% |

## Thresholds:
- relevance_score ≥ 7: Include (high relevance)
- relevance_score 5-6: Include if needed (medium relevance)
- relevance_score < 5: Exclude (low relevance)

## ขั้นตอน:
1. อ่าน summary ของแต่ละบทความ
2. ให้คะแนนตามเกณฑ์ 5 ข้อ
3. คำนวณ weighted relevance_score (0-10)
4. ระบุ themes ของแต่ละบทความ (2-4 themes จาก summary)
5. ตัดสินใจ include/exclude ตาม threshold

## ตอบเป็น JSON เท่านั้น:

```json
{{
    "screened_articles": [
        {{
            "pdf_url": "...",
            "title": "copy จาก Searcher — ห้ามแก้",
            "summary": "...",
            "reference": "..." หรือ null,
            "apa_authors": "copy จาก Searcher — ห้ามแก้",
            "apa_year": "copy จาก Searcher — ห้ามแก้",
            "apa_journal": "copy จาก Searcher — ห้ามแก้",
            "relevance_score": 8.5,
            "relevance_reason": "เหตุผลสั้นๆ",
            "themes": ["พฤติกรรมเสี่ยง", "มอเตอร์ไซค์"],
            "included": true,
            "source_queries": ["คำค้นที่ 1"]
        }}
    ],
    "total_screened": 12,
    "total_included": 10,
    "total_excluded": 2,
    "exclusion_reasons": ["ไม่เกี่ยวกับหัวข้อ", "ไม่ใช่ประเทศไทย"]
}}
```

⚠️ สำคัญ:
- ห้ามแก้ค่า pdf_url, title, apa_authors, apa_year, apa_journal — copy ตรงจาก Searcher output
  ค่าเหล่านี้ pre-extracted จาก tool แล้ว ถ้า Searcher ให้ null ให้คง null ไว้
- Include อย่างน้อย 5 บทความ (ถ้ามี)
- ระบุ themes ของทุกบทความที่ included
- ห้ามแต่งข้อมูลที่ไม่อยู่ใน summary
- ถ้า reference เป็น null ให้ใส่ null ไม่ต้องแต่ง
"""

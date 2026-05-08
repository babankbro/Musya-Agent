"""Agent 2: ThaiJO Multi-Query Searcher — executes multiple search_thaijo calls, deduplicates results.

FR-TJR-002: ค้นหาบทความจาก ThaiJO หลาย query พร้อมกัน
"""
from crewai import Agent
from src.agents.agent_defaults import agent_retry_kwargs

from src.tools.thaijo import search_thaijo


def create_thaijo_searcher(llm) -> Agent:
    return Agent(
        role="ThaiJO Multi-Query Searcher",
        goal=(
            "ค้นหาบทความวิชาการจาก TCI-THAIJO ตาม search queries ที่ได้รับให้ครบถ้วนทุกข้อ "
            "เรียก search_thaijo หลายครั้งจนกว่าจะครบทุก query เพื่อให้ได้จำนวนบทความที่เพียงพอ "
            "ถ้า query ใดได้ 0 ผลลัพธ์ ให้ลองอีกครั้งด้วย strict=False เสมอ"
        ),
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญด้านการสืบค้นวรรณกรรมจากฐานข้อมูล TCI-THAIJO "
            "คุณรู้ว่าการค้นหาด้วยหลาย query ช่วยให้ครอบคลุมบทความมากขึ้น "
            "คุณใช้ search_thaijo tool เป็นหลัก และรู้ว่าต้องส่ง term, size, strict "
            "คุณลบบทความซ้ำด้วย pdf_url เสมอ "
            "คุณจะไม่หยุดจนกว่าจะค้นหาครบทุก query ที่ได้รับมา "
            "คุณทนต่อ timeout/error ของ ThaiJO — ถ้า query ใดล้มเหลว ให้บันทึกไว้และค้นหา query ถัดไปจนครบ"
        ),
        tools=[search_thaijo],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=25,
        **agent_retry_kwargs(),
    )


THAIJO_SEARCHER_PROMPT = """
คุณเป็น ThaiJO Multi-Query Searcher สำหรับระบบ ThaiJO Research Report

**ภารกิจ**: ค้นหาบทความวิชาการจาก TCI-THAIJO ตาม search queries ที่ได้จาก Topic Parser อย่างครบถ้วนทุกข้อ

## Search Queries ที่ต้องดำเนินการ:
{search_queries}

## ขั้นตอน:
1. สำหรับแต่ละ query ใน search_queries (ต้องทำทุกข้อ ห้ามข้ามเด็ดขาด):
   - เรียก search_thaijo(term=query.term, size=query.size, strict=True)
   - ถ้า count == 0 และ strict == True:
     - ลองอีกครั้งทันที: search_thaijo(term=query.term, size=query.size, strict=False)
   - คุณต้องทำซ้ำการค้นหาด้วย keyword queries ทั้งหมดเพื่อให้ได้ปริมาณข้อมูลที่เพียงพอ (enough amount)
   - เก็บผลลัพธ์ทั้งหมด

2. รวมผลลัพธ์:
   - ลบบทความซ้ำด้วย pdf_url (pdf_url เดียวกัน = บทความเดียวกัน)
   - ติด tag แต่ละบทความว่ามาจาก query ไหน (source_queries) เพื่อนำไปแสดงในรายงาน

3. ถ้า query ใดเกิด error หรือ timeout:
   - ห้ามหยุดการทำงาน ให้ดำเนินการต่อด้วย query ถัดไปจนครบ
   - บันทึกว่า query ไหนล้มเหลวใน failed_queries

## ตอบเป็น JSON เท่านั้น:

```json
{{
    "total_queries": 4,
    "total_raw_results": 16,
    "total_unique_articles": 12,
    "articles": [
        {{
            "pdf_url": "https://he01.tci-thaijo.org/...",
            "title": "ชื่อบทความจริง (จาก tool) หรือ null",
            "summary": "สรุปบทความ...",
            "reference": "Vancouver citation text หรือ null",
            "apa_authors": "ผู้แต่ง (จาก tool) หรือ null",
            "apa_year": "2565 (จาก tool) หรือ null",
            "apa_journal": "ชื่อวารสาร (จาก tool) หรือ null",
            "source_queries": ["คำค้นที่ 1"],
            "source_type": "thaijo_article",
            "trust_level": "medium"
        }}
    ],
    "query_results": [
        {{"query": "คำค้น", "count": 5, "strict": true, "status": "success"}},
        {{"query": "คำค้น", "count": 0, "strict": false, "status": "success"}}
    ],
    "failed_queries": []
}}
```

⚠️ กฎเหล็ก — ห้ามละเมิดโดยเด็ดขาด:

**pdf_url — COPY ONLY, ห้าม generate ห้าม reconstruct:**
- ค่า pdf_url ในแต่ละ article ต้อง copy มาจาก field ชื่อ "pdf_url" ใน JSON ที่ search_thaijo tool ส่งคืนมาเท่านั้น
- ห้ามนำ URL ใดๆ จาก summary text, reference text, หรือส่วนอื่นๆ มาใส่เป็น pdf_url
- ห้าม reconstruct URL เอง ห้าม เดา ID ห้าม ต่อ URL จากชิ้นส่วน
- ถ้า tool ไม่ให้ pdf_url หรือให้ค่าว่าง ให้ใส่ null — ห้ามสร้าง URL ขึ้นมาเอง
- ถ้าพบ URL รูปแบบ /article/download/ID/FILEID ในค่า pdf_url ที่ tool ส่งมา ให้แปลงเป็น /article/view/ID
  เช่น https://he01.tci-thaijo.org/index.php/jnat/article/download/252647/170884
       → https://he01.tci-thaijo.org/index.php/jnat/article/view/252647

**ฟิลด์อื่นๆ:**
- ห้ามเปลี่ยนค่า title, apa_authors, apa_year, apa_journal — copy ตรงๆ จาก tool output เท่านั้น
- ถ้า tool ให้ title=null ให้คง null ไว้ ห้ามแต่งชื่อขึ้นมาเอง

**การค้นหา:**
- ต้องเรียก search_thaijo สำหรับทุกๆ keyword query ที่ได้รับมา ห้ามข้ามเด็ดขาด
- หากได้ผลลัพธ์น้อย ให้ลอง strict=False หรือเรียกหลาย page
- ลบซ้ำด้วย pdf_url เท่านั้น — URL เดียวกัน = บทความเดียวกัน
- ถ้าได้ error ให้ใส่ใน failed_queries และดำเนินต่อจนครบทุก query
- ต้องรักษาข้อมูล source_queries ของแต่ละบทความอย่างถูกต้อง
"""

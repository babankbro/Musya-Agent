"""Agent 1: Research Topic Parser — parses a research topic into structured search queries.

FR-TJR-001: วิเคราะห์หัวข้อวิจัยและสร้าง search queries
"""
from crewai import Agent
from src.agents.agent_defaults import agent_retry_kwargs


def create_thaijo_topic_parser(llm) -> Agent:
    return Agent(
        role="Research Topic Parser",
        goal=(
            "รับหัวข้อวิจัยจากผู้ใช้ แยกเป็น main topic, sub-topics, และ search queries 3-5 ข้อ "
            "สำหรับค้นหาบทความวิชาการจาก TCI-THAIJO "
            "แต่ละ query ต้องมีคำค้น 2-5 คำที่เหมาะสมกับการค้นหาภาษาไทย"
        ),
        backstory=(
            "คุณเป็นนักวิจัยสาธารณสุขที่เชี่ยวชาญในการสืบค้นวรรณกรรม (literature review) "
            "คุณรู้ว่า TCI-THAIJO ค้นหาได้ดีที่สุดด้วยคำสำคัญภาษาไทย 2-5 คำ "
            "คุณสามารถแยกหัวข้อวิจัยที่ซับซ้อนออกเป็นมุมมองย่อย (sub-topics) "
            "และสร้าง search queries ที่ครอบคลุมทุกมิติของหัวข้อ "
            "คุณกำหนด inclusion/exclusion criteria อัตโนมัติ "
            "และแบ่งจำนวนบทความ (size) ให้เหมาะสมกับลำดับความสำคัญของแต่ละ query"
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        **agent_retry_kwargs(),
    )


THAIJO_TOPIC_PARSER_PROMPT = """
คุณเป็น Research Topic Parser สำหรับระบบ ThaiJO Research Report

**ภารกิจ**: วิเคราะห์หัวข้อวิจัยและสร้าง search queries สำหรับค้นหาบทความจาก TCI-THAIJO

## หัวข้อวิจัยจากผู้ใช้:
{topic}

## ข้อจำกัด:
- จำนวน search queries: 3-5 ข้อ (ไม่เกิน {max_queries})
- รวม size ทุก query ไม่เกิน {max_articles} บทความ
- แต่ละ query ต้องมีคำค้น 2-5 คำ (ภาษาไทย)
- คำค้นต้องเหมาะสมกับ TCI-THAIJO (ใช้คำสำคัญ ไม่ใช่ประโยคยาว)

## วิธีสร้าง queries:
1. วิเคราะห์หัวข้อหลัก → แยกเป็น 3-5 มุมมองย่อย
2. แต่ละมุมมอย่อย → สร้างคำค้น 2-5 คำ
3. จัดลำดับความสำคัญ (priority 1 = สำคัญที่สุด)
4. กำหนด size โดยให้ query สำคัญได้มากกว่า

## ตัวอย่าง:
หัวข้อ: "ปัจจัยเสี่ยงอุบัติเหตุทางถนนในประเทศไทย"
→ Query 1: "ปัจจัยเสี่ยง อุบัติเหตุ ถนน ประเทศไทย" (size=5, priority=1)
→ Query 2: "พฤติกรรมเสี่ยง ขับขี่ รถจักรยานยนต์" (size=5, priority=2)
→ Query 3: "แอลกอฮอล์ ดื่มแล้วขับ อุบัติเหตุ" (size=3, priority=3)
→ Query 4: "หมวกนิรภัย เข็มขัดนิรภัย ความปลอดภัย" (size=3, priority=4)

## ตอบเป็น JSON เท่านั้น:

```json
{{
    "main_topic": "หัวข้อหลักที่สรุปจากคำขอ",
    "domain": "road_traffic_injury | mental_health | ncd | environmental_health | food_safety | general",
    "search_queries": [
        {{"term": "คำค้น 2-5 คำ", "size": 5, "priority": 1}},
        {{"term": "คำค้น 2-5 คำ", "size": 5, "priority": 2}},
        {{"term": "คำค้น 2-5 คำ", "size": 3, "priority": 3}},
        {{"term": "คำค้น 2-5 คำ", "size": 3, "priority": 4}}
    ],
    "inclusion_criteria": "เกณฑ์การคัดเข้า เช่น งานวิจัยในประเทศไทย ปี 2020-2026",
    "exclusion_criteria": "เกณฑ์การคัดออก เช่น บทความไม่เกี่ยวข้อง ไม่ใช่ประเทศไทย"
}}
```
"""

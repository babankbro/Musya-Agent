"""Request Interpreter Agent: parses user query into structured parameters."""
from crewai import Agent


def create_request_interpreter(llm) -> Agent:
    return Agent(
        role="Request Interpreter",
        goal="แปลความคำขอของผู้ใช้ให้เป็นโครงสร้างข้อมูลที่ชัดเจน รวมถึงระบุหัวข้อ พื้นที่ ช่วงเวลา และประเภทรายงาน",
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญด้านการตีความคำขอเกี่ยวกับข้อมูลสุขภาพ "
            "คุณสามารถแยกแยะได้ว่าผู้ใช้ต้องการข้อมูลด้านอุบัติเหตุ สุขภาพจิต หรือโภชนาการ "
            "รวมถึงระบุพื้นที่ ช่วงเวลา และรูปแบบรายงานที่ต้องการ "
            "ถ้าผู้ใช้ไม่ระบุรายละเอียดครบ ให้ใช้ค่าเริ่มต้นที่เหมาะสม"
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


REQUEST_INTERPRETER_PROMPT = """
จากข้อความของผู้ใช้ ให้วิเคราะห์และสกัดข้อมูลต่อไปนี้:

1. **topics**: หัวข้อที่เกี่ยวข้อง (accident, mental_health, nutrition, general) — สามารถมีได้หลายหัวข้อ
2. **geography**: ชื่อจังหวัด อำเภอ หรือพื้นที่ (ถ้าไม่ระบุ ให้ใส่ "ทั้งประเทศ")
3. **time_range**: ช่วงเวลา start_date และ end_date ในรูปแบบ YYYY-MM-DD (ถ้าไม่ระบุ ให้ใช้ปีปัจจุบัน)
4. **report_type**: ประเภทรายงาน (health_plan, executive_summary, data_query, general_chat)
5. **focus**: ประเด็นที่ต้องการเน้น (เช่น จุดเสี่ยง, แนวโน้ม, กลุ่มเสี่ยง)
6. **language**: ภาษาที่ใช้ตอบ (th หรือ en)
7. **academic_search_needed**: true ถ้าคำถามต้องการข้อมูลวิชาการ/งานวิจัย
   - true เมื่อมีคำว่า: วิจัย, บทความ, วารสาร, ศึกษา, พบว่า, หลักฐาน, งานวิจัย
   - true เมื่อมีคำว่า: research, evidence, study, journal, article
   - true เมื่อ report_type = "health_plan" (ต้องการ evidence-based)
   - false เมื่อถามแค่สถิติหรือข้อมูลจากฐานข้อมูลเท่านั้น
8. **search_keywords**: คำค้นหาสำหรับ ThaiJO (2-5 คำ ภาษาไทย) — ระบุเมื่อ academic_search_needed=true เท่านั้น
   - ตัดคำทั่วไปออก (มี, ไหม, เกี่ยวกับ, งานวิจัย)
   - เก็บคำนาม/คำเฉพาะทาง
   - ตัวอย่าง: "อุบัติเหตุทางถนน ปัจจัยเสี่ยง วัยรุ่น"

ตอบเป็น JSON เท่านั้น:
```json
{{
    "topics": ["accident"],
    "geography": "ทั้งประเทศ",
    "time_range": {{"start_date": "2025-01-01", "end_date": "2025-12-31"}},
    "report_type": "data_query",
    "focus": ["สถานการณ์ปัจจุบัน"],
    "language": "th",
    "academic_search_needed": false,
    "search_keywords": ""
}}
```

ข้อความผู้ใช้: {user_message}
"""

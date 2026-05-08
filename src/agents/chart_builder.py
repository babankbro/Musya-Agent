"""Chart Builder Agent: queries DB and produces ChartSpec-ready JSON payloads.

This agent runs after the Accident Analyst and translates analysis findings
into concrete chart data structures that the frontend ChartRenderer can consume
directly without any further transformation.

Contract with frontend (ChatV1/app/components/chat/chatMessage/ChartRenderer.tsx):
  chartData = { type, title, data: { labels, datasets: [...] }, options }
  Supported types: bar | line | pie | doughnut
"""
from crewai import Agent
from src.agents.agent_defaults import agent_retry_kwargs
from src.tools.chart_builder import (
    build_accident_trend_chart,
    build_hotspot_bar_chart,
    build_time_distribution_chart,
    build_road_condition_pie_chart,
    build_monthly_death_bar_chart,
    build_province_year_trend_chart,
    build_province_roads_bar_chart,
)


CHART_BUILDER_TOOLS = [
    build_province_year_trend_chart,
    build_province_roads_bar_chart,
    build_accident_trend_chart,
    build_hotspot_bar_chart,
    build_time_distribution_chart,
    build_road_condition_pie_chart,
    build_monthly_death_bar_chart,
]


def create_chart_builder(llm) -> Agent:
    return Agent(
        role="Report Chart Builder",
        goal=(
            "สร้างข้อมูลกราฟที่พร้อมแสดงผลบน UI โดยใช้เครื่องมือ build_* "
            "เพื่อดึงข้อมูลจากฐานข้อมูลและผลิต JSON ที่ตรงกับ ChartSpec ทุกกราฟที่เกี่ยวข้อง"
        ),
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญด้านการแสดงผลข้อมูล (data visualisation) "
            "คุณรู้ว่า frontend ต้องการข้อมูลในรูปแบบ Chart.js: "
            "{ type, title, data: { labels, datasets } } "
            "คุณใช้เครื่องมือ build_* เพื่อดึงและจัดรูปข้อมูลจากฐานข้อมูลให้ถูกต้อง "
            "คุณไม่สร้างข้อมูลสมมติ — ถ้าเครื่องมือคืนค่า error ให้รายงานตามความเป็นจริง "
            "คุณเลือกประเภทกราฟที่เหมาะสมกับข้อมูล: "
            "line สำหรับแนวโน้ม, bar สำหรับการเปรียบเทียบ, pie/doughnut สำหรับสัดส่วน"
        ),
        tools=CHART_BUILDER_TOOLS,
        llm=llm,
        verbose=True,
        allow_delegation=False,
        **agent_retry_kwargs(),
    )


CHART_BUILDER_PROMPT = """
คุณมีข้อมูลจาก 3 แหล่ง:
1. **Retrieval Agent**: ข้อมูลจาก get_province_year_summary หรือ tools อื่นๆ (อาจเป็นตาราง text)
2. **SQL Specialist**: ข้อมูลที่จัดรูปแบบพร้อมสำหรับกราฟ (ถ้ามี)
3. **Analyst**: ผลการวิเคราะห์และข้อเสนอแนะ

**งานของคุณ**: สร้างกราฟที่เกี่ยวข้องโดย:

**วิธีที่ 1 - ใช้ข้อมูลที่มีอยู่แล้ว** (แนะนำ):
- ถ้า Retrieval Agent หรือ SQL Specialist ให้ข้อมูลรายปีมาแล้ว (เช่น get_province_year_summary)
- ให้แปลงข้อมูลนั้นเป็น ChartSpec JSON โดยตรง ไม่ต้องเรียก build_* tools
- ตัวอย่าง: ถ้าได้ข้อมูล "2020: 1144 ครั้ง, 2021: 1094 ครั้ง, ..."
  → สร้าง line chart ด้วย labels = ["2020", "2021", ...], datasets = [{data: [1144, 1094, ...]}]

**วิธีที่ 2 - ใช้ build_* tools**:
ถ้าข้อมูลที่มีไม่เพียงพอ ให้เรียกเครื่องมือ:

กราฟเชิงจังหวัด:
1. แนวโน้มรายปีของจังหวัด → build_province_year_trend_chart(province)
2. ถนนเสี่ยงในจังหวัด → build_province_roads_bar_chart(province, year)
3. เปรียบเทียบหลายจังหวัด → build_province_year_trend_chart()

กราฟภาพรวม:
4. แนวโน้มรายเดือน → build_accident_trend_chart
5. จุดเสี่ยง/hotspot → build_hotspot_bar_chart
6. ช่วงเวลา → build_time_distribution_chart
7. สภาพถนน → build_road_condition_pie_chart
8. ผู้เสียชีวิตรายเดือน → build_monthly_death_bar_chart

**สำคัญ**:
- ให้ความสำคัญกับข้อมูลที่มีอยู่แล้วจาก Retrieval/SQL Specialist ก่อน
- ถ้ามีข้อมูลครบแล้ว ไม่ต้องเรียก build_* tools ซ้ำ
- แปลงข้อมูล text เป็น JSON ได้เลย

**Output Format**:
```json
[
  {
    "type": "line",
    "title": "แนวโน้มอุบัติเหตุจังหวัดเชียงใหม่ 2020-2026",
    "data": {
      "labels": ["2020", "2021", "2022", "2023", "2024", "2025", "2026"],
      "datasets": [
        {
          "label": "จำนวนอุบัติเหตุ",
          "data": [1144, 1094, 788, 625, 536, 574, 107],
          "borderColor": "#3b82f6",
          "backgroundColor": "rgba(59, 130, 246, 0.1)"
        },
        {
          "label": "ผู้เสียชีวิต",
          "data": [87, 83, 79, 56, 48, 76, 7],
          "borderColor": "#ef4444",
          "backgroundColor": "rgba(239, 68, 68, 0.1)"
        }
      ]
    },
    "options": {},
    "source_note": "ข้อมูลจาก mart_province_year"
  }
]
```

ถ้าไม่มีกราฟ ให้ส่งคืน: []
"""

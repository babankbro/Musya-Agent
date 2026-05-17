# Musya Agent — Flow V2 (Policy Brief Extension)
# เอกสารออกแบบ Agent Pipeline สำหรับสร้าง Policy Brief สาธารณสุข

> **เวอร์ชัน**: 3.0 (Phase 3 — Policy Brief)
> **วันที่**: 2026-04-14
> **ผู้อ่านเป้าหมาย**: Developer ที่ต่อยอดจาก Phase 2
> **ขอบเขต**: Policy Brief Agent Pipeline + NotebookLM Integration

---

## 1. บทนำ

### 1.1 วัตถุประสงค์

Phase 3 ต่อยอดจาก Phase 2 (Citation & Evidence) โดยเพิ่มความสามารถในการ **สร้าง Policy Brief อัตโนมัติ** จากรายงานตรวจราชการสาธารณสุข 5 จังหวัด (เขตสุขภาพที่ 10) ครอบคลุม 3 หัวข้อ:

| หัวข้อ | ตัวชี้วัดหลัก | แหล่งข้อมูล |
|--------|--------------|------------|
| **อุบัติเหตุทางถนน (RTI)** | อัตราเสียชีวิต/แสน, จุดเสี่ยง, Haddon Matrix | NotebookLM + PostgreSQL |
| **สุขภาพจิต (Mental Health)** | Suicide rate, อัตราไม่ซ้ำใน 1 ปี, ซึมเศร้า | NotebookLM |
| **โภชนาการ & NCDs** | BMI, DM/HT control, follow-up rate, CKD | NotebookLM |

### 1.2 จังหวัดที่รองรับ (เขตสุขภาพที่ 10)

| จังหวัด | Notebook ID | ปีที่มีข้อมูล |
|---------|-------------|--------------|
| มุกดาหาร | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` | รอบ 2 ปี 64–68, รอบ 1 ปี 69 |
| ยโสธร | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` | รอบ 2 ปี 64–68 |
| ศรีสะเกษ | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` | รอบ 2 ปี 64–68, รอบ 1 ปี 69 |
| อำนาจเจริญ | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` | รอบ 2 ปี 64–68, รอบ 1 ปี 69 |
| อุบลราชธานี | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` | รอบ 2 ปี 64–68, รอบ 1 ปี 69 |

### 1.3 วิวัฒนาการระบบ

```
Phase 1: 6 agents — accident domain (PostgreSQL only)
Phase 2: 7 agents — + Citation & Evidence layer
Phase 3: 11 agents — + Policy Brief pipeline (NotebookLM + PDF reports)
```

---

## 2. ภาพรวม Architecture (Phase 3)

### 2.1 Full Pipeline Diagram

```
POST /api/policy-brief
{ "province": "อุบลราชธานี", "topics": ["rti","mental","ncd"], "year": 2564 }
         │
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                  POLICY BRIEF ORCHESTRATOR (Agent A0)              │
│  - ตรวจสอบ input (province + topics)                               │
│  - เรียก NLM Data Fetcher (shared data layer)                      │
│  - แจก context ให้ Analyst agents แบบ parallel                     │
│  - รวม output ทั้งหมด → Citation Agent → Policy Report Writer      │
└──────────┬──────────────────────────────────────────────┬──────────┘
           │                                              │
           ▼                                              ▼
┌──────────────────────┐              ┌────────────────────────────────┐
│   NLM DATA FETCHER   │              │     DATA SOURCES               │
│      (Agent A1)      │              │                                │
│                      │              │  ┌──────────────────────────┐  │
│  tools:              │              │  │  NotebookLM              │  │
│  - nlm_ask()         │◀─────────────│  │  (PDF inspection reports)│  │
│                      │              │  │  Notebook ID:            │  │
│  3 queries/province: │              │  │  bc3d9350-...            │  │
│  - RTI query         │              │  └──────────────────────────┘  │
│  - Mental query      │              │                                │
│  - NCD query         │              │  ┌──────────────────────────┐  │
│                      │              │  │  PostgreSQL              │  │
│  Output:             │              │  │  fact_accident_event     │  │
│  Structured JSON     │              │  │  mart_province_year      │  │
│  per topic/province  │              │  │  mart_accident_hotspot   │  │
└──────────┬───────────┘              │  └──────────────────────────┘  │
           │                          └────────────────────────────────┘
           │  shared context
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                   PARALLEL ANALYST AGENTS                         │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │  RTI POLICY      │  │  MENTAL HEALTH   │  │  NCD POLICY   │  │
│  │  ANALYST (A2)    │  │  ANALYST (A3)    │  │  ANALYST (A4) │  │
│  │                  │  │                  │  │               │  │
│  │ + reuse tools:   │  │ ⚠️  Safety       │  │ Life-course   │  │
│  │  get_hotspots    │  │  Guardrails      │  │ chain:        │  │
│  │  province_year   │  │  (safe lang.)    │  │ child→adult   │  │
│  │  time_dist       │  │                  │  │ →complication │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬────────┘  │
└───────────┼────────────────────┼───────────────────┼────────────┘
            │                    │                   │
            └────────────────────┼───────────────────┘
                                 │
                                 ▼
            ┌────────────────────────────────────────────┐
            │      CITATION & EVIDENCE AGENT (A5)        │
            │  (reuse Phase 2 — เพิ่ม source type)       │
            │  evidence_type: "notebooklm_pdf"           │
            │  trust_level: "high" (official report)     │
            └────────────────────┬───────────────────────┘
                                 │
                                 ▼
            ┌────────────────────────────────────────────┐
            │       POLICY REPORT WRITER (A6)            │
            │  - สังเคราะห์ทั้ง 3 หัวข้อ                  │
            │  - เพิ่ม cross-topic linkage section        │
            │  - output: Policy Brief Markdown            │
            │  - inline citations [C-001]                 │
            └────────────────────────────────────────────┘
```

### 2.2 เปรียบเทียบ Phase 2 vs Phase 3

| ส่วน | Phase 2 (ปัจจุบัน) | Phase 3 (ใหม่) |
|------|------------------|---------------|
| Endpoint | `POST /api/chat` | `POST /api/policy-brief` |
| Data source | PostgreSQL + pgvector | + NotebookLM (PDF) |
| Agents | 7 (sequential) | 11 (sequential + parallel) |
| Domain | Accident only | RTI + Mental + NCD |
| Output | Chat report | Structured Policy Brief |
| Cross-topic | ❌ | ✅ linkage section |
| LLM | Gemini 2.0 Flash | Gemini 2.0 Flash |

---

## 3. รายละเอียด 6 Agents ใหม่

### Agent A0 — Policy Brief Orchestrator

| Property | Value |
|----------|-------|
| **Role** | Policy Brief Orchestrator |
| **Goal** | รับ input → ประสาน NLM Fetcher → แจก context → รวม output |
| **Tools** | ไม่มี (ควบคุม flow ผ่าน CrewAI task dependencies) |
| **Output** | AgentContext object สำหรับส่งต่อ Analysts |

**ขั้นตอนหลัก:**
1. Validate `province` อยู่ใน 5 จังหวัดที่รองรับ
2. Map `province` → Notebook ID
3. เรียก NLM Data Fetcher (sequential — ต้องรอก่อน)
4. แจก context ให้ 3 Analysts (parallel — รันพร้อมกัน)
5. Collect outputs → Citation Agent → Policy Report Writer

---

### Agent A1 — NLM Data Fetcher

| Property | Value |
|----------|-------|
| **Role** | NotebookLM Data Fetcher |
| **Goal** | ดึงข้อมูลดิบจากรายงานตรวจราชการผ่าน NotebookLM API |
| **Tools** | `nlm_ask(province, topic, notebook_id)` |
| **Input** | province, topics list, notebook_id |
| **Output** | Structured JSON ต่อ topic ต่อ province |

**Queries ที่ใช้:**

```python
QUERIES = {
    "rti": """
        อุบัติเหตุทางถนน จ.{province} รายงานตรวจราชการ:
        1) อัตราผู้เสียชีวิตต่อแสนประชากร เปรียบเทียบ Median
        2) กลุ่มเด็กและเยาวชน (1-18 ปี) สถิติและพฤติกรรมเสี่ยง
        3) จุดเสี่ยง Hot Spots ระดับอำเภอ/ตำบล
        4) ผลการวิเคราะห์ Haddon Matrix
        5) มาตรฐาน EMS / D-RTI
    """,
    "mental": """
        สุขภาพจิต การฆ่าตัวตาย จ.{province} รายงานตรวจราชการ:
        1) อัตราการฆ่าตัวตายสำเร็จต่อแสนประชากร แยกรายอำเภอ
        2) อัตราผู้พยายามฆ่าตัวตายไม่ซ้ำใน 1 ปี
        3) ผู้ป่วยโรคซึมเศร้า: เข้าถึงบริการ + ทุเลาใน 6 เดือน
        4) Mental Health Check-in: กลุ่มเครียด/เสี่ยงซึมเศร้า/เสี่ยงฆ่าตัวตาย
        5) กลุ่มพิเศษ: ผู้ต้องขัง, บุคลากรสาธารณสุข
    """,
    "ncd": """
        โภชนาการ BMI เบาหวาน ความดัน จ.{province} รายงานตรวจราชการ:
        1) เด็ก 0-5 ปี: สูงดีสมส่วน / เตี้ย / ผอม / อ้วน (%)
        2) DM/HT screening coverage กลุ่มอายุ 35 ปีขึ้นไป
        3) Follow-up rate กลุ่มสงสัยป่วย (เป้าหมาย 60-80%)
        4) HbA1c control (%) และ BP control (%)
        5) CKD รายใหม่ และ CVD Risk assessment
        6) DM Remission clinic นวัตกรรมที่ดำเนินการ
    """
}
```

**Output Schema:**
```json
{
    "province": "อุบลราชธานี",
    "notebook_id": "bc3d9350-1855-45f0-a2c3-a5634ed8056e",
    "year": 2564,
    "rti": {
        "death_rate_per_100k": "...",
        "median_comparison": "...",
        "youth_stats": "...",
        "hotspots": ["...", "..."],
        "haddon_matrix": "...",
        "ems_standard": "..."
    },
    "mental": {
        "suicide_rate_per_100k": "...",
        "no_repeat_rate_1yr": "...",
        "depression_access": "...",
        "depression_remission_6m": "...",
        "checkin_results": "...",
        "district_breakdown": "..."
    },
    "ncd": {
        "child_growth_status": "...",
        "dm_screening_coverage": "...",
        "ht_screening_coverage": "...",
        "followup_rate": "...",
        "hba1c_controlled": "...",
        "bp_controlled": "...",
        "ckd_new_cases": "...",
        "dm_remission_model": "..."
    }
}
```

---

### Agent A2 — RTI Policy Analyst

| Property | Value |
|----------|-------|
| **Role** | Road Traffic Injury Policy Analyst |
| **Goal** | วิเคราะห์ RTI เชิงพื้นที่และพฤติกรรม สังเคราะห์ข้อเสนอนโยบาย |
| **Tools** | `get_accident_hotspots`, `get_province_year_summary`, `get_accident_time_distribution` (reuse Phase 2) |
| **Input** | NLM data context (rti section) |
| **Output** | RTI Policy Analysis JSON (6 ส่วน) |

**Analysis Framework (Haddon Matrix):**

```
          │ ก่อนเกิดเหตุ    │ ขณะเกิดเหตุ     │ หลังเกิดเหตุ
──────────┼─────────────────┼─────────────────┼──────────────
คน        │ เมาแล้วขับ      │ ไม่ใส่หมวก      │ รู้ CPR?
          │ ไม่มีใบขับขี่   │ ความเร็วสูง     │
──────────┼─────────────────┼─────────────────┼──────────────
รถ        │ ไม่ตรวจสภาพ     │ เบรกไม่ดี       │ กู้ชีพรถ?
──────────┼─────────────────┼─────────────────┼──────────────
สิ่งแวดล้อม│ ไม่มีป้ายเตือน │ ถนนลื่น         │ EMS ถึงทัน?
          │ แสงน้อย         │ ทางโค้งอันตราย  │
```

**Output Schema:**
```json
{
    "situation": {
        "current_rate": "อัตราเสียชีวิตปัจจุบัน",
        "vs_median": "เปรียบเทียบกับค่ามัธยฐาน (สูง/ต่ำ/เท่ากัน)",
        "trend": "แนวโน้ม 3-5 ปี (เพิ่ม/ลด/ทรงตัว)",
        "youth_burden": "ภาระในกลุ่มเด็ก-เยาวชน"
    },
    "risk_factors": {
        "behavioral": ["ไม่สวมหมวก", "เมาแล้วขับ"],
        "environmental": ["ทางโค้งอันตราย", "แสงไม่เพียงพอ"],
        "systemic": ["EMS ถึงช้า", "โรงพยาบาลห่างไกล"]
    },
    "hotspots": [
        { "location": "...", "district": "...", "frequency": "...", "priority": "high" }
    ],
    "target_groups": ["เยาวชน 15-24 ปี", "ผู้สูงอายุ 60+ ปี"],
    "policy_recommendations": [
        {
            "priority": "high",
            "timeframe": "short",
            "action": "...",
            "responsible": "...",
            "kpi": "...",
            "target": "..."
        }
    ],
    "evidence_refs": ["C-001", "C-002"]
}
```

---

### Agent A3 — Mental Health Policy Analyst

| Property | Value |
|----------|-------|
| **Role** | Mental Health & Suicide Prevention Policy Analyst |
| **Goal** | วิเคราะห์สถิติสุขภาพจิต ระบุกลุ่มเปราะบาง เสนอนโยบายเชิงระบบ |
| **Tools** | ไม่มี (วิเคราะห์จาก NLM context) |
| **Input** | NLM data context (mental section) |
| **Output** | Mental Health Policy Analysis JSON |

**⚠️ Safety Guardrails (บังคับใส่ใน backstory):**

```
CRITICAL SAFETY RULES:
1. ใช้ภาษา epidemiological/policy — ห้ามใช้ภาษา sensational หรือบรรยายวิธีการ
2. ห้ามระบุข้อมูลส่วนตัว ชื่อ หรือรายละเอียดรายกรณี
3. เน้น protective factors และการเข้าถึงบริการเสมอ
4. ระบุ disclaimer ในทุก output:
   "ข้อมูลนี้จัดทำเพื่อวางแผนนโยบายสาธารณสุข
    ไม่ใช่สำหรับสื่อมวลชนหรือรายงานสาธารณะ
    ต้องผ่านการทบทวนโดยผู้เชี่ยวชาญด้านสุขภาพจิตก่อนเผยแพร่"
5. กลุ่มเปราะบางให้ระบุในรูปแบบ demographic (เช่น "ชายวัยกลางคน อายุ 40-59 ปี")
   ไม่ใช่รูปแบบที่ระบุตัวตนได้
```

**Output Schema:**
```json
{
    "disclaimer": "ข้อมูลนี้จัดทำเพื่อวางแผนนโยบายสาธารณสุข...",
    "situation": {
        "suicide_rate_per_100k": "...",
        "vs_target": "เปรียบเทียบกับเป้าหมาย ≤8.0",
        "no_repeat_rate_1yr": "...",
        "vs_target_repeat": "เปรียบเทียบกับเป้าหมาย ≥90-95%"
    },
    "high_risk_districts": [
        { "district": "...", "rate": "...", "priority": "..." }
    ],
    "service_gaps": {
        "depression_access_gap": "...",
        "remission_6m_gap": "...",
        "checkin_coverage": "..."
    },
    "vulnerable_groups": [
        "กลุ่ม demographic ที่เสี่ยงสูง (epidemiological framing)"
    ],
    "policy_recommendations": [
        {
            "priority": "high",
            "timeframe": "short",
            "action": "...",
            "responsible": "...",
            "kpi": "...",
            "target": ""
        }
    ],
    "evidence_refs": ["C-003", "C-004"]
}
```

---

### Agent A4 — NCD Policy Analyst

| Property | Value |
|----------|-------|
| **Role** | Nutrition & Non-Communicable Disease Policy Analyst |
| **Goal** | วิเคราะห์ห่วงโซ่ความเสี่ยง NCD เสนอ life-course intervention |
| **Tools** | ไม่มี (วิเคราะห์จาก NLM context) |
| **Input** | NLM data context (ncd section) |
| **Output** | NCD Policy Analysis JSON |

**Risk Chain Framework:**
```
เด็กอ้วน/เตี้ว (BMI เกินเกณฑ์)
    │
    ▼
↑ ความเสี่ยง DM/HT วัยทำงาน
    │
    ▼
คัดกรองพบสงสัยป่วย แต่ follow-up ไม่ครบ (< 60-80%)
    │
    ▼
ป่วยรุนแรง: HbA1c > 7% / BP ไม่ได้ตามเกณฑ์
    │
    ▼
ภาวะแทรกซ้อน: CKD รายใหม่ / CVD Risk สูง
    │
    ▼
ภาระระบบสุขภาพและเศรษฐกิจ
```

**Output Schema:**
```json
{
    "life_course_assessment": {
        "early_life": {
            "good_growth_pct": "...",
            "stunting_pct": "...",
            "obesity_pct": "...",
            "vs_target": "..."
        },
        "working_age": {
            "dm_screening_coverage": "...",
            "ht_screening_coverage": "...",
            "followup_rate": "...",
            "followup_gap_district": ["อำเภอที่ follow-up ต่ำสุด"]
        },
        "disease_control": {
            "hba1c_controlled_pct": "...",
            "bp_controlled_pct": "...",
            "ckd_new_cases": "...",
            "cvd_risk_high_pct": "..."
        }
    },
    "priority_districts": [
        { "district": "...", "issue": "low_followup/uncontrolled_dm/...", "priority": "high" }
    ],
    "innovations": {
        "dm_remission_model": "รายละเอียดโมเดลที่ดำเนินการอยู่",
        "scale_recommendation": "..."
    },
    "policy_recommendations": [
        {
            "priority": "high",
            "timeframe": "short",
            "action": "...",
            "responsible": "...",
            "kpi": "...",
            "target": ""
        }
    ],
    "evidence_refs": ["C-005", "C-006"]
}
```

---

### Agent A5 — Citation & Evidence Agent (Extended)

**Reuse Phase 2** — เพิ่ม source type ใหม่:

| เพิ่มใหม่ใน Phase 3 | คำอธิบาย |
|--------------------|----------|
| `evidence_type: "notebooklm_pdf"` | อ้างอิงจาก PDF รายงานตรวจราชการผ่าน NotebookLM |
| `source_ref: "notebooklm:{notebook_id}:{filename}"` | ชี้ไฟล์ PDF เฉพาะ |
| `trust_level: "high"` | รายงานราชการ ความน่าเชื่อถือสูง |
| `page_ref: "ตรวจราชการ รอบที่ 2 ปี 2564"` | อ้างอิงปีและรอบ |

**ตัวอย่าง Citation ใหม่:**
```json
{
    "evidence_id": "EV-NLM-001",
    "evidence_type": "notebooklm_pdf",
    "source_ref": "notebooklm:bc3d9350-...:เอกสารรับตรวจ จ.อุบลราชธานี รอบ2-64.pdf",
    "title": "รายงานตรวจราชการสาธารณสุข จ.อุบลราชธานี รอบที่ 2 ปี 2564",
    "trust_level": "high",
    "section_label": "อุบัติเหตุทางถนน"
}
```

---

### Agent A6 — Policy Report Writer

| Property | Value |
|----------|-------|
| **Role** | Policy Brief Report Writer |
| **Goal** | สังเคราะห์ผลจาก 3 Analysts เป็น Policy Brief ฉบับเดียว |
| **Tools** | ไม่มี (สังเคราะห์จาก context) |
| **Input** | RTI + Mental + NCD analysis + Citations |
| **Output** | Policy Brief Markdown + cross-topic section |

**Policy Brief Template:**
```markdown
# นโยบายสาธารณสุข จังหวัด{province}
## รายงานตรวจราชการ รอบที่ 2 ปี {year}

> จัดทำโดย: Musya Agent Policy Brief System
> วันที่: {date}
> ⚠️ เอกสารนี้จัดทำเพื่อใช้ภายในสำหรับวางแผนนโยบาย

---

## บทสรุปผู้บริหาร (Executive Summary)
[ประเด็นวิกฤต 3-5 ข้อ จากทุก topic รวมกัน]

---

## 1. สถานการณ์อุบัติเหตุทางถนน
### 1.1 สถานการณ์ปัจจุบัน
[ข้อมูลอัตรา + เปรียบเทียบ Median] [C-001]

### 1.2 จุดเสี่ยงเร่งด่วน
[Top hotspots] [C-002]

### 1.3 ข้อเสนอแนะเชิงนโยบาย
| ลำดับ | มาตรการ | ระยะเวลา | ผู้รับผิดชอบ | KPI |
...

---

## 2. สถานการณ์สุขภาพจิต
> ⚠️ ข้อมูลนี้จัดทำเพื่อวางแผนนโยบายเท่านั้น
### 2.1 ภาพรวมสถานการณ์
...

---

## 3. โภชนาการและโรคไม่ติดต่อเรื้อรัง (NCDs)
...

---

## 4. ความเชื่อมโยงข้ามประเด็น (Cross-topic Linkage)
[ส่วนนี้สำคัญ — Agent สังเคราะห์ความสัมพันธ์ระหว่าง 3 หัวข้อ]

ตัวอย่าง:
- อุบัติเหตุรุนแรง → PTSD → เพิ่มความเสี่ยง suicide
- โรคอ้วน → mobility ลดลง → ซึมเศร้า
- DM ควบคุมไม่ได้ → CKD → ภาระค่าใช้จ่าย → ความเครียดครัวเรือน
- ชุมชนยากจน → โภชนาการต่ำ + เข้าไม่ถึงบริการ + อุบัติเหตุสูง

---

## 5. ข้อเสนอแนะเชิงระบบ (Priority Recommendations)
[รวม top 5-10 จากทุก topic จัดลำดับ priority]

---

## 6. ตัวชี้วัดติดตามผล (KPIs)
| KPI | ค่าปัจจุบัน | เป้าหมาย | กรอบเวลา |
...

---

## อ้างอิง
[C-001] รายงานตรวจราชการ จ.อุบลราชธานี รอบที่ 2 ปี 2564 [หน้า: อุบัติเหตุทางถนน]
...
```

---

## 4. Tools ใหม่ที่ต้องพัฒนา

### 4.1 `nlm_ask` Tool

```python
# src/tools/notebooklm.py

import subprocess
from crewai.tools import tool

@tool("NotebookLM Ask Tool")
def nlm_ask(province: str, topic: str, notebook_id: str) -> str:
    """
    ดึงข้อมูลจากรายงานตรวจราชการผ่าน NotebookLM CLI
    Args:
        province: ชื่อจังหวัด (ภาษาไทย)
        topic: "rti" | "mental" | "ncd"
        notebook_id: NotebookLM notebook UUID
    Returns:
        ข้อความตอบกลับจาก NotebookLM
    """
    queries = {
        "rti": f"อุบัติเหตุทางถนน จ.{province}: อัตราเสียชีวิต จุดเสี่ยง กลุ่มเยาวชน Haddon Matrix EMS",
        "mental": f"สุขภาพจิต suicide rate จ.{province}: อัตราฆ่าตัวตาย ไม่ซ้ำ 1 ปี ซึมเศร้า รายอำเภอ",
        "ncd": f"BMI เบาหวาน ความดัน จ.{province}: สูงดีสมส่วน screening followup HbA1c CKD",
    }

    result = subprocess.run(
        ["conda", "run", "-n", "notebooklm",
         "notebooklm", "ask", queries[topic]],
        capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout
```

---

## 5. API Endpoints ใหม่

### 5.1 Policy Brief Endpoint

```
POST /api/policy-brief
```

**Request:**
```json
{
    "province":  "อุบลราชธานี",
    "topics":    ["rti", "mental", "ncd"],
    "year":      2564,
    "format":    "markdown"
}
```

**Response:**
```json
{
    "province":      "อุบลราชธานี",
    "policy_brief":  "# นโยบายสาธารณสุข...\n\n...[C-001]...",
    "sections": {
        "rti":    { "situation": "...", "hotspots": [...], "recommendations": [...] },
        "mental": { "disclaimer": "...", "situation": "...", "recommendations": [...] },
        "ncd":    { "life_course": {...}, "recommendations": [...] }
    },
    "cross_topic_links": [
        "อุบัติเหตุรุนแรง → PTSD → suicide risk",
        "โรคอ้วน → mobility ลด → depression",
        "DM ควบคุมไม่ได้ → CKD → ความเครียดครัวเรือน"
    ],
    "charts":    [...],
    "citations": [...],
    "metadata": {
        "elapsed_seconds": 180,
        "agent_count":     11,
        "pipeline":        "phase3_policy_brief",
        "notebook_id":     "bc3d9350-...",
        "topics_analyzed": ["rti", "mental", "ncd"]
    }
}
```

### 5.2 Endpoints รวมทั้งระบบ (Phase 3)

| Method | Path | คำอธิบาย | Phase |
|--------|------|----------|-------|
| `GET`  | `/api/health` | ตรวจสุขภาพระบบ | 1 |
| `POST` | `/api/chat` | Chat + Accident analysis | 2 |
| `POST` | `/api/ingest` | นำเข้าเอกสารสู่ pgvector | 2 |
| `GET`  | `/api/evidence/{id}` | ดู evidence item | 2 |
| `POST` | `/api/policy-brief` | สร้าง Policy Brief | **3 (ใหม่)** |
| `GET`  | `/api/policy-brief/provinces` | รายชื่อจังหวัดที่รองรับ | **3 (ใหม่)** |

---

## 6. โครงสร้างไฟล์ที่เพิ่ม/แก้ไข

```
Agent/
├── src/
│   ├── agents/
│   │   ├── policy_orchestrator.py    ← NEW: Agent A0
│   │   ├── nlm_data_fetcher.py       ← NEW: Agent A1
│   │   ├── policy_rti.py             ← NEW: Agent A2
│   │   ├── policy_mental.py          ← NEW: Agent A3
│   │   ├── policy_ncd.py             ← NEW: Agent A4
│   │   ├── policy_report_writer.py   ← NEW: Agent A6
│   │   └── citation_evidence.py      ← MODIFY: เพิ่ม notebooklm_pdf type
│   ├── tools/
│   │   └── notebooklm.py             ← NEW: nlm_ask tool
│   ├── routers/
│   │   └── policy_brief.py           ← NEW: POST /api/policy-brief
│   └── schemas/
│       └── policy_brief.py           ← NEW: PolicyBriefRequest/Response
```

---

## 7. ประสิทธิภาพและ Timing (Phase 3)

| ขั้นตอน | Agent | เวลาโดยประมาณ |
|---------|-------|--------------|
| Policy Brief Orchestrator | A0 | 3-5 วินาที |
| NLM Data Fetcher (3 queries) | A1 | 30-60 วินาที |
| RTI Analyst | A2 | 15-20 วินาที |
| Mental Health Analyst | A3 | 15-20 วินาที (parallel กับ A2) |
| NCD Analyst | A4 | 15-20 วินาที (parallel กับ A2, A3) |
| Citation & Evidence | A5 | 10-15 วินาที |
| Policy Report Writer | A6 | 20-30 วินาที |
| **รวม Pipeline ทั้งหมด** | | **~2-3 นาที** |

> NLM Data Fetcher เป็น bottleneck หลัก เนื่องจากต้องรอ NotebookLM API ตอบกลับ 3 ครั้ง

---

## 8. ลำดับการพัฒนา (Implementation Order)

```
Sprint 1: Data Layer
  ✦ tools/notebooklm.py        (nlm_ask tool)
  ✦ agents/nlm_data_fetcher.py (Agent A1)
  ✦ ทดสอบ: query ข้อมูลจริงทุก topic ทุกจังหวัด

Sprint 2: Analyst Agents
  ✦ agents/policy_rti.py       (Agent A2)
  ✦ agents/policy_mental.py    (Agent A3 + safety guardrails)
  ✦ agents/policy_ncd.py       (Agent A4)

Sprint 3: Integration
  ✦ citation_evidence.py       (extend: notebooklm_pdf type)
  ✦ agents/policy_report_writer.py (Agent A6)
  ✦ agents/policy_orchestrator.py  (Agent A0)

Sprint 4: API & Schema
  ✦ schemas/policy_brief.py
  ✦ routers/policy_brief.py
  ✦ ทดสอบ end-to-end ทุกจังหวัด
```

---

## 9. ข้อควรระวัง

| ประเด็น | รายละเอียด | วิธีจัดการ |
|---------|-----------|-----------|
| **Mental Health Safety** | ข้อมูล suicide อ่อนไหวมาก | Safety guardrails ใน backstory + disclaimer บังคับ |
| **NotebookLM Rate Limit** | Google อาจ throttle requests | ใส่ delay 2-3 วินาทีระหว่าง queries |
| **Auth Expiry** | cookies หมดอายุ | ตรวจสอบก่อนรัน pipeline + auto-refresh |
| **Data Completeness** | PDF บางจังหวัดไม่มีทุกปี | Graceful fallback + แจ้งใน response |
| **Response Language** | ข้อมูลเป็นภาษาไทยทั้งหมด | ระบุ `language: "th"` ใน agent config |

---

*Last updated: 2026-04-14 | Musya Agent Phase 3 (Policy Brief Extension)*

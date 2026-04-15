# Agent ↔ Style Guide Mapping
# การจับคู่ระหว่าง Agent กับ Style Guide แต่ละส่วน

> **Style Guide**: `doc/REPORT_WRITING_STYLE_GUIDE.md`
> **Architecture**: Shared Foundation Pipeline v6.0
> **วันที่อัปเดต**: 2026-04-15

---

## Overview

### Shared Foundation Agents (1-4) — ใช้ร่วมกันทั้ง Chat + Policy Pipeline

| Agent | ไฟล์ | Style Guide Section | หน้าที่ |
|-------|------|-------------------|---------|
| 1 — Request Interpreter | `src/agents/request_interpreter.py` | — | ตีความคำขอ สกัด parameters |
| 2 — Data Retrieval | `src/agents/retrieval.py` | Section 2, 4, 5, 6, 7 | ค้นข้อมูล RAG + DB (+NLM ใน policy mode) |
| 3 — SQL Specialist | `src/agents/sql_specialist.py` | — | เขียน SQL ดึงข้อมูลเฉพาะทาง |
| 4 — Citation & Evidence | `src/agents/citation_evidence.py` | Section 3.1, APA 7th | จัดการอ้างอิง APA format, coverage validation |

### Policy-Specific Agents (5-8) — เฉพาะ Policy Brief Pipeline

| Agent | ไฟล์ | Style Guide Section | หน้าที่ |
|-------|------|-------------------|---------|
| 5 — RTI Analyst | `src/agents/policy_rti.py` | Section 5 (RTI) | วิเคราะห์อุบัติเหตุ ตาม Haddon Matrix + 4 มาตรการ |
| 6 — Mental Health Analyst | `src/agents/policy_mental.py` | Section 6 (Mental Health) | วิเคราะห์สุขภาพจิต ตาม 3ส Plus / วัคซีนใจ |
| 7 — NCD Analyst | `src/agents/policy_ncd.py` | Section 7 (NCD) | วิเคราะห์โภชนาการ/NCD ตาม ต้นน้ำ-กลางน้ำ-ปลายน้ำ |
| 8 — Report Writer | `src/agents/policy_report_writer.py` | Section 1, 2, 8, 9, 10 | สังเคราะห์รายงานตาม template 4 ส่วน |

**Factory**: `src/agents/shared_foundation.py` — `build_foundation_agents()`, `build_foundation_tasks()`

---

## Detailed Mapping

### Agent 2 (Foundation) — Data Retrieval → Style Guide Sections 2, 4, 5, 6, 7

In **policy mode** (`include_nlm=True`), the Retrieval Agent also fetches data from NotebookLM:

| Style Guide Element | Agent Implementation |
|---------------------|---------------------|
| **Section 2**: 4-part writing pattern | Task description instructs retrieval of data for all 4 parts: Situation, Measures, Performance, GAP |
| **Section 4**: Number presentation (อัตราต่อแสน, Median baseline) | NLM queries extract: `death_rate_per_100k`, `median_baseline`, `median_comparison` |
| **Section 5**: RTI KPIs | NLM ดึง: เด็ก 1-18 ปี, ผู้เสียชีวิตภาพรวม, Triage 1, Severe TBI, 4 มาตรการ, Haddon Matrix, Black Spot |
| **Section 6**: Mental Health KPIs | NLM ดึง: suicide rate, no-repeat 1yr, depression access/remission, 2Q/8Q/9Q, 3ส Plus, วัคซีนใจ |
| **Section 7**: NCD KPIs | NLM ดึง: child growth, BMI, DM/HT screening, follow-up, HbA1c/BP control, ต้นน้ำ/กลางน้ำ/ปลายน้ำ |

### Agent 4 (Foundation) — Citation & Evidence → APA 7th Edition + Style Guide Section 3.1

In **policy mode**, gets additional APA metadata for NotebookLM sources:

| Style Guide Element | Agent Implementation |
|---------------------|---------------------|
| **APA 7th Edition**: Thai adaptation | bibliography_text ตาม APA 7th, inline citation ตาม APA short form |
| **Citation Code Ordering** | C-001..C-099 (reports), C-100..C-199 (database), C-200+ (external) |
| **รายงานตรวจราชการ** (report) | `สสจ.{จังหวัด}. ({ปี}). *รายงานตรวจราชการฯ*. กระทรวงสาธารณสุข.` |
| **ฐานข้อมูล** (dataset) | `Musya Agent. ({ปี}). *{ชื่อตาราง}* [Data set]. Musya Agent Database.` |
| **เว็บไซต์** (website) | `{หน่วยงาน}. ({ปี}). *{ชื่อหน้า}*. {ชื่อเว็บ}. {URL}` |
| **Inline Format** | `(สสจ.{จังหวัด}, {ปี}, หน้า {X})` หรือ `[C-001]` |
| **APA Metadata Fields** | `apa_type`, `apa_authors`, `apa_year`, `apa_publisher` on EvidenceItem |
| **Coverage Validation** | ตัวเลข KPI ทุกตัวต้องมี evidence, กราฟ/ตารางต้องมี source_note |
| **Trust Levels** | 🟢 high (รายงานราชการ), 🟡 medium (fact tables), 🔴 low (external) |
| **Reference List** | `reference_list` array: `[C-001] {APA bibliography_text}` |
| **Source Notes** | `source_notes.charts/tables`: `ที่มา: {APA inline} [C-xxx]` |

**Files**: `src/agents/citation_evidence.py`, `src/utils/apa_formatter.py`, `src/schemas/evidence.py`

### Agent 5 — RTI Analyst → Style Guide Section 5

| Style Guide Element | Agent Implementation |
|---------------------|---------------------|
| **หมวด**: Area Based / Functional Based (Service Plan อุบัติเหตุฉุกเฉิน) | Prompt ระบุหมวดหมู่ตรงกัน |
| **4 ส่วน**: Situation → Measures → Performance → GAP | Prompt เขียนตามลำดับ 4 ส่วน |
| **KPI: เด็ก 1-18 ปี** | `youth_1_18`: ลดลง ≥3% จาก Median 3 ปี |
| **KPI: ผู้เสียชีวิตภาพรวม** | `current_rate`: ลดลง ≥5% จาก Median 5 ปี หรือ ≤16/แสน |
| **KPI: Triage 1 ตาย 24 ชม.** | `triage1_mortality`: ≤12% |
| **KPI: Severe TBI** | `severe_tbi_mortality`: <30% |
| **4 มาตรการ** | `four_measures`: management, data_integration, prevention, treatment |
| **Haddon Matrix** | `haddon_matrix`: pre_event/event/post_event × host/agent/environment |
| **Black Spot** | `hotspots`: location, district, frequency, priority |
| **ตัวเลข**: อัตราต่อแสน + Median baseline | `performance_table` with ✓/✗ status |

### Agent 6 — Mental Health Analyst → Style Guide Section 6

| Style Guide Element | Agent Implementation |
|---------------------|---------------------|
| **หมวด**: Functional Based / Service Excellence | Prompt ระบุหมวดหมู่ตรงกัน |
| **4 ส่วน**: Situation → Measures → Performance → GAP | Prompt เขียนตามลำดับ 4 ส่วน |
| **KPI: อัตราฆ่าตัวตาย** | `suicide_rate_per_100k`: ≤8.0 ต่อแสน |
| **KPI: ไม่ซ้ำ 1 ปี** | `no_repeat_rate_1yr`: ≥90-95% |
| **KPI: เข้าถึงบริการ** | `suicide_attempt_access`: ≥65-70% |
| **KPI: ซึมเศร้าเข้าถึง** | `depression_access`: ≥71-80% |
| **KPI: ทุเลา 6 เดือน** | `depression_remission_6m`: ≥55% |
| **เครื่องมือ**: Mental Health Check-in, 2Q/8Q/9Q | `tools_and_measures.screening_2q_8q_9q` |
| **3ส Plus** | `tools_and_measures.sam_sor_plus` |
| **วัคซีนใจ** | `tools_and_measures.vaccine_jai` |
| **Psychological Autopsy** | `tools_and_measures.psychological_autopsy` |
| **อำเภอที่มีอัตราสูง เทียบ Target 8.0** | `high_risk_districts` with `vs_target_8` |
| **Safety Guardrails** | epidemiological framing, no personal info, disclaimer, protective factors |

### Agent 7 — NCD Analyst → Style Guide Section 7

| Style Guide Element | Agent Implementation |
|---------------------|---------------------|
| **หมวด**: Functional Based (สุขภาพกลุ่มวัย) / Service Excellence | Prompt ระบุหมวดหมู่ตรงกัน |
| **4 ส่วน**: Situation → Measures → Performance → GAP | Prompt เขียนตามลำดับ 4 ส่วน |
| **กรอบ**: Input-Process-Output (ต้นน้ำ-กลางน้ำ-ปลายน้ำ) | `upstream_midstream_downstream` |
| **KPI: เด็ก 0-5 ปี** | `child_0_5_growth`: ≥62-64% |
| **KPI: BMI ปกติ** | `working_age_bmi`: ≥50-54% |
| **KPI: คัดกรอง DM/HT** | `dm/ht_screening_coverage`: ≥90% |
| **KPI: Follow-up DM** | `dm_followup_rate`: ≥60-72% |
| **KPI: Follow-up HT** | `ht_followup_rate`: ≥70-85% |
| **KPI: HbA1c** | `hba1c_controlled_pct`: ≥40-50% |
| **KPI: BP** | `bp_controlled_pct`: ≥60% |
| **Key Message** | "5 รู้ 2 ไม่ ใส่ใจนับคาร์บ" |
| **นวัตกรรม** | DM Remission, NCD Clinic Plus |
| **Life-Course Risk Chain** | เด็กอ้วน → DM/HT → CKD/CVD → ภาระระบบ |

### Agent 8 — Report Writer → Style Guide Sections 1, 2, 8, 9, 10

| Style Guide Element | Agent Implementation |
|---------------------|---------------------|
| **Section 1**: Report Structure (5 ส่วน) | Template มีครบ: Front Matter, Foundation, Follow-up, Main Content, GAP |
| **Section 2**: 4-part writing pattern per topic | ทุก domain template ใช้: สถานการณ์ → มาตรการ → ผลดำเนินงาน → ปัญหา/ข้อเสนอแนะ |
| **Section 8**: Executive Summary | `executive_summary`: ผ่านกี่ตัว/ไม่ผ่านกี่ตัว + ประเด็นวิกฤต |
| **Section 8**: Rubric Scoring | ปริมาณ 70% + คุณภาพ 30% (Rubric 5 ระดับ 0-100) |
| **Section 9**: Policy Directive Style | `priority_recommendations` table: ข้อสั่งการ + ผลดำเนินการ + หน่วยรับผิดชอบ |
| **Section 10**: Agent Template | domain templates ตรงกับ Section 10 template |
| **ตาราง Performance** | ทุก domain มี: ตัวชี้วัด \| เป้าหมาย \| ผลงาน \| อัตรา \| สถานะ ✓/✗ |
| **Cross-topic Linkage** | `cross_topic_links`: RTI→PTSD, DM→CKD→stress, poverty→multi-risk |
| **KPI Summary** | `kpi_summary_table`: รวม KPI ทุก domain พร้อมสถานะ |

---

## Shared Style Rules (ทุก Agent ใช้ร่วมกัน)

| Rule | Style Guide Source | Applied To |
|------|-------------------|------------|
| อัตราต่อแสนประชากร (ไม่ใช่แค่จำนวนนับ) | Section 4.1 | Agent 2 (NLM), 5, 6, 7, 8 |
| Baseline = Median ย้อนหลัง 3-5 ปี | Section 4.1 | Agent 2 (NLM), 5, 6, 7, 8 |
| สถานะ ✓ ผ่าน / ✗ ไม่ผ่าน | Section 4.1 | Agent 5, 6, 7, 8 |
| คะแนน: ปริมาณ 70% + คุณภาพ 30% | Section 4.1, 8 | Agent 8 |
| 4-part structure per topic | Section 2 | Agent 2 (NLM), 5, 6, 7, 8 |
| JSON output only | All sections | Agent 5, 6, 7, 8 |
| Citation [C-xxx] APA 7th Edition | Section 3.1 + APA 7th | Agent 4, 8 |
| APA bibliography_text | APA 7th Thai adaptation | Agent 4 (generates), 8 (embeds in reference list) |
| APA inline citation | APA 7th short form | Agent 4 (generates), 5-7 (evidence_refs), 8 (embeds inline) |
| Mental Health disclaimer | Section 6 | Agent 6, 8 |

---

## Pipeline Flow with Style Guide

```
User Request
    │
    ▼
=== SHARED FOUNDATION (agents 1-4) ===
[1] Request Interpreter ─── parse intent, extract parameters
    │
[2] Data Retrieval ──────── Style Guide §2, §4, §5-7 (data + NLM KPI extraction)
    │                       (+NLM tools in policy mode: nlm_ask per topic)
[3] SQL Specialist ──────── complex queries, chart-ready data
    │
[4] Citation & Evidence ─── Style Guide §3.1 + APA 7th Edition (Thai adaptation)
    │                       → bibliography_text, inline citation, reference_list
    │                       → coverage validation (KPI ทุกตัวต้องมี evidence)
    ▼
=== POLICY-SPECIFIC (agents 5-8) ===
[5] RTI Analyst ────────── Style Guide §5 (Haddon Matrix, 4 measures, KPIs)
[6] Mental Analyst ─────── Style Guide §6 (3ส Plus, วัคซีนใจ, Safety Rules)
[7] NCD Analyst ────────── Style Guide §7 (ต้นน้ำ/กลางน้ำ/ปลายน้ำ, KPIs)
    │ (parallel execution — context from agents 2, 3, 4)
    ▼
[8] Report Writer ──────── Style Guide §1, §2, §8-10 (final report template)
    │ 4-part structure, Executive Summary, Rubric Scoring, KPI Summary
    ▼
Policy Brief Output (JSON: executive_summary + per-domain reports + kpi_summary_table)
```

---

*Generated: 2026-04-15 | Shared Foundation Architecture v6.0 | Source: doc/REPORT_WRITING_STYLE_GUIDE.md*

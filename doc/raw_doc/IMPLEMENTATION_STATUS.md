# Musya Agent — Implementation Status

> **เวอร์ชัน**: 7.1
> **วันที่**: 2026-04-18
> **สถานะ**: Production-ready + Enhanced Routing & SQL Fix

---

## 1. Pipeline Architecture (สถานะปัจจุบัน)

### Chat Pipeline — 9 agents sequential
```
Router → Interpreter → Retrieval(search_docs first) → SQL → Citation →
Analyst → Chart → Research Synthesizer → Deep Analyst → Report Composer
```

| Agent | File | LLM Tier | สถานะ |
|-------|------|----------|-------|
| Request Router | `request_router.py` | fast | ✅ พร้อม |
| Request Interpreter | `request_interpreter.py` | fast | ✅ พร้อม |
| Data Retrieval | `retrieval.py` | fast | ✅ พร้อม (ThaiJO enabled) |
| SQL Specialist | `sql_specialist.py` | fast | ✅ พร้อม |
| Citation & Evidence | `citation_evidence.py` | fast | ✅ พร้อม (C-200 ThaiJO support) |
| Accident Analyst | `analyst_accident.py` | pro | ✅ พร้อม |
| Chart Builder | `chart_builder.py` | pro | ✅ พร้อม |
| Research Synthesizer | `research_synthesizer.py` | pro | ✅ พร้อม |
| Deep Analyst | `deep_analyst.py` | pro | ✅ พร้อม |
| Report Composer | `report_writer.py` | pro | ✅ พร้อม |

### Short Chat Pipeline — 3 agents (New v7.1)
```
Router(mode=short) → Interpreter → Quick Retrieval → Quick Answer Writer
```

| Agent | File | LLM Tier | สถานะ |
|-------|------|----------|-------|
| Quick Retrieval | `shared_foundation.py` | fast | ✅ 3 tools minimal |
| Quick Answer Writer | `quick_answer_writer.py` | pro | ✅ 500-1000 words |

### Policy Brief Pipeline — 4+N agents
```
Router → Interpreter → Retrieval(+NLM) → SQL → Citation →
[RTI‖Mental‖NCD] → Policy Report Writer
```

### Accident Policy Pipeline (Zone 10) — 3 agents (New v7.2)
```
Router(mode=accident_policy) → Zone10 SQL Fetcher → Zone10 Policy Analyst → Zone10 Report Writer
```

| Agent | File | LLM Tier | สถานะ |
|-------|------|----------|-------|
| Zone10 SQL Fetcher | `accident_policy_agent.py` | fast | ✅ พร้อม (7 tools) |
| Zone10 Policy Analyst | `accident_policy_agent.py` | pro | ✅ พร้อม |
| Zone10 Report Writer | `accident_policy_agent.py` | pro | ✅ พร้อม |

### Accident Chat Pipeline (Zone 10) — 2 agents (New v7.3)
```
Router(mode=accident_chat) → Accident SQL Data Specialist → RTI Policy Answer Writer
```

| Agent | File | LLM Tier | สถานะ |
|-------|------|----------|-------|
| Accident SQL Data Specialist | `accident_chat_orchestrator.py` | fast | ✅ พร้อม |
| RTI Policy Answer Writer | `accident_chat_orchestrator.py` | pro | ✅ พร้อม |

---

## 2. ThaiJO Academic Subsystem

| คุณสมบัติ | สถานะ |
|-----------|-------|
| **search_thaijo tool** | ✅ พร้อมใช้งาน (Tool 11) |
| **APA Citation Range** | ✅ C-200~C-299 |
| **Evidence Registration** | ✅ `thaijo_article` supported |
| **Subsystem Integration** | ✅ มีใน Chat, Policy, และ Short Chat |

---

## 3. UI Mode Toggle (Frontend)

| ฟีเจอร์ | ไฟล์ | สถานะ |
|---------|------|-------|
| **Mode Toggle** (Full/Short) | `static/policy_brief_ui.html` | ✅ พร้อม |
| **SSE Streaming Support** | `static/policy_brief_ui.html` | ✅ พร้อม |
| **Short Chat UI** | `static/policy_brief_ui.html` | ✅ พร้อม |
| **Inline Citation Tooltips** | `static/policy_brief_ui.html` | ✅ พร้อม |

---

## 4. Bug Fixes & Improvements (v7.1)

| ประเด็น | วิธีแก้ไข |
|---------|-----------|
| Short Chat Citation missing bib | `short_chat_orchestrator.py`: เพิ่ม extraction จาก References section |
| Short Chat Citation missing URL | `short_chat_orchestrator.py`: เพิ่ม fuzzy matching กับ retrieval context |
| missing redis dependency | installed in .venv |
| ThaiJO year widening | Migration 016 applied |
| **Router Auto-Detection** | `request_router.py`: เพิ่ม auto-detect สำหรับคำถามสั้น (<= 60 ตัวอักษร) |
| **ThaiJO Timeout** | `config.py`: ปรับลดจาก 120s เป็น 20s เพื่อความรวดเร็ว |
| **Evidence Constraint Fix** | Migration 017: รองรับ `thaijo_article` ใน `evidence_registry` |
| **Follow-up Extraction** | `short_chat_orchestrator.py`: ปรับปรุง logic การดึงคำถามติดตามให้ robust ขึ้น |

---

## 5. API Endpoints

| Method | Path | Pipeline | คำอธิบาย |
|--------|------|----------|----------|
| `POST` | `/api/chat/unified` | auto-route | Router → chat หรือ policy-brief |
| `POST` | `/api/chat/short` | short_chat | คำตอบสั้น (JSON) |
| `POST` | `/api/chat/short/stream`| short_chat | คำตอบสั้น (SSE) |
| `POST` | `/api/policy-brief` | policy-brief | Direct policy brief pipeline |
| `POST` | `/api/accident-policy/zone10` | accident-policy | รัน Accident Policy Pipeline สำหรับเขตสุขภาพ 10 (LLM) |
| `GET` | `/api/accident-policy/zone10/data` | accident-policy | ดึงข้อมูล 7 policy queries สำหรับเขตสุขภาพ 10 (raw SQL) |
| `POST` | `/api/accident-chat/ask` | accident-chat | รัน Accident Chat Pipeline (2 agents) |
| `POST` | `/api/accident-chat/ask/stream` | accident-chat | รัน Accident Chat Pipeline (SSE) |
| `POST` | `/api/accident-chat/quick` | accident-chat | ดึงข้อมูลดิบจากเครื่องมือ |
| `GET` | `/api/db/tables` | db-explorer | ดูตารางทั้งหมด |
| `GET` | `/api/db/tables/{table}/rows` | db-explorer | ดูข้อมูลในตาราง |

---

*Last updated: 2026-04-18 | Musya Agent v7.1*

# เอกสาร Database & API Reference
# Musya Agent — ฐานข้อมูลรวมและ API ทั้งระบบ

> **เวอร์ชัน**: 2.3  
> **วันที่**: 2026-04-16  
> **Database**: PostgreSQL 16 + pgvector — `chat-aio`  
> **ขอบเขต**: Agent backend + ตารางที่ใช้ร่วมกับ Chat-

---

## 1. บทนำ

### 1.1 วัตถุประสงค์
เอกสารฉบับนี้รวม Database Schema ทั้ง 2 ฝั่ง (Chat- frontend + Agent backend) และ API Reference ทั้งระบบไว้ในที่เดียว เพื่อให้ developer เข้าใจว่าข้อมูลอยู่ที่ไหน ไหลอย่างไร และเรียกใช้ผ่าน API ใด

### 1.2 ฐานข้อมูลที่ใช้ร่วมกัน
ทั้ง 3 components ใช้ **PostgreSQL database เดียวกัน**: `chat-aio`

```
Connection: postgresql://postgres:1234@localhost:5432/chat-aio
```

### 1.3 เอกสารอ้างอิง
| เอกสาร | ตำแหน่ง |
|--------|---------|
| Agent Architecture | `Agent/doc/ARCHITECTURE.md` |
| Agent Architecture | `Agent/doc/ARCHITECTURE.md` |
| Agent Existing DB Architecture | `Agent/doc/DATABASE_API_ARCHITECTURE.md` |
| Chat- Database & API | `Chat-/doc/DATABASE_API.md` |
| Chat- API Routes (ละเอียด) | `Chat-/docs/API_ROUTES.md` |
| Chat- Database Schema (ละเอียด) | `Chat-/docs/DATABASE_SCHEMA.md` |

---

## 2. ภาพรวมฐานข้อมูล (Database Overview)

### 2.1 Database Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                     PostgreSQL 16 (chat-aio)                     │
│                                                                  │
│  ┌────────────────────────┐  ┌────────────────────────────────┐ │
│  │  Application Tables    │  │  Agent Analytics Tables         │ │
│  │  (Chat-/ChatV1 owned)  │  │  (Agent owned)                 │ │
│  │                        │  │                                 │ │
│  │  users                 │  │  dim_geography                  │ │
│  │  chat_sessions         │  │  dim_time                       │ │
│  │  chat_messages         │  │  dim_road_segment               │ │
│  │  planning_history      │  │  dim_population_group           │ │
│  │  file_apa_metadata     │  │  dim_facility                   │ │
│  │                        │  │  dim_source                     │ │
│  │  ─── Domain Data ───   │  │                                 │ │
│  │  accident (Thai cols)  │  │  fact_accident_event            │ │
│  │  diabetes              │  │  fact_accident_person           │ │
│  │  bipola                │  │                                 │ │
│  │  (CSV-imported tables) │  │  mart_accident_summary          │ │
│  │                        │  │  mart_accident_hotspot          │ │
│  └────────────────────────┘  │  mart_province_year             │ │
│                              │  mart_province_road              │ │
│                              │                                 │ │
│                              │  document_registry (enhanced)   │ │
│                              │  document_embeddings (pgvector) │ │
│                              │  indicator_catalog              │ │
│                              │  evidence_registry              │ │
│                              │  claim_evidence_link            │ │
│                              └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  pgvector (inside PostgreSQL chat-aio)                       │
│  table: document_embeddings                                  │
│  collection: musya_documents                                 │
│  model: gemini-embedding-001 (3072-dim, API-based)           │
│  search: exact cosine scan (no ANN index, <50K chunks OK)   │
└─────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│  MinIO (Shared)  localhost:9000                               │
│  Bucket: uploads                                             │
│  ├── folder1/                                               │
│  │   ├── document.pdf                                       │
│  │   └── .folder (marker)                                   │
│  └── report.docx                                            │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 ER Diagram รวม

```
┌──────────┐     1:N     ┌───────────────┐     1:N     ┌───────────────┐
│  users   │────────────►│ chat_sessions │────────────►│ chat_messages │
│  (PK id) │             │ (PK id VARCHAR)│             │ (PK id SERIAL)│
└────┬─────┘             └───────┬───────┘             └───────────────┘
     │                           │
     │ 1:N                       │ 1:N
     ▼                           ▼
┌──────────────────┐   ┌──────────────────┐
│ planning_history │   │ (FK session_id)  │
│ (PK id SERIAL)   │   └──────────────────┘
└──────────────────┘

┌──────────────────────┐      (Standalone — no FKs)
│  file_apa_metadata   │
│  (UQ file_name+path) │
└──────────────────────┘

── Agent Star Schema ──────────────────────────────────────────

┌──────────────┐
│dim_geography │◄──┐
│ (PK id)      │   │
└──────────────┘   │
                   │  FK geography_id
┌──────────────┐   │  ┌─────────────────────┐
│dim_road_     │◄──┼──│ fact_accident_event  │
│segment (PK)  │   │  │ (PK accident_id)    │
└──────────────┘   │  └──────────┬──────────┘
                   │             │ 1:N
┌──────────────┐   │             ▼
│ dim_source   │◄──┘  ┌─────────────────────┐
│ (PK id)      │      │ fact_accident_person │
└──────────────┘      │ (PK person_event_id) │
                      └─────────────────────┘
┌──────────────┐
│  dim_time    │      ── Marts (pre-aggregated) ──
│ (2020-2030)  │      mart_accident_summary
└──────────────┘      mart_accident_hotspot
                      mart_province_year
                      mart_province_road
```

---

## 3. Application Tables (Chat-/ChatV1 owned)

### 3.1 `users` — ระบบผู้ใช้

| Column | Type | Nullable | Default | คำอธิบาย |
|--------|------|----------|---------|---------|
| `id` | SERIAL | NOT NULL | auto-increment | Primary key |
| `name` | VARCHAR(255) | NOT NULL | — | ชื่อผู้ใช้ |
| `email` | VARCHAR(255) | NOT NULL | — | อีเมล (unique) |
| `password` | VARCHAR(255) | NOT NULL | — | รหัสผ่าน (⚠️ plaintext ใน Chat-, bcrypt ใน ChatV1) |
| `role` | VARCHAR(20) | NOT NULL | `'user'` | สิทธิ์: `'admin'` หรือ `'user'` |
| `approved` | BOOLEAN | NOT NULL | `FALSE` | อนุมัติโดย admin แล้วหรือยัง |
| `disabled` | BOOLEAN | NOT NULL | `FALSE` | ถูก admin ระงับหรือไม่ |
| `created_at` | TIMESTAMP | NOT NULL | `NOW()` | วันที่ลงทะเบียน |
| `last_login` | TIMESTAMP | YES | `NULL` | เข้าสู่ระบบครั้งล่าสุด |
| `updated_at` | TIMESTAMP | NOT NULL | `NOW()` | อัปเดตล่าสุด (auto trigger) |

**Constraints**: PK(id), UNIQUE(email), CHECK(role IN ('admin','user'))  
**Indexes**: `idx_users_email`, `idx_users_approved`, `idx_users_disabled`  
**Trigger**: `update_users_updated_at` → auto-set updated_at = NOW()

### 3.2 `chat_sessions` — ประวัติการสนทนา

| Column | Type | Nullable | Default | คำอธิบาย |
|--------|------|----------|---------|---------|
| `id` | VARCHAR(255) | NOT NULL | — | Session ID (client-generated UUID) |
| `user_id` | INTEGER | NOT NULL | — | FK → users.id |
| `title` | VARCHAR(500) | NOT NULL | `'แชทใหม่'` | ชื่อ session |
| `created_at` | TIMESTAMP | NOT NULL | `NOW()` | วันที่สร้าง |
| `updated_at` | TIMESTAMP | NOT NULL | `NOW()` | กิจกรรมล่าสุด |

**Constraints**: PK(id), FK(user_id → users.id)  
**Indexes**: `idx_chat_sessions_user_id`, `idx_chat_sessions_updated_at`

### 3.3 `chat_messages` — ข้อความในการสนทนา

| Column | Type | Nullable | Default | คำอธิบาย |
|--------|------|----------|---------|---------|
| `id` | SERIAL | NOT NULL | auto-increment | Primary key |
| `session_id` | VARCHAR(255) | NOT NULL | — | FK → chat_sessions.id (CASCADE) |
| `role` | VARCHAR(20) | NOT NULL | — | `'user'`, `'assistant'`, `'system'` |
| `content` | TEXT | NOT NULL | `''` | เนื้อหาข้อความ (Markdown) |
| `images` | JSONB | YES | `NULL` | Array of image URLs |
| `charts` | JSONB | YES | `NULL` | Array of ChartSpec objects |
| `tables` | JSONB | YES | `NULL` | Array of TableSpec objects |
| `code_blocks` | JSONB | YES | `NULL` | Array of {code, language} |
| `plan_content` | TEXT | YES | `NULL` | Markdown แผนงาน |
| `created_at` | TIMESTAMP | NOT NULL | `NOW()` | วันที่สร้าง |

**Constraints**: PK(id), FK(session_id → chat_sessions.id ON DELETE CASCADE)  
**Indexes**: `idx_chat_messages_session_id`, `idx_chat_messages_content_gin` (full-text search)

### 3.4 `planning_history` — ประวัติ Planning

| Column | Type | Nullable | Default | คำอธิบาย |
|--------|------|----------|---------|---------|
| `id` | SERIAL | NOT NULL | auto-increment | Primary key |
| `session_id` | VARCHAR(255) | YES | `NULL` | FK → chat_sessions.id (SET NULL) |
| `user_id` | INTEGER | YES | `NULL` | FK → users.id (SET NULL) |
| `selected_tool` | VARCHAR(100) | YES | `NULL` | เครื่องมือ AI |
| `query` | TEXT | YES | `NULL` | คำถามต้นฉบับ |
| `files` | JSONB | YES | `NULL` | ไฟล์ที่เกี่ยวข้อง |
| `response` | TEXT | YES | `NULL` | ผลลัพธ์จาก AI |
| `status` | VARCHAR(50) | YES | `'completed'` | สถานะ |
| `duration_ms` | INTEGER | YES | `NULL` | เวลาประมวลผล (ms) |
| `created_at` | TIMESTAMP | NOT NULL | `NOW()` | วันที่สร้าง |

### 3.5 `file_apa_metadata` — Metadata ไฟล์ APA

| Column | Type | Nullable | Default | คำอธิบาย |
|--------|------|----------|---------|---------|
| `id` | SERIAL | NOT NULL | auto-increment | Primary key |
| `file_name` | VARCHAR(500) | NOT NULL | — | ชื่อไฟล์ |
| `file_path` | VARCHAR(1000) | NOT NULL | `'/'` | path ใน MinIO |
| `mime_type` | VARCHAR(100) | YES | `NULL` | ประเภทไฟล์ |
| `size_bytes` | BIGINT | YES | `NULL` | ขนาดไฟล์ |
| `apa_json` | JSONB | NOT NULL | — | APA metadata |
| `created_at` | TIMESTAMP | NOT NULL | `NOW()` | สกัดครั้งแรก |
| `updated_at` | TIMESTAMP | NOT NULL | `NOW()` | สกัดครั้งล่าสุด |

**Constraints**: PK(id), UNIQUE(file_name, file_path)

**โครงสร้าง `apa_json`**:
```json
{
  "abstract": "บทคัดย่อ",
  "keywords": {"thai": ["คำสำคัญ"], "english": ["keywords"]},
  "references": ["รายการอ้างอิง APA format"],
  "projectInfo": {
    "titleThai": "ชื่อโครงการ", "titleEnglish": "Title",
    "proposalCode": "รหัส", "budgetYear": "ปี",
    "university": "มหาวิทยาลัย", "projectCode": "รหัสโครงการ",
    "totalBudget": "งบประมาณ", "otherInfo": "อื่นๆ"
  },
  "researchers": [{"name": "ชื่อ", "role": "หัวหน้า", "affiliation": "สังกัด"}],
  "documentType": "ประเภท", "additionalInfo": "ข้อมูลเพิ่มเติม"
}
```

### 3.6 Domain Data Tables (Chat- side)

#### `diabetes` — เบาหวาน

| Column | Type | คำอธิบาย |
|--------|------|---------|
| `a_name` | TEXT | ชื่อพื้นที่/หน่วยงาน |
| `target` | INTEGER | เป้าหมายจำนวนผู้ป่วย |
| `result` | INTEGER | ผลรวมทั้งปี |
| `result1`-`result12` | INTEGER | ผลรายเดือน (ต.ค. - ก.ย.) |

#### `bipola` (mental health) — Dynamic schema จาก CSV import

---

## 4. Agent Analytics Tables

### 4.1 Shared Core Dimensions (Migration 001)

#### `dim_geography` — มิติพื้นที่
| Column | Type | คำอธิบาย |
|--------|------|---------|
| `geography_id` | SERIAL (PK) | |
| `province_name` | VARCHAR | จังหวัด |
| `district_name` | VARCHAR | อำเภอ |
| `subdistrict_name` | VARCHAR | ตำบล |
| `latitude` | DOUBLE PRECISION | ละติจูด |
| `longitude` | DOUBLE PRECISION | ลองจิจูด |

**UNIQUE**: (province_name, district_name, subdistrict_name)

#### `dim_time` — มิติเวลา (Pre-populated 2020-2030)
| Column | Type | คำอธิบาย |
|--------|------|---------|
| `time_id` | SERIAL (PK) | |
| `full_date` | DATE | วันที่เต็ม |
| `day_of_week` | INTEGER | วันในสัปดาห์ |
| `month_no` | INTEGER | เดือน (1-12) |
| `year_no` | INTEGER | ปี |
| `hour_no` | INTEGER | ชั่วโมง |

#### `dim_road_segment` — มิติถนน
| Column | Type | คำอธิบาย |
|--------|------|---------|
| `road_segment_id` | SERIAL (PK) | |
| `road_name` | VARCHAR | ชื่อถนน |
| `road_code` | VARCHAR | รหัสสายทาง |
| `road_type` | VARCHAR | ประเภทถนน |
| `geography_id` | INTEGER (FK) | พื้นที่ |
| `km_marker` | DOUBLE PRECISION | กม. |

#### `dim_source`, `dim_population_group`, `dim_facility`
Dimension tables เสริม สำหรับ metadata แหล่งข้อมูล, กลุ่มประชากร, สถานพยาบาล

### 4.2 Document RAG Tables (Migration 002)

#### `document_registry` — ทะเบียนเอกสาร
| Column | Type | คำอธิบาย |
|--------|------|---------|
| `document_id` | SERIAL (PK) | |
| `title` | VARCHAR | ชื่อเอกสาร |
| `topic` | VARCHAR | หัวข้อ |
| `document_type` | VARCHAR | ประเภท (PDF/DOCX) |
| `effective_date` | DATE | วันที่มีผล |
| `status` | VARCHAR | สถานะ (active/archived) |

#### `indicator_catalog` — ตัวชี้วัดสุขภาพ
| Column | Type | คำอธิบาย |
|--------|------|---------|
| `indicator_code` | VARCHAR (PK) | รหัส (ACC-001 ถึง ACC-006) |
| `indicator_name` | VARCHAR | ชื่อตัวชี้วัด |
| `definition` | TEXT | คำจำกัดความ |
| `unit_name` | VARCHAR | หน่วย |
| `preferred_chart` | VARCHAR | ประเภทกราฟที่เหมาะสม |

### 4.3 Evidence & Citation Tables (Migration 010 🆕)

> **รายละเอียดเต็ม**: ดู `Agent/doc/CITATION_EVIDENCE_AGENT.md`

#### `evidence_registry` — ทะเบียนหลักฐาน

| Column | Type | Nullable | Default | คำอธิบาย |
|--------|------|----------|---------|---------|
| `evidence_id` | VARCHAR(20) | NOT NULL | — | Primary key (EV-001) |
| `session_id` | VARCHAR(255) | YES | — | Chat session ที่สร้าง |
| `evidence_type` | VARCHAR(20) | NOT NULL | — | `document` \| `database` \| `api` \| `thaijo_article` \| `notebooklm_pdf` |
| `topic` | VARCHAR(100) | YES | `'general'` | โดเมน (accident, mental_health, etc.) |
| `source_ref` | VARCHAR(500) | NOT NULL | — | ชื่อไฟล์หรือชื่อตาราง |
| `title` | VARCHAR(500) | YES | — | ชื่อเอกสาร/dataset |
| `section_label` | VARCHAR(200) | YES | — | Section/heading ภายในเอกสาร |
| `page_ref` | VARCHAR(50) | YES | — | หน้าที่อ้างอิง |
| `chunk_id` | VARCHAR(255) | YES | — | ID ใน `document_embeddings` table |
| `chunk_index` | INTEGER | YES | — | ลำดับ chunk ในเอกสาร |
| `query_signature` | VARCHAR(64) | YES | — | SHA-256 ของ SQL query |
| `query_params` | JSONB | YES | — | พารามิเตอร์ query |
| `geography_ref` | VARCHAR(200) | YES | — | จังหวัด/พื้นที่ |
| `time_range_ref` | VARCHAR(100) | YES | — | ช่วงเวลา |
| `text_snippet` | TEXT | YES | — | ข้อความสำคัญ (max 500 chars) |
| `trust_level` | VARCHAR(20) | YES | `'medium'` | `high` \| `medium` \| `low` |
| `original_url` | VARCHAR(1000) | YES | — | minio://... หรือ postgresql://... |
| `open_url` | VARCHAR(1000) | YES | — | /api/documents/open/{id} |
| `used_in_objects` | TEXT[] | YES | `'{}'` | array ของ object IDs ที่ใช้ evidence นี้ |
| `extracted_at` | TIMESTAMP | YES | `NOW()` | วันที่สกัด |
| `created_at` | TIMESTAMP | YES | `NOW()` | วันที่สร้าง |

**Constraints**: PK(evidence_id)  
**Indexes**: `idx_ev_session`, `idx_ev_source`, `idx_ev_topic`, `idx_ev_query_sig`

#### `claim_evidence_link` — ความสัมพันธ์ claim↔evidence

| Column | Type | Nullable | Default | คำอธิบาย |
|--------|------|----------|---------|---------|
| `link_id` | BIGSERIAL | NOT NULL | auto-increment | Primary key |
| `session_id` | VARCHAR(255) | YES | — | Chat session |
| `claim_id` | VARCHAR(20) | NOT NULL | — | CL-001 |
| `claim_text` | TEXT | YES | — | ข้อสรุป |
| `claim_type` | VARCHAR(50) | YES | — | statistic \| comparison \| trend \| ... |
| `section_id` | VARCHAR(100) | YES | — | Section ในรายงาน |
| `object_type` | VARCHAR(20) | YES | `'text'` | text \| chart \| table |
| `object_id` | VARCHAR(100) | YES | — | ID ของ chart/table/paragraph |
| `evidence_id` | VARCHAR(20) | NOT NULL | — | FK → evidence_registry |
| `support_level` | VARCHAR(30) | YES | `'supported'` | supported \| partially_supported \| insufficient \| conflicting |
| `evidence_strength` | VARCHAR(20) | YES | `'moderate'` | strong \| moderate \| weak |
| `confidence_note` | TEXT | YES | — | คำอธิบาย |
| `citation_code` | VARCHAR(20) | YES | — | C-001 |
| `created_at` | TIMESTAMP | YES | `NOW()` | วันที่สร้าง |

**Constraints**: PK(link_id), FK(evidence_id → evidence_registry)  
**Indexes**: `idx_cel_session`, `idx_cel_claim`, `idx_cel_evidence`, `idx_cel_citation`

---

### 4.4 Accident Domain (Migration 003)

#### `fact_accident_event` — เหตุการณ์อุบัติเหตุ (Normalized)
| Column | Type | คำอธิบาย |
|--------|------|---------|
| `accident_id` | SERIAL (PK) | |
| `geography_id` | INTEGER (FK → dim_geography) | พื้นที่ |
| `road_segment_id` | INTEGER (FK → dim_road_segment) | ถนน |
| `source_id` | INTEGER (FK → dim_source) | แหล่งข้อมูล |
| `event_datetime` | TIMESTAMP | วันเวลาเกิดเหตุ |
| `weather_condition` | VARCHAR | สภาพอากาศ |
| `road_condition` | VARCHAR | สภาพถนน |
| `light_condition` | VARCHAR | สภาพแสง |
| `accident_type` | VARCHAR | ประเภทอุบัติเหตุ |
| `severity_level` | VARCHAR | ความรุนแรง |
| `vehicle_type` | VARCHAR | ประเภทยานพาหนะ |
| `injured_count` | INTEGER | จำนวนบาดเจ็บ |
| `serious_injured` | INTEGER | จำนวนบาดเจ็บหนัก |
| `death_count` | INTEGER | จำนวนเสียชีวิต |
| `csv_year` | INTEGER | ปีจาก CSV (2020-2026) |
| `latitude` | DOUBLE PRECISION | ละติจูดจุดเกิดเหตุ |
| `longitude` | DOUBLE PRECISION | ลองจิจูดจุดเกิดเหตุ |

**Indexes**: `event_datetime`, `geography_id`, `severity_level`, `csv_year`  
**UNIQUE**: Composite constraint ป้องกันข้อมูลซ้ำ (Migration 008)

#### `fact_accident_person` — ผู้ประสบเหตุ
| Column | Type | คำอธิบาย |
|--------|------|---------|
| `person_event_id` | SERIAL (PK) | |
| `accident_id` | INTEGER (FK) | เหตุการณ์ |
| `age` | INTEGER | อายุ |
| `sex` | VARCHAR | เพศ |
| `role_in_event` | VARCHAR | บทบาท (ผู้ขับ/ผู้โดยสาร) |
| `injury_level` | VARCHAR | ระดับการบาดเจ็บ |
| `helmet_used` | BOOLEAN | สวมหมวกกันน็อก |
| `seatbelt_used` | BOOLEAN | คาดเข็มขัดนิรภัย |

### 4.4 Analytic Marts

#### `mart_accident_summary` — สรุปรายเดือน
| Column | Type | Grain |
|--------|------|-------|
| `year_no` | INTEGER | ปี |
| `month_no` | INTEGER | เดือน |
| `geography_id` | INTEGER (FK) | พื้นที่ |
| `province_name` | VARCHAR | จังหวัด (denormalized) |
| `accident_count` | INTEGER | จำนวนอุบัติเหตุ |
| `injured_count` | INTEGER | จำนวนบาดเจ็บ |
| `death_count` | INTEGER | จำนวนเสียชีวิต |
| `high_risk_timeband` | VARCHAR | ช่วงเวลาเสี่ยง |
| `dominant_road_cond` | VARCHAR | สภาพถนนหลัก |

**ใช้โดย**: `build_accident_trend_chart`, `build_monthly_death_bar_chart`

#### `mart_accident_hotspot` — จุดเสี่ยง
| Column | Type | Grain |
|--------|------|-------|
| `hotspot_id` | SERIAL (PK) | |
| `geography_id` | INTEGER (FK) | พื้นที่ |
| `road_segment_id` | INTEGER (FK) | ถนน |
| `accident_count` | INTEGER | จำนวนอุบัติเหตุ |
| `injured_count` | INTEGER | จำนวนบาดเจ็บ |
| `death_count` | INTEGER | จำนวนเสียชีวิต |
| `hotspot_score` | DOUBLE PRECISION | คะแนนเสี่ยง |
| `dominant_timeband` | VARCHAR | ช่วงเวลาหลัก |

**ใช้โดย**: `build_hotspot_bar_chart`, `get_accident_hotspots`

#### `mart_province_year` — สรุปรายจังหวัดรายปี
| Column | Type | Grain |
|--------|------|-------|
| `province_name` | VARCHAR | จังหวัด |
| `year_no` | INTEGER | ปี |
| `accident_count` | INTEGER | อุบัติเหตุ |
| `injured_count` | INTEGER | บาดเจ็บ |
| `serious_injured` | INTEGER | บาดเจ็บหนัก |
| `death_count` | INTEGER | เสียชีวิต |
| `road_count` | INTEGER | จำนวนถนน |
| `top_vehicle` | VARCHAR | ยานพาหนะหลัก |
| `top_cause` | VARCHAR | สาเหตุหลัก |
| `top_timeband` | VARCHAR | ช่วงเวลาหลัก |
| `top_weather` | VARCHAR | สภาพอากาศหลัก |

**ใช้โดย**: `build_province_year_trend_chart`, `get_province_year_summary`

#### `mart_province_road` — สรุปรายถนน
| Column | Type | Grain |
|--------|------|-------|
| `province_name` | VARCHAR | จังหวัด |
| `road_name` | VARCHAR | ชื่อถนน |
| `road_code` | VARCHAR | รหัสสายทาง |
| `year_no` | INTEGER | ปี |
| `accident_count` | INTEGER | อุบัติเหตุ |
| `injured_count` | INTEGER | บาดเจ็บ |
| `serious_injured` | INTEGER | บาดเจ็บหนัก |
| `death_count` | INTEGER | เสียชีวิต |
| `hotspot_score` | DOUBLE PRECISION | คะแนนเสี่ยง |
| `dominant_cause` | VARCHAR | สาเหตุหลัก |
| `dominant_vehicle` | VARCHAR | ยานพาหนะหลัก |

**ใช้โดย**: `build_province_roads_bar_chart`, `get_province_roads`

### 4.5 pgvector (Vector Search) Tables (Migration 011 🆕)

#### `document_embeddings` — Vector Embeddings (แทน ChromaDB)

| Column | Type | Nullable | Default | คำอธิบาย |
|--------|------|----------|---------|----------|
| `id` | VARCHAR(64) | NOT NULL | — | Primary key (MD5 hash ของ source::chunk_index) |
| `collection` | VARCHAR(100) | NOT NULL | `'musya_documents'` | ชื่อ collection |
| `document` | TEXT | NOT NULL | — | เนื้อหา chunk |
| `embedding` | vector(3072) | YES | — | Vector embedding (3072 มิติ — Gemini gemini-embedding-001) |
| `source` | VARCHAR(500) | YES | — | ชื่อไฟล์ใน MinIO |
| `title` | VARCHAR(500) | YES | — | ชื่อเอกสาร |
| `topic` | VARCHAR(100) | YES | — | โดเมน (accident, mental_health) |
| `chunk_index` | INTEGER | YES | -1 | ลำดับ chunk |
| `total_chunks` | INTEGER | YES | 0 | จำนวน chunk ทั้งหมด |
| `page_ref` | VARCHAR(50) | YES | — | หน้าที่อ้างอิง |
| `section_label` | VARCHAR(200) | YES | — | Section/heading |
| `total_pages` | INTEGER | YES | 0 | จำนวนหน้าทั้งหมด |
| `created_at` | TIMESTAMP | YES | `NOW()` | วันที่เพิ่ม |

**Indexes**:
- `idx_de_collection` — B-tree บน `collection`
- `idx_de_source` — B-tree บน `source`
- `idx_de_topic` — B-tree บน `topic`
- ❌ ไม่มี vector index (pgvector HNSW/IVFFlat รองรับสูงสุด 2000 มิติ — ใช้ exact cosine scan แทน)

**Embedding Model**: `models/gemini-embedding-001` via Google Gemini API (3072 มิติ, API-based — ไม่ต้องดาวน์โหลด model ในเครื่อง)

**SDK**: `google-genai` v1.65.0 (`from google import genai`)

### 4.6 Migration History

| Migration | ไฟล์ | การเปลี่ยนแปลงหลัก |
|-----------|------|-------------------|
| **001** | `001_shared_core.sql` | dim_geography, dim_time, dim_source, dim_population_group, dim_facility |
| **002** | `002_document_rag.sql` | document_registry, indicator_catalog |
| **003** | `003_accident_domain.sql` | fact_accident_event, fact_accident_person, dim_road_segment, mart_accident_summary, mart_accident_hotspot |
| **004** | `004_seed_accident_mockup.sql` | Mock data สำหรับทดสอบ |
| **005** | `005_enhance_road_geo.sql` | เพิ่ม road_code, geography_id, km_marker ใน dim_road_segment |
| **006** | `006_province_marts.sql` | mart_province_year, mart_province_road |
| **007** | `007_all_years_province.sql` | serious_injured, csv_year ใน fact; province views |
| **008** | `008_prevent_duplicates.sql` | UNIQUE constraints ป้องกันข้อมูลซ้ำ |
| **009** | `009_add_coordinates_to_events.sql` | latitude, longitude ใน fact_accident_event |
| **010** | `010_evidence_citation.sql` | evidence_registry, claim_evidence_link |
| **011** | `011_pgvector.sql` | 🆕 pgvector extension + document_embeddings (แทน ChromaDB) |
| **012** | `012_document_upload_enhanced.sql` | 🆕 Enhanced document_registry: file_path, file_size, APA metadata, upload_method, ingestion_status, source_type, external_url |
| **013** | `013_apa_approval_status.sql` | 🆕 ADD COLUMN apa_approval_status (pending/draft/approved/rejected) |
| **014** | `014_populate_document_chunks.sql` | 🗑️ DROP TABLE document_chunks (ChromaDB-era obsolete table removed) |
| **015** | `015_thaijo_evidence.sql` | 🆕 Adds thaijo_* columns to evidence_registry (thaijo_pdf_url, thaijo_reference, thaijo_summary) |

**วิธีรัน Migration**:
```bash
psql -U postgres -d chat-aio -f database/001_shared_core.sql
psql -U postgres -d chat-aio -f database/002_document_rag.sql
# ... ไปจนถึง 015
psql -U postgres -d chat-aio -f database/015_thaijo_evidence.sql  # ThaiJO evidence support
python database/import_subdistrict_csv.py                           # Import CSV data
```

---

## 5. Vector Store (pgvector — PostgreSQL Native)

| รายการ | รายละเอียด |
|--------|-----------|
| **Platform** | PostgreSQL 16 + pgvector extension v0.8+ |
| **Docker Image** | `pgvector/pgvector:pg16` |
| **Table** | `document_embeddings` |
| **Collection** | `musya_documents` (ENV: `PGVECTOR_COLLECTION`) |
| **Embedding Model** | `models/gemini-embedding-001` via Google Gemini API (3072-dim, API-based) |
| **SDK** | `google-genai` v1.65.0 (`from google import genai`) |
| **Index Type** | ❌ ไม่มี ANN index (pgvector รอง ≤ 2000-dim เท่านั้น) — ใช้ exact cosine scan |
| **Chunk Size** | 1,000 characters |
| **Chunk Overlap** | 200 characters |
| **Distance Metric** | Cosine similarity (`<=>` operator) |

> **เหตุผลที่เปลี่ยน**: รวม vector store เข้ากับ PostgreSQL ทำให้ใช้ database เดียว ดูข้อมูลผ่าน DBeaver/pgAdmin ได้ทันที ไม่ต้องติดตั้ง ChromaDB แยก

### Document Ingestion Flows

**Bulk ingest (MinIO scan)**:
```
POST /api/ingest
  ├── 1. List files from MinIO bucket (uploads)
  ├── 2. For each file:
  │   ├── PDF → PyMuPDF (fitz) → text
  │   ├── DOCX → python-docx → text
  │   └── TXT/MD → direct read
  ├── 3. Split into chunks (langchain-text-splitters)
  ├── 4. Embed chunks (Gemini API `gemini-embedding-001` → 3072-dim vectors)
  ├── 5. Upsert into document_embeddings (ON CONFLICT DO UPDATE)
  └── 6. Register in document_registry table
```

**Single-file upload (new)**:
```
POST /api/documents/upload  (multipart/form-data)
  ├── 1. Validate file type (.pdf/.docx/.txt/.md) + size (≤ MAX_UPLOAD_SIZE_MB)
  ├── 2. Upload to MinIO: uploads/{year}/{month}/{filename}
  ├── 3. INSERT into document_registry (ingestion_status='processing')
  ├── 4. ingest_single_document(): extract → chunk → embed → pgvector
  ├── 5. UPDATE document_registry SET ingestion_status='completed', chunk_count=N
  └── 6. Return {document_id, chunks_ingested, apa_citation, source_link}
```

### Search Pattern
```python
search_documents(query="อุบัติเหตุเชียงใหม่", n_results=5)
# → embed query → pgvector cosine search → ORDER BY embedding <=> query_vec
# → top-k relevant chunks with similarity score
```

### View Data (DBeaver / pgAdmin / psql)
```sql
-- ดูเอกสารทั้งหมด
SELECT source, COUNT(*) chunks FROM document_embeddings GROUP BY source;

-- Semantic search (SQL)
SELECT source, page_ref, LEFT(document, 200) AS snippet,
       1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM document_embeddings
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
```

---

## 6. Object Storage (MinIO)

| รายการ | รายละเอียด |
|--------|-----------|
| **Endpoint** | localhost:9000 (API), localhost:9001 (Console) |
| **Access Key** | minioadmin |
| **Secret Key** | minioadmin |
| **Bucket** | `uploads` |
| **SSL** | false (development) |

### File Organization
```
uploads/
├── folder1/
│   ├── .folder          ← marker file (empty, indicates folder exists)
│   ├── report.pdf
│   └── data.docx
└── standalone.pdf
```

---

## 7. API Reference — Agent Backend (Port 8000)

### 7.1 Core APIs (ปัจจุบัน ✅)

| Method | Path | คำอธิบาย |
|--------|------|---------|
| `GET` | `/` | Root info + API links |
| `GET` | `/api/health` | Health check (PostgreSQL + MinIO + pgvector status) |
| `POST` | `/api/chat` | Process chat → 10-agent pipeline → AgentResponse |
| `POST` | `/api/chat/unified` | Auto-route to chat or policy_brief pipeline |
| `POST` | `/api/chat/stream` | SSE streaming with agent progress |
| `POST` | `/api/ingest` | Bulk ingest documents (MinIO scan → extract → pgvector embeddings) |
| `POST` | `/api/policy-brief` | Policy Brief pipeline (5 จังหวัด, 3 domains) |
| `POST` | `/api/policy-brief/stream` | Policy Brief SSE streaming |
| `POST` | `/api/accident-policy/zone10` | Accident Policy pipeline (5 จังหวัด Zone 10) |
| `GET`  | `/api/accident-policy/zone10/data` | ดึงข้อมูล 7 policy queries (raw SQL) |
| `POST` | `/api/accident-chat/ask` | Accident Chat Pipeline |
| `POST` | `/api/accident-chat/ask/stream` | Accident Chat SSE streaming |
| `POST` | `/api/accident-chat/quick` | Raw SQL data for accident chat tools |

### 7.1B Database Explorer APIs (✅ Implemented)

| Method | Path | คำอธิบาย |
|--------|------|---------|
| `GET`  | `/api/db/tables` | List all tables |
| `GET`  | `/api/db/tables/{table}/columns` | List columns for a table |
| `GET`  | `/api/db/tables/{table}/rows` | Paginated rows |

### 7.1C ThaiJO APIs (✅ Implemented)

| Method | Path | คำอธิบาย |
|--------|------|---------|
| `POST` | `/api/thaijo/search` | ค้นหาบทความวิชาการจาก TCI-THAIJO (ผ่าน ThaiJO microservice) |
| `GET` | `/api/thaijo/status` | ตรวจสถานะ ThaiJO microservice |

### 7.1C MinIO Browse APIs (✅ Implemented)

| Method | Path | คำอธิบาย |
|--------|------|---------|
| `GET` | `/api/documents/minio/tree` | MinIO folder tree view |
| `GET` | `/api/documents/minio/browse` | Browse MinIO prefix |
| `GET` | `/api/documents/minio/read` | Read file text preview |
| `POST` | `/api/documents/minio/apa-draft` | AI-generated APA metadata draft |
| `POST` | `/api/documents/minio/approve` | Approve draft & trigger ingest |
| `POST` | `/api/documents/analyze-upload` | Analyze uploaded file for APA |
| `GET` | `/api/documents/registry` | List all registered documents |

### 7.2 Evidence & Document Access APIs (Citation & Evidence ✅)

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `GET` | `/api/documents/open/{document_id}` | เปิดดูเอกสารต้นฉบับ (file stream) — รองรับ `?page=12` |
| `GET` | `/api/documents/open/{document_id}/info` | ข้อมูลเอกสาร (title, file_path, total_pages, mime_type) |
| `GET` | `/api/evidence/{evidence_id}` | ดู EvidenceItem JSON พร้อม open_url |
| `GET` | `/api/evidence/{evidence_id}/query` | สำหรับ database evidence — แสดง SQL + result rows |
| `GET` | `/api/evidence/session/{session_id}` | รายการ evidence ทั้งหมดของ session |
| `GET` | `/api/evidence/session/{session_id}/coverage` | Coverage report ของ session |

> **รายละเอียดเต็ม**: ดู `Agent/doc/CITATION_EVIDENCE_AGENT.md` Section 7

### 7.2B Document Upload & Management APIs (Migration 012 🆕)

**Upload** (`src/routers/upload.py`):

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `POST` | `/api/documents/upload` | Upload file → MinIO → register → auto-ingest → pgvector |
| `POST` | `/api/documents/upload-url` | Download external URL → MinIO → register → auto-ingest |

**Document Management** (`src/routers/documents.py`):

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `GET` | `/api/documents` | List documents (filter: status/topic/source_type/search, pagination) |
| `GET` | `/api/documents/{document_id}` | Document detail + APA metadata + chunks preview |
| `PATCH` | `/api/documents/{document_id}` | Update metadata (title, APA fields, topic) |
| `DELETE` | `/api/documents/{document_id}` | Delete from registry + pgvector + MinIO |
| `POST` | `/api/documents/{document_id}/reingest` | Re-embed document (after model change) |

**Citation** (`src/routers/citation.py`):

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `GET` | `/api/citations/session/{session_id}` | APA-formatted citations for a chat session |
| `GET` | `/api/citations/document/{document_id}` | APA reference + inline citation for a document |

---

### 7.3 AI Utility APIs (Phase 2B — ย้ายจาก Chat- ⬆️)

| Method | Path | คำอธิบาย | แหล่งเดิม (Chat-) |
|--------|------|---------|-------------------|
| `POST` | `/api/ai/detect-tool` | ตรวจจับเครื่องมือ AI จากข้อความ | `ChatInterface.aiDetectTool()` |
| `POST` | `/api/ai/plan-apis` | วางแผนเรียก domain API | `ChatInterface.aiPlanAdminApiCalls()` |
| `POST` | `/api/ai/select-files` | เลือกเอกสารที่เกี่ยวข้อง | `ChatInterface.searchRelevantFiles()` |
| `POST` | `/api/ai/generate-sql` | แปล NL→SQL | `GeminiAIService.generateSQL()` |
| `POST` | `/api/ai/summarize` | สรุปข้อความ | `GeminiAIService.summarize()` |

### 7.3 Domain Query APIs (Phase 2 — ย้ายจาก Chat- ⬆️)

| Method | Path | คำอธิบาย | แหล่งเดิม (Chat-) |
|--------|------|---------|-------------------|
| `POST` | `/api/domain/accident` | NL→SQL query อุบัติเหตุ | `POST /api/admin/accident` |
| `POST` | `/api/domain/diabetes` | NL→SQL query เบาหวาน | `POST /api/admin/diabetes` |
| `POST` | `/api/domain/mental` | NL→SQL query สุขภาพจิต | `POST /api/admin/mental` |
| `POST` | `/api/domain/query` | Generic table query + pagination | `GET /api/admin/db-table` |
| `POST` | `/api/domain/csv-import` | Import CSV → auto-create table | `POST /api/admin/csv-import` |

### 7.4 Document APIs (Phase 2 — ย้ายจาก Chat- ⬆️)

| Method | Path | คำอธิบาย | แหล่งเดิม (Chat-) |
|--------|------|---------|-------------------|
| `POST` | `/api/document/extract-apa` | สกัด APA metadata จากเอกสาร | `POST /api/files/apa` |
| `POST` | `/api/document/extract-apa/bulk` | Bulk APA extraction | `POST /api/files/apa/bulk` |

### 7.5 External Integration APIs (Phase 2 — ย้ายจาก Chat- ⬆️)

| Method | Path | คำอธิบาย | แหล่งเดิม (Chat-) |
|--------|------|---------|-------------------|
| `GET` | `/api/external/weather` | พยากรณ์อากาศ (Open-Meteo) | `GET /api/weather` |
| `POST` | `/api/external/thaijo` | ค้นหาวารสาร ThaiJO | `POST /api/admin/thaijo` |

### 7.6 Test APIs (Direct Tool Access)

| Method | Path | Tool Function |
|--------|------|--------------|
| `POST` | `/api/test/chart/accident_trend` | `build_accident_trend_chart` |
| `POST` | `/api/test/chart/hotspot` | `build_hotspot_bar_chart` |
| `POST` | `/api/test/chart/province_trend` | `build_province_year_trend_chart` |
| `POST` | `/api/test/chart/province_roads` | `build_province_roads_bar_chart` |
| `POST` | `/api/test/chart/time_dist` | `build_time_distribution_chart` |
| `POST` | `/api/test/chart/road_condition` | `build_road_condition_pie_chart` |
| `POST` | `/api/test/chart/monthly_death` | `build_monthly_death_bar_chart` |
| `POST` | `/api/test/tool/accident_summary` | `get_accident_summary` |
| `POST` | `/api/test/tool/hotspots` | `get_accident_hotspots` |
| `POST` | `/api/test/tool/geography` | `get_geography_profile` |
| `POST` | `/api/test/query` | Execute read-only SQL |

---

## 8. Request/Response Schemas

### 8.1 ChatRequest

```json
{
  "message": "สถิติอุบัติเหตุเชียงใหม่ปี 2025",
  "session_id": "optional-session-id",
  "user_id": "optional-user-id"
}
```

### 8.2 AgentResponse

```json
{
  "content": "## สรุปสาระสำคัญ\n...(Markdown ภาษาไทย)",
  "topic": "accident",
  "charts": [{
    "type": "line|bar|pie|doughnut",
    "title": "ชื่อกราฟ",
    "data": {"labels": [...], "datasets": [...]},
    "options": {},
    "source_note": "mart_province_year"
  }],
  "tables": [{
    "title": "ชื่อตาราง",
    "headers": ["col1", "col2"],
    "rows": [["val1", "val2"]]
  }],
  "citations": [{"citation_code": "C-001", "source_type": "document", "source_ref": "policy.pdf", "citation_text": "(กรมทางหลวง, 2025, หน้า 12)", "bibliography_text": "กรมทางหลวง. (2025). *นโยบายความปลอดภัย*. กระทรวงคมนาคม."}],
  "follow_ups": ["คำถาม 1", "คำถาม 2", "คำถาม 3"],
  "metadata": {"elapsed_seconds": 45.2, "agent_count": 10, "chart_count": 1}
}
```

### 8.3 ChartSpec (ใช้ร่วมกับ ChartRenderer.tsx)

```json
{
  "type": "line",
  "title": "แนวโน้มอุบัติเหตุรายปี",
  "data": {
    "labels": ["2020", "2021", "2022"],
    "datasets": [
      {
        "label": "อุบัติเหตุ",
        "data": [1200, 1150, 1100],
        "borderColor": "#FF6384",
        "backgroundColor": "rgba(255,99,132,0.2)"
      }
    ]
  },
  "options": {"responsive": true, "plugins": {"legend": {"position": "top"}}},
  "source_note": "mart_province_year"
}
```

### 8.4 Domain Query (Phase 2)

**Request**:
```json
{"message": "สถิติอุบัติเหตุเชียงใหม่ปี 2025"}
```

**Response**:
```json
{
  "sql": "SELECT ... FROM mart_province_year WHERE ...",
  "reply": "จังหวัดเชียงใหม่ในปี 2025 มีอุบัติเหตุ 920 ครั้ง ...",
  "total": 1,
  "rows": [{"province_name": "เชียงใหม่", "accident_count": 920, "death_count": 28}],
  "chart": {
    "type": "bar",
    "title": "สถิติอุบัติเหตุเชียงใหม่ 2025",
    "data": {"labels": ["อุบัติเหตุ","บาดเจ็บ","เสียชีวิต"], "datasets": [...]}
  }
}
```

---

## 9. Data Flow Patterns

### 9.1 Agent Chat Query (End-to-End — 10 agents)

```
Browser → POST /api/chat/unified → Agent Backend
  │
  ├── Agent 0: Request Router
  │   └── Classify → pipeline: "chat" | "policy_brief"
  │
  ├── Agent 1: Request Interpreter              [Fast LLM]
  │   └── LLM parse → {topics: ["อุบัติเหตุ"], geography: "เชียงใหม่", time_range: "2025"}
  │
  ├── Agent 2: Data Retrieval                   [Fast LLM]
  │   ├── search_documents("อุบัติเหตุเชียงใหม่") → pgvector → relevant chunks
  │   ├── get_province_year_summary("เชียงใหม่") → mart_province_year → JSON
  │   ├── get_province_roads("เชียงใหม่") → mart_province_road → JSON
  │   └── search_thaijo("อุบัติเหตุทางถนน เชียงใหม่") → ThaiJO articles
  │
  ├── Agent 3: SQL Specialist                   [Fast LLM]
  │   └── execute_custom_sql("SELECT ... FROM fact_accident_event ...") → rows
  │
  ├── Agent 4: Citation & Evidence              [Fast LLM]
  │   ├── Map data → EvidenceItem list → INSERT INTO evidence_registry
  │   ├── Map claims → ClaimEvidenceLink → INSERT INTO claim_evidence_link
  │   └── Generate APA citations (C-001~C-099 docs, C-100~C-199 DB, C-200~C-299 ThaiJO)
  │
  ├── Agent 5: Accident Analyst                 [Pro LLM]
  │   └── Synthesize → key_findings, trends, Haddon Matrix
  │
  ├── Agent 6: Chart Builder                    [Pro LLM]
  │   ├── build_province_year_trend_chart("เชียงใหม่") → ChartSpec JSON
  │   └── build_province_roads_bar_chart("เชียงใหม่") → ChartSpec JSON
  │
  ├── Agent 7: Research Synthesizer             [Pro LLM]
  │   └── Narrative prose → 4 blocks (1,200-2,000 คำ)
  │
  ├── Agent 8: Deep Analyst                     [Pro LLM]
  │   └── Root cause, policy gaps → 4 dimensions (1,000-1,500 คำ)
  │
  └── Agent 9: Report Composer                  [Pro LLM]
      └── Thai report (2,000-4,000 คำ) + follow_ups

  → AgentResponse {content, charts, tables, citations, follow_ups, metadata}
  → Browser renders: MessageList + ChartRenderer + TableRenderer
```

### 9.2 CSV Import Flow (Phase 2)

```
Admin uploads CSV
  │
  ▼
POST /api/domain/csv-import (FormData: file, tableName, mode)
  ├── 1. Parse CSV (csv-parse)
  ├── 2. Detect column types (number, date, boolean, text)
  ├── 3. If mode='replace': TRUNCATE TABLE
  ├── 4. CREATE TABLE IF NOT EXISTS (auto-detected schema)
  ├── 5. Batch INSERT (parameterized)
  └── 6. Return {inserted, skipped, errors}
```

### 9.3 Document Ingestion Flows (MinIO → pgvector)

**Bulk ingest from MinIO**:
```
POST /api/ingest
  ├── 1. List files in MinIO bucket (uploads)
  ├── 2. For each file:
  │   ├── Download from MinIO
  │   ├── Extract text (PyMuPDF for PDF, python-docx for DOCX)
  │   ├── Split into chunks (1000 chars, 200 overlap)
  │   ├── Generate embeddings (Gemini gemini-embedding-001, 3072-dim)
  │   └── Upsert into document_embeddings (ON CONFLICT DO UPDATE)
  └── 3. Return {ingested_count, total_chunks}
```

**Single-file upload (new, Migration 012)**:
```
POST /api/documents/upload  (or /upload-url for external URL)
  ├── 1. Validate: file type ∈ {.pdf,.docx,.txt,.md}, size ≤ MAX_UPLOAD_SIZE_MB
  ├── 2. upload_to_minio(uploads/{year}/{month}/{filename})
  ├── 3. INSERT document_registry (ingestion_status='processing', all APA fields)
  ├── 4. ingest_single_document(path, bytes, doc_id, topic)
  │   ├── extract_text() → text
  │   ├── _splitter.split_text() → chunks[]
  │   ├── _embed(chunks) → vectors[]
  │   └── add_documents() → pgvector upsert
  ├── 5. UPDATE document_registry SET ingestion_status='completed', chunk_count=N
  └── 6. Return {document_id, chunks_ingested, apa_citation, source_link}
```

**Delete document (cascading)**:
```
DELETE /api/documents/{id}
  ├── delete_document_chunks(file_path) → DELETE FROM document_embeddings WHERE source=?  (document_chunks removed in 014)
  ├── delete_from_minio(minio_path)
  └── DELETE FROM document_registry WHERE document_id=?
```

---

## 10. ภาคผนวก

### A. Index Strategy Summary

**Application Tables**:
| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| users | idx_users_email | B-tree | Login lookup |
| users | idx_users_approved | B-tree | Approval filter |
| chat_sessions | idx_chat_sessions_user_id | B-tree | User's sessions |
| chat_sessions | idx_chat_sessions_updated_at | B-tree | Recent sessions |
| chat_messages | idx_chat_messages_session_id | B-tree | Session messages |
| chat_messages | idx_chat_messages_content_gin | GIN | Full-text search |

**pgvector Table**:
| Table | Index | Type | Purpose |
|-------|-------|------|------|
| document_embeddings | idx_de_collection | B-tree | Filter by collection |
| document_embeddings | idx_de_source | B-tree | Filter by source file |
| document_embeddings | (ไม่มี) | — exact cosine scan | 3072-dim เกินขีดจำกัด 2000-dim ของ pgvector |

**Agent Mart Tables**:
| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| mart_accident_summary | idx_mart_acc_ym | B-tree | Time-series (year, month) |
| mart_accident_hotspot | idx_hotspot_score | B-tree DESC | Top-N queries |
| fact_accident_event | idx_accident_datetime | B-tree | Time-range queries |
| fact_accident_event | idx_accident_geo | B-tree | Geographic queries |
| dim_geography | idx_geo_province | B-tree | Province lookup |

### B. Connection Pool Configuration

| Component | Library | Pool Type | Min | Max | Timeout |
|-----------|---------|-----------|-----|-----|---------|
| **Chat-** | pg (node-postgres) | Per-route Pool | — | 20 | idle: 30s |
| **ChatV1** | pg (node-postgres) | Singleton Pool (RW) | — | 20 | idle: 30s |
| **ChatV1** | pg (node-postgres) | Singleton Pool (RO) | — | 10 | idle: 30s |
| **Agent** | asyncpg | Async Pool | 2 | 10 | — |
| **Agent** | psycopg2 | Sync ThreadedPool | 1 | 5 | — |

> **⚠️ Chat- ปัญหา**: Pool ถูก instantiate ใหม่ทุก route file (15 copies)
> **✅ Agent**: Singleton pools จัดการผ่าน FastAPI lifespan

### C. SQL Query Patterns (Agent Tools)

**Time-Series** (mart_accident_summary):
```sql
SELECT year_no, month_no, accident_count, death_count
FROM mart_accident_summary
WHERE year_no >= 2023
ORDER BY year_no, month_no;
-- Performance: ~10ms (index scan)
```

**Province Lookup** (mart_province_year):
```sql
SELECT year_no, accident_count, death_count
FROM mart_province_year
WHERE province_name ILIKE '%เชียงใหม่%'
ORDER BY year_no;
-- Performance: ~5ms
```

**Top-N Hotspots** (mart_accident_hotspot):
```sql
SELECT hotspot_id, hotspot_score, accident_count, death_count
FROM mart_accident_hotspot
ORDER BY hotspot_score DESC
LIMIT 10;
-- Performance: ~2ms (index-only scan)
```

**Custom SQL** (execute_custom_sql tool):
```sql
-- Auto-validated: SELECT/WITH only
-- Auto-limited: LIMIT 1000 appended
SELECT province_name, SUM(death_count) as total_deaths
FROM mart_province_year
WHERE year_no = 2025
GROUP BY province_name
ORDER BY total_deaths DESC;
```

### D. Environment Variables Reference

```env
# ── Shared Database ──
DB_HOST=localhost
DB_PORT=5432
DB_NAME=chat-aio
DB_USER=postgres
DB_PASSWORD=1234

# ── Shared Object Storage ──
MINIO_ENDPOINT=localhost
MINIO_PORT=9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=uploads

# ── Agent Specific ──
GEMINI_API_KEY=...              # Google Gemini API key (required)
GEMINI_MODEL=gemini-2.0-flash
PGVECTOR_COLLECTION=musya_documents
EMBEDDING_MODEL=models/gemini-embedding-001
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# ── Document Upload (Migration 012) ──
MAX_UPLOAD_SIZE_MB=50           # Maximum file size per upload
ALLOWED_FILE_TYPES=.pdf,.docx,.txt,.md
AUTO_INGEST_ON_UPLOAD=true      # Auto-embed on upload
ALLOW_EXTERNAL_URL_IMPORT=true  # Allow POST /api/documents/upload-url
EXTERNAL_URL_TIMEOUT=30         # Seconds to wait for external URL download

# ── ThaiJO Integration ──
THAIJO_API_URL=http://72.61.120.205:8505/api/v1/thaijo
THAIJO_TIMEOUT=120              # Request timeout (seconds)
THAIJO_DEFAULT_SIZE=5           # Default number of results
THAIJO_MAX_SIZE=10              # Max results per query
THAIJO_ENABLED=true             # Enable/disable ThaiJO search

# ── Report Settings ──
REPORT_MAX_TOKENS=8192          # Max tokens for report generation
```

### E. Trigger Functions

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Applied to: users, chat_sessions, file_apa_metadata
```
//localhost:3000,http://127.0.0.1:3000

# ── Document Upload (Migration 012) ──
MAX_UPLOAD_SIZE_MB=50           # Maximum file size per upload
ALLOWED_FILE_TYPES=.pdf,.docx,.txt,.md
AUTO_INGEST_ON_UPLOAD=true      # Auto-embed on upload
ALLOW_EXTERNAL_URL_IMPORT=true  # Allow POST /api/documents/upload-url
EXTERNAL_URL_TIMEOUT=30         # Seconds to wait for external URL download

# ── ThaiJO Integration ──
THAIJO_API_URL=http://72.61.120.205:8505/api/v1/thaijo
THAIJO_TIMEOUT=120              # Request timeout (seconds)
THAIJO_DEFAULT_SIZE=5           # Default number of results
THAIJO_MAX_SIZE=10              # Max results per query
THAIJO_ENABLED=true             # Enable/disable ThaiJO search

# ── Report Settings ──
REPORT_MAX_TOKENS=8192          # Max tokens for report generation
```

### E. Trigger Functions

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Applied to: users, chat_sessions, file_apa_metadata
```

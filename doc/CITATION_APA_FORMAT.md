# Musya Agent — Citation APA Format Reference
# คู่มือการอ้างอิงตามมาตรฐาน APA 7th Edition (Thai Public Health Adaptation)

> **มาตรฐาน**: APA 7th Edition ปรับใช้กับรายงานตรวจราชการสาธารณสุขไทย
> **วันที่**: 2026-04-15
> **ไฟล์ที่เกี่ยวข้อง**: `src/agents/citation_evidence.py`, `src/utils/apa_formatter.py`, `src/schemas/evidence.py`

---

## 1. ภาพรวม (Overview)

ระบบ Citation ของ Musya Agent ใช้ **APA 7th Edition** เป็นมาตรฐานการอ้างอิง
โดยปรับใช้กับบริบทรายงานตรวจราชการสาธารณสุขไทย ซึ่งมีลักษณะเฉพาะ:

- ผู้เขียนเป็น **หน่วยงานราชการ** (ไม่ใช่บุคคล)
- ใช้ **ปี พ.ศ.** (ไม่ใช่ ค.ศ.)
- ชื่อเอกสารเป็น **ภาษาไทย**
- มีระบบ **Trust Level** ประเมินความน่าเชื่อถือ

---

## 2. ประเภทแหล่งอ้างอิง (Source Types)

### 2.1 รายงานตรวจราชการ (Report) — `apa_type: "report"`

**แหล่ง**: PDF รายงานตรวจราชการกระทรวงสาธารณสุข ผ่าน NotebookLM
**Trust Level**: 🟢 High

**Bibliography (reference list):**
```
สำนักงานสาธารณสุขจังหวัด{จังหวัด}. ({ปี พ.ศ.}). *รายงานตรวจราชการกระทรวงสาธารณสุข
    รอบที่ {รอบ} ปีงบประมาณ {ปี}*. กระทรวงสาธารณสุข.
```

**ตัวอย่าง:**
```
สำนักงานสาธารณสุขจังหวัดอุบลราชธานี. (2567). *รายงานตรวจราชการกระทรวงสาธารณสุข
    รอบที่ 2 ปีงบประมาณ 2567*. กระทรวงสาธารณสุข.
```

**Inline citation:**
```
(สสจ.อุบลราชธานี, 2567, หน้า 45)
```
หรือ `[C-001]`

### 2.2 ฐานข้อมูล (Dataset) — `apa_type: "dataset"`

**แหล่ง**: ฐานข้อมูล Musya Agent (PostgreSQL mart/fact tables)
**Trust Level**: 🟢 High (mart) / 🟡 Medium (fact)

**Bibliography:**
```
Musya Agent. ({ปี}). *{ชื่อฐานข้อมูล}* [Data set]. Musya Agent Database.
```

**ตัวอย่าง:**
```
Musya Agent. (2568). *ฐานข้อมูลสรุปอุบัติเหตุรายจังหวัดรายปี* [Data set]. Musya Agent Database.
Musya Agent. (2568). *ฐานข้อมูลจุดเสี่ยงอุบัติเหตุ* [Data set]. Musya Agent Database.
```

**Inline citation:**
```
(Musya Agent Database, 2568)
```
หรือ `[C-100]`

### 2.3 เว็บไซต์ (Website) — `apa_type: "website"`

**แหล่ง**: HDC, กระทรวงสาธารณสุข, สำนักระบาดวิทยา
**Trust Level**: 🟡 Medium

**Bibliography:**
```
{ชื่อหน่วยงาน}. ({ปี}). *{ชื่อหน้า/รายงาน}*. {ชื่อเว็บไซต์}. {URL}
```

**ตัวอย่าง:**
```
กระทรวงสาธารณสุข. (2567). *Dashboard อุบัติเหตุทางถนน*. HDC Service.
    https://hdcservice.moph.go.th
```

**Inline citation:**
```
(กระทรวงสาธารณสุข, 2567)
```
หรือ `[C-200]`

### 2.4 บทความวิชาการ (Article) — `apa_type: "article"`

**Bibliography:**
```
{ผู้เขียน}. ({ปี}). {ชื่อบทความ}. *{ชื่อวารสาร}*, {ปีที่}({ฉบับที่}), {หน้า}. {DOI}
```

### 2.5 กฎหมาย/ประกาศ (Law) — `apa_type: "law"`

**Bibliography:**
```
{ชื่อกฎหมาย}, พ.ศ. {ปี}. ราชกิจจานุเบกษา เล่ม {เล่ม} ตอนที่ {ตอน}.
```

---

## 3. ลำดับ Citation Code

| ช่วง | ประเภท | ตัวอย่าง |
|------|--------|---------|
| C-001 ถึง C-099 | รายงานตรวจราชการ (notebooklm_pdf/report) | [C-001] สสจ.อุบลราชธานี, 2567 |
| C-100 ถึง C-199 | ฐานข้อมูล (database/dataset) | [C-100] Musya Agent Database, 2568 |
| C-200 ถึง C-299 | เว็บไซต์/เอกสารภายนอก (website/external) | [C-200] กระทรวงสาธารณสุข, 2567 |

**ภายในแต่ละช่วง เรียงตาม topic:**
1. RTI (อุบัติเหตุทางถนน)
2. Mental Health (สุขภาพจิต)
3. NCD (โรคไม่ติดต่อเรื้อรัง)

---

## 4. การใช้ Citation ในรายงาน

### 4.1 Inline Citation ในเนื้อหา

ใช้ `[C-xxx]` หลังข้อความที่อ้างอิง:
```markdown
อัตราการเสียชีวิตจากอุบัติเหตุทางถนน 27.71 ต่อแสนประชากร [C-001]
สูงกว่าค่ามัธยฐาน 5 ปีย้อนหลัง (22.15 ต่อแสน) [C-001]
```

### 4.2 Source Note สำหรับตาราง/กราฟ

ทุกตาราง/กราฟต้องมี source note:
```markdown
| ตัวชี้วัด | เป้าหมาย | ผลงาน | สถานะ |
|-----------|----------|-------|-------|
| อัตราเสียชีวิต | ≤16/แสน | 27.71/แสน | ✗ |

*ที่มา: รายงานตรวจราชการฯ จ.อุบลราชธานี ปี 2567 [C-001]*
```

### 4.3 Reference List ท้ายรายงาน

จัดเรียงตาม citation code:
```markdown
## อ้างอิง (References)

[C-001] สำนักงานสาธารณสุขจังหวัดอุบลราชธานี. (2567). *รายงานตรวจราชการ
    กระทรวงสาธารณสุข รอบที่ 2 ปีงบประมาณ 2567*. กระทรวงสาธารณสุข.
[C-002] สำนักงานสาธารณสุขจังหวัดอุบลราชธานี. (2567). *รายงานตรวจราชการ
    กระทรวงสาธารณสุข (สุขภาพจิต) ปีงบประมาณ 2567*. กระทรวงสาธารณสุข.
[C-100] Musya Agent. (2568). *ฐานข้อมูลสรุปอุบัติเหตุรายจังหวัดรายปี* [Data set].
    Musya Agent Database.
```

---

## 5. Trust Level System

| Level | Icon | คำอธิบาย | แหล่งข้อมูล |
|-------|------|---------|------------|
| **High** | 🟢 | ข้อมูลจากแหล่งราชการ ตรวจสอบแล้ว | รายงานตรวจราชการ, mart tables |
| **Medium** | 🟡 | ข้อมูลจากระบบ มีความน่าเชื่อถือปานกลาง | fact tables, HDC dashboard |
| **Low** | 🔴 | ข้อมูลภายนอก ต้องตรวจสอบเพิ่มเติม | external APIs, user uploads |

---

## 6. Coverage Validation

Citation Agent ตรวจสอบ:

1. **ตัวเลข KPI ทุกตัวต้องมี citation** — อัตราต่อแสน, Median, ✓/✗ สถานะ
2. **ตาราง/กราฟทุกชิ้นต้องมี source_note** — ระบุแหล่งข้อมูล + [C-xxx]
3. **Coverage Score** = (supported_claims / total_claims) × 100%
4. **Flag** ข้อสรุปที่ไม่มีหลักฐาน — แจ้งให้ Review ก่อนเผยแพร่

**เกณฑ์ Coverage:**
| Score | สถานะ | การดำเนินการ |
|-------|-------|-------------|
| ≥ 90% | ผ่าน | เผยแพร่ได้ |
| 70-89% | เงื่อนไข | ต้อง review ข้อสรุปที่ไม่มี evidence |
| < 70% | ไม่ผ่าน | ต้องเพิ่มหลักฐานก่อนเผยแพร่ |

---

## 7. APA Metadata Fields (EvidenceItem Schema)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `apa_type` | str | ประเภทเอกสาร APA | `"report"`, `"dataset"`, `"website"` |
| `apa_authors` | str | ผู้เขียน/หน่วยงาน | `"สำนักงานสาธารณสุขจังหวัดอุบลราชธานี"` |
| `apa_year` | str | ปีที่เผยแพร่ (พ.ศ.) | `"2567"` |
| `apa_publisher` | str | สำนักพิมพ์/หน่วยงาน | `"กระทรวงสาธารณสุข"` |

---

## 8. Python API Reference

### apa_formatter.py

```python
from src.utils.apa_formatter import (
    format_apa_reference,          # Full bibliography text
    format_apa_inline,             # Short inline citation
    format_notebooklm_reference,   # NotebookLM source → APA dict
    format_notebooklm_inline,      # NotebookLM source → inline text
    format_database_reference,     # Database table → APA dataset
    format_database_inline,        # Database table → inline text
    build_reference_list,          # List of citations → Markdown reference list
    build_reference_list_html,     # List of citations → HTML with trust badges
    resolve_source_link,           # Evidence → clickable URL dict
)
```

### Usage Examples

```python
# Format NotebookLM inspection report
ref_dict = format_notebooklm_reference(
    province="อุบลราชธานี",
    year=2567,
    round_no=2,
    notebook_id="bc3d9350-1855-45f0-a2c3-a5634ed8056e",
)
bibliography = format_apa_reference(ref_dict)
# → สำนักงานสาธารณสุขจังหวัดอุบลราชธานี. (2567). *รายงานตรวจราชการฯ รอบที่ 2 ปีงบประมาณ 2567*. กระทรวงสาธารณสุข.

inline = format_notebooklm_inline("อุบลราชธานี", 2567, page_ref="45")
# → (สสจ.อุบลราชธานี, 2567, หน้า 45)

# Format database source
db_ref = format_database_reference("mart_province_year", "2568")
# → Musya Agent. (2568). *ฐานข้อมูลสรุปอุบัติเหตุรายจังหวัดรายปี* [Data set]. Musya Agent Database.

db_inline = format_database_inline("mart_province_year", "2568")
# → (Musya Agent Database, 2568)

# Build reference list
ref_list = build_reference_list([
    {"citation_code": "C-001", "bibliography_text": "สสจ.อุบลฯ..."},
    {"citation_code": "C-100", "bibliography_text": "Musya Agent..."},
])
```

---

## 9. Agent Pipeline Flow

```
[A1] NLM Data Fetcher
  → ดึงข้อมูลดิบ + metadata (province, year, notebook_id)

[A2-A4] Domain Analysts (parallel)
  → วิเคราะห์ + ระบุ evidence_refs: ["C-001", "C-002"]

[A5] Citation & Evidence Agent
  → Normalize evidence items + APA metadata
  → Map claims to evidence
  → Generate APA citations (bibliography_text + citation_text)
  → Build reference_list
  → Coverage validation
  → Output: JSON with evidence_items, claims, citations, reference_list, coverage

[A6] Report Writer
  → Embed [C-xxx] inline in report text
  → Append reference list at end of each domain report
  → Add source_notes to tables/charts
```

---

*Last updated: 2026-04-15 | Based on APA 7th Edition adapted for Thai public health inspection reports*

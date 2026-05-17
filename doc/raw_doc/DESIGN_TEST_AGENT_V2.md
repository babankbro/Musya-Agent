# Design Test Agent — Policy Brief UI
# Musya Agent Flow V2 — Test Interface Design Document

> **เวอร์ชัน**: 1.0
> **วันที่**: 2026-04-14
> **อ้างอิง**: AGENT_FLOW_V2.md, test_ui.html (Phase 2 style base)
> **ขอบเขต**: UI สำหรับทดสอบ Policy Brief Agent Pipeline (Phase 3)

---

## 1. ภาพรวม Design System

### 1.1 สืบทอดจาก test_ui.html (Phase 2)

| Element | Phase 2 (เดิม) | Phase 3 (ใหม่) |
|---------|---------------|---------------|
| Font | IBM Plex Sans Thai | IBM Plex Sans Thai (เหมือนเดิม) |
| Framework | Tailwind CSS (CDN) | Tailwind CSS (CDN) |
| Charts | Chart.js 4.4.2 | Chart.js 4.4.2 |
| Markdown | marked.js | marked.js |
| Color Primary | Purple-600 `#7c3aed` | Teal-600 `#0d9488` (แยกจาก Phase 2) |
| Color Accent | Indigo-600 `#4f46e5` | Emerald-500 `#10b981` |
| Header subtitle | "Phase 1 — Accident Domain" | "Phase 3 — Policy Brief" |

### 1.2 Color Palette (Phase 3)

```
Primary   ── Teal   ──  #0d9488  (header, active tab, primary button)
Accent    ── Emerald──  #10b981  (success, NCD badge)
Warning   ── Amber  ──  #f59e0b  (Mental health warning badge)
Danger    ── Red    ──  #ef4444  (RTI alert, high priority)
Neutral   ── Gray   ──  #6b7280  (text secondary)
Surface   ── White  ──  #ffffff  (card background)
Background── Gray-50──  #f9fafb  (page background)

Topic Colors:
  RTI      → Red-500    #ef4444
  Mental   → Amber-500  #f59e0b  (⚠️ sensitive topic)
  NCD      → Emerald-500 #10b981
```

### 1.3 Typography

```css
body         { font-family: 'IBM Plex Sans Thai', sans-serif; }
h1 (header)  { font-size: 1.125rem; font-weight: 700; }  /* text-lg font-bold */
h2 (section) { font-size: 1rem;     font-weight: 600; }  /* text-base font-semibold */
h3 (card)    { font-size: 0.875rem; font-weight: 600; }  /* text-sm font-semibold */
body-text    { font-size: 0.875rem; }                     /* text-sm */
caption      { font-size: 0.75rem;  }                     /* text-xs */
mono (code)  { font-family: monospace; font-size: 0.75rem; }
```

---

## 2. Layout Architecture

### 2.1 Page Structure

```
┌───────────────────────────────────────────────────────────────────────┐
│  HEADER (sticky, bg-white, border-b)                                  │
│  ┌─────────┐  Musya Agent — Policy Brief         [health badge]       │
│  │  M logo │  Phase 3 — Policy Brief             [Tab][Tab][Tab][Tab] │
│  └─────────┘                                                           │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  MAIN (max-w-6xl mx-auto)                                             │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  PANEL (active tab content)                                      │ │
│  │                                                                  │ │
│  │  [ Policy ] [ Pipeline ] [ Tools ] [ Data ]                     │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

### 2.2 Header Component

```
┌────────────────────────────────────────────────────────────────────────┐
│  ┌───────┐  Musya Agent Test UI                  ● All OK              │
│  │ T  M  │  Phase 3 — Policy Brief       [Policy][Pipeline][Tools][Data]│
│  └───────┘                                                              │
└────────────────────────────────────────────────────────────────────────┘

Logo: gradient teal-to-emerald (เปลี่ยนจาก purple-to-indigo)
      initials "M" สีขาว บน bg-gradient-to-br from-teal-500 to-emerald-600
```

---

## 3. Tab Panels (4 Tabs)

```
Tab 1: Policy     ── สร้างและแสดง Policy Brief (หลัก)
Tab 2: Pipeline   ── ติดตาม agent execution step-by-step
Tab 3: Tools      ── ทดสอบ nlm_ask และ tools อื่นโดยตรง
Tab 4: Data       ── ดูข้อมูล notebook sources และ DB
```

---

## 4. Tab 1 — Policy Brief Panel (หลัก)

### 4.1 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  TAB: Policy                                                         │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  INPUT PANEL (bg-white, rounded-xl, border, p-5)            │   │
│  │                                                              │   │
│  │  เลือกจังหวัด:                                                │   │
│  │  [ มุกดาหาร ][ ยโสธร ][ ศรีสะเกษ ][ อำนาจเจริญ ][ อุบลฯ ]   │   │
│  │                                                              │   │
│  │  เลือกหัวข้อ:                                                 │   │
│  │  [✓ RTI อุบัติเหตุ] [✓ สุขภาพจิต ⚠️] [✓ NCDs โภชนาการ]      │   │
│  │                                                              │   │
│  │  ปี พ.ศ.: [__2564__]    รูปแบบ: [● Markdown ○ PDF]          │   │
│  │                                                              │   │
│  │            [ สร้าง Policy Brief ]                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ─── ผลลัพธ์ ────────────────────────────────────────────────────   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  RESULT PANEL                                                │   │
│  │                                                              │   │
│  │  [RTI] [สุขภาพจิต] [NCD] [Cross-topic] [Citations]          │   │
│  │  ─────────────────────────────────────────────────          │   │
│  │                                                              │   │
│  │  📄 Policy Brief Content (Markdown rendered)                │   │
│  │  📊 Charts (ถ้ามี)                                           │   │
│  │  🔖 Citations [C-001] [C-002]                               │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Input Panel — Province Selector

```html
<!-- Province Pills (single select) -->
<div class="flex flex-wrap gap-2">
  <button class="province-btn active" data-province="มุกดาหาร">มุกดาหาร</button>
  <button class="province-btn" data-province="ยโสธร">ยโสธร</button>
  <button class="province-btn" data-province="ศรีสะเกษ">ศรีสะเกษ</button>
  <button class="province-btn" data-province="อำนาจเจริญ">อำนาจเจริญ</button>
  <button class="province-btn" data-province="อุบลราชธานี">อุบลราชธานี</button>
</div>

CSS States:
  default : bg-gray-100 text-gray-600 border-gray-200
  active  : bg-teal-50 text-teal-700 border-teal-400 border-2
  hover   : bg-teal-50 border-teal-300
```

### 4.3 Input Panel — Topic Checkboxes

```html
<!-- Topic Cards (multi-select checkboxes) -->

┌────────────────────────────┐  ┌────────────────────────────┐  ┌────────────────────────────┐
│  🚗 RTI                    │  │  🧠 สุขภาพจิต              │  │  🍎 NCDs                   │
│  อุบัติเหตุทางถนน            │  │  ⚠️ ข้อมูลละเอียดอ่อน      │  │  โภชนาการ & โรคเรื้อรัง     │
│  [✓ checkbox]              │  │  [✓ checkbox]              │  │  [✓ checkbox]              │
│  border-red-200 bg-red-50  │  │  border-amber-200          │  │  border-emerald-200        │
│                            │  │  bg-amber-50               │  │  bg-emerald-50             │
└────────────────────────────┘  └────────────────────────────┘  └────────────────────────────┘

Mental Health card มี tooltip เตือน:
"ข้อมูลนี้ใช้เพื่อวางแผนนโยบายเท่านั้น"
```

### 4.4 Input Panel — Submit Button

```html
<!-- States -->
idle    : bg-teal-600 text-white "สร้าง Policy Brief"
loading : bg-teal-400 disabled spinner "กำลังประมวลผล... (A0/6)"
success : bg-teal-600 "สร้างใหม่"
error   : bg-red-50 text-red-600 border-red-200 "เกิดข้อผิดพลาด — ลองใหม่"
```

### 4.5 Result Panel — Inner Tabs

```
Result inner tabs (topic sections):
┌──────────────────────────────────────────────────────────────┐
│ [🚗 RTI] [🧠 สุขภาพจิต] [🍎 NCD] [🔗 Cross-topic] [🔖 อ้างอิง] │
└──────────────────────────────────────────────────────────────┘

Active tab indicator: border-b-2 border-teal-500 text-teal-700
Inactive: text-gray-500 hover:text-gray-700

Mental Health tab มี ⚠️ icon สีเหลืองกำกับตลอด
```

### 4.6 Policy Brief Content Card

```
┌─────────────────────────────────────────────────────────────────┐
│  🚗 สถานการณ์อุบัติเหตุทางถนน จ.อุบลราชธานี          [📋 copy] │
│  ─────────────────────────────────────────────────────────────  │
│  Markdown rendered (prose class — ใช้ style เดิมจาก Phase 2)   │
│                                                                 │
│  ## บทสรุปผู้บริหาร                                              │
│  อัตราการเสียชีวิต... [C-001]                                    │
│                                                                 │
│  📊 [Chart: แนวโน้มอัตราเสียชีวิต]                               │
│                                                                 │
│  | มาตรการ | ระยะเวลา | KPI |                                   │
│  |---------|---------|-----|                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.7 Mental Health Content — Special Styling

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  DISCLAIMER                                     (amber bg)  │
│  ─────────────────────────────────────────────────────────────  │
│  ข้อมูลนี้จัดทำเพื่อวางแผนนโยบายสาธารณสุขภายใน                    │
│  ไม่ใช่สำหรับสื่อมวลชนหรือรายงานสาธารณะ                           │
│  ต้องผ่านการทบทวนโดยผู้เชี่ยวชาญก่อนเผยแพร่                        │
└─────────────────────────────────────────────────────────────────┘

bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4
icon: ⚠️ text-amber-600
text: text-sm text-amber-800
```

### 4.8 Cross-topic Linkage Section

```
┌─────────────────────────────────────────────────────────────────┐
│  🔗 ความเชื่อมโยงข้ามประเด็น                                       │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  🚗 RTI  ──→  🧠 สุขภาพจิต                               │   │
│  │  อุบัติเหตุรุนแรง → PTSD → เพิ่มความเสี่ยง suicide        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  🍎 NCD  ──→  🧠 สุขภาพจิต                               │   │
│  │  DM ควบคุมไม่ได้ → CKD → ภาระค่าใช้จ่าย → ความเครียด    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  🍎 NCD  ──→  🚗 RTI                                     │   │
│  │  โรคอ้วน → สมาธิลดลง → เสี่ยงอุบัติเหตุ                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

linkage card: bg-gray-50 border border-gray-200 rounded-lg p-3
from-topic badge: colored pill (red/amber/emerald)
arrow: → text-gray-400 font-bold
```

### 4.9 Citations Section

```
┌─────────────────────────────────────────────────────────────────┐
│  🔖 อ้างอิง (6 รายการ)                                           │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  [C-001] 📄 รายงานตรวจราชการ จ.อุบลราชธานี รอบที่ 2 ปี 2564    │
│          notebooklm_pdf | trust: HIGH                [🔗 เปิด]  │
│                                                                 │
│  [C-002] 🗄️ ฐานข้อมูลอุบัติเหตุ fact_accident_event             │
│          database | trust: HIGH                      [🔗 เปิด]  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

citation row: flex justify-between items-start py-2 border-b border-gray-100
citation code: font-mono text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded
trust badge:
  HIGH   → bg-green-50 text-green-700
  MEDIUM → bg-yellow-50 text-yellow-700
  LOW    → bg-red-50 text-red-700
source icon:
  notebooklm_pdf → 📄
  database       → 🗄️
  document       → 📝
```

---

## 5. Tab 2 — Pipeline Monitor Panel

### 5.1 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  TAB: Pipeline                                                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  PIPELINE PROGRESS (แสดงเมื่อกำลัง run)                     │   │
│  │                                                              │   │
│  │  ┌──────┐    ┌──────┐    ┌─────┬─────┬─────┐    ┌──────┐   │   │
│  │  │  A0  │───▶│  A1  │───▶│ A2  │ A3  │ A4  │───▶│  A5  │   │   │
│  │  │ Orch │    │ NLM  │    │ RTI │MH   │NCD  │    │ Cite │   │   │
│  │  └──────┘    └──────┘    └─────┴─────┴─────┘    └──────┘   │   │
│  │       └─────────────────────────────────────────────────▶A6 │   │
│  │                                                         Report│   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AGENT LOG (real-time stream)                                │   │
│  │                                                              │   │
│  │  ★ [CREW START] province=อุบลราชธานี topics=rti,mental,ncd  │   │
│  │  🔄 [A0] Policy Brief Orchestrator — starting...            │   │
│  │  ✅ [A0] Done — routing to A1                                │   │
│  │  🔄 [A1] NLM Data Fetcher — querying RTI...                 │   │
│  │  🔄 [A1] NLM Data Fetcher — querying Mental...              │   │
│  │  🔄 [A1] NLM Data Fetcher — querying NCD...                 │   │
│  │  ✅ [A1] Done — structured JSON ready                        │   │
│  │  🔄 [A2][A3][A4] Parallel Analysts — running...             │   │
│  │  ...                                                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  TIMING SUMMARY (แสดงหลัง complete)                          │   │
│  │  A0: 4s  A1: 45s  A2-A4: 18s (parallel)  A5: 12s  A6: 25s  │   │
│  │  ─────────────────────────────────────────────────────────   │   │
│  │  Total: 104s  |  agents: 11  |  citations: 6               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Agent Node Component

```
States ของแต่ละ node:

  waiting  : bg-gray-100  border-gray-300  text-gray-400  icon: ○
  running  : bg-teal-50   border-teal-400  text-teal-700  icon: ⟳ (spin)
  done     : bg-green-50  border-green-400 text-green-700 icon: ✓
  error    : bg-red-50    border-red-400   text-red-700   icon: ✗
  skipped  : bg-gray-50   border-gray-200  text-gray-300  icon: –

Parallel group (A2, A3, A4):
  wrapper: border-2 border-dashed border-teal-200 rounded-xl p-2
  label: "Parallel" badge ด้านบน bg-teal-100 text-teal-600 text-xs
```

### 5.3 Agent Log Stream

```css
/* Log Panel */
#pipeline-log {
  font-family: monospace;
  font-size: 0.75rem;     /* text-xs */
  background: #0f172a;    /* dark bg */
  color: #94a3b8;         /* gray-400 */
  border-radius: 0.75rem;
  padding: 1rem;
  height: 320px;
  overflow-y: auto;
}

/* Log line colors */
.log-start   { color: #f59e0b; }  /* amber — crew start */
.log-running { color: #38bdf8; }  /* sky-400 — agent thinking */
.log-done    { color: #4ade80; }  /* green-400 — complete */
.log-error   { color: #f87171; }  /* red-400 — error */
.log-tool    { color: #c084fc; }  /* purple-400 — tool call */
.log-warn    { color: #fbbf24; }  /* amber — warning */
```

---

## 6. Tab 3 — Tools Panel

### 6.1 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  TAB: Tools                                                          │
│                                                                     │
│  Section A: NotebookLM Tools (ใหม่ Phase 3)                         │
│  ┌─────────────────────────────────┐  ┌──────────────────────────┐  │
│  │  🤖 nlm_ask                     │  │  📋 nlm_source_list       │  │
│  │  province: [อุบลราชธานี    ▼]    │  │  notebook_id: [____]     │  │
│  │  topic:    [rti           ▼]    │  │  [Run]                   │  │
│  │  [Run]                          │  │  result...               │  │
│  │  result...                      │  └──────────────────────────┘  │
│  └─────────────────────────────────┘                                │
│                                                                     │
│  Section B: Database Tools (reuse Phase 2)                          │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐    │
│  │ get_hotspots     │ │ province_year    │ │ time_distribution│    │
│  │ [top_n: 10]      │ │ [province: ___] │ │ [Run]            │    │
│  │ [Run]            │ │ [Run]            │ │ result...        │    │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 NLM Ask Tool Card

```html
<!-- nlm_ask Tool Card -->
┌────────────────────────────────────────────────────────────────┐
│  🤖 nlm_ask — NotebookLM Query                                 │
│  ──────────────────────────────────────────────────────────    │
│  จังหวัด:                                                       │
│  [ มุกดาหาร ▼ ]  (select: 5 จังหวัด)                           │
│                                                                │
│  หัวข้อ:                                                        │
│  [ rti ▼ ]  (select: rti / mental / ncd)                      │
│                                                                │
│  Custom Query (optional):                                      │
│  [ _____________________________________ ]                     │
│                                                                │
│  [▶ Run nlm_ask]                                               │
│                                                                │
│  ──── Result ────────────────────────────────────────────────  │
│  [response text...]                                            │
│                                                                │
│  Elapsed: 12.3s  |  chars: 842                                 │
└────────────────────────────────────────────────────────────────┘

Card: bg-white rounded-xl border border-teal-200 p-4
Header icon bg: bg-teal-50 (แยกสีจาก Phase 2 ที่เป็น indigo)
Run button: bg-teal-600 text-white
```

### 6.3 Database Tool Cards (Reuse Phase 2 Style)

เหมือน Phase 2 แต่เพิ่ม filter จังหวัด (5 จังหวัด เขตสุขภาพที่ 10):

```
get_accident_hotspots  → เพิ่ม province filter
get_province_year_summary → เปลี่ยน province dropdown เป็น 5 จังหวัด
get_accident_time_distribution → คงเดิม
```

---

## 7. Tab 4 — Data Panel

### 7.1 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  TAB: Data                                                           │
│                                                                     │
│  Section A: NotebookLM Sources                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  📚 Notebook: รายงานตรวจราชการสาธารณสุข รอบที่ 2 ปี 2564     │   │
│  │  ID: bc3d9350-1855-45f0-a2c3-a5634ed8056e  | Sources: 28     │   │
│  │  ─────────────────────────────────────────────────────────   │   │
│  │  ┌──────────────────────────────┬────────┬──────────────┐    │   │
│  │  │ ชื่อไฟล์                       │ จังหวัด │ ปี           │    │   │
│  │  ├──────────────────────────────┼────────┼──────────────┤    │   │
│  │  │ เอกสารรับตรวจ จ.อุบลฯ รอบ2-64│ อุบลฯ  │ 2564         │    │   │
│  │  │ ...                          │ ...    │ ...          │    │   │
│  │  └──────────────────────────────┴────────┴──────────────┘    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Section B: Database Overview (reuse Phase 2 data cards)            │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐          │
│  │ accident_event │ │ dim_geography  │ │ mart_summary   │          │
│  │  113,410 rows  │ │   5,793 rows   │ │  aggregated    │          │
│  └────────────────┘ └────────────────┘ └────────────────┘          │
│                                                                     │
│  Section C: SQL Query (reuse Phase 2)                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Sources Table Component

```
province badges:
  มุกดาหาร   → bg-purple-50 text-purple-700
  ยโสธร     → bg-blue-50   text-blue-700
  ศรีสะเกษ  → bg-orange-50 text-orange-700
  อำนาจเจริญ → bg-pink-50   text-pink-700
  อุบลราชธานี → bg-teal-50   text-teal-700

status badge:
  ready  → bg-green-50 text-green-700 • ready
  pending → bg-yellow-50 text-yellow-700 ⟳ pending
```

---

## 8. Shared Components

### 8.1 Loading State (ขณะ Pipeline รัน)

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│              ⟳  กำลังประมวลผล Policy Brief...                    │
│                                                                  │
│  A0 Orchestrator    ✓ done     (4s)                              │
│  A1 NLM Fetcher     ⟳ running  RTI...                            │
│  A2 RTI Analyst     ○ waiting                                    │
│  A3 Mental Analyst  ○ waiting                                    │
│  A4 NCD Analyst     ○ waiting                                    │
│  A5 Citations       ○ waiting                                    │
│  A6 Report Writer   ○ waiting                                    │
│                                                                  │
│  ████████░░░░░░░░░░░░  40%  ~90s remaining                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

Progress bar: bg-teal-500, rounded-full, transition-all duration-500
```

### 8.2 Priority Badge

```
high   : bg-red-50   text-red-700   border-red-200   "สูง"
medium : bg-amber-50 text-amber-700 border-amber-200 "กลาง"
low    : bg-gray-50  text-gray-600  border-gray-200  "ต่ำ"
```

### 8.3 Timeframe Badge

```
short : bg-red-50   text-red-700   "ระยะสั้น < 3 เดือน"
mid   : bg-amber-50 text-amber-700 "ระยะกลาง 3-12 เดือน"
long  : bg-blue-50  text-blue-700  "ระยะยาว > 1 ปี"
```

### 8.4 Topic Tag

```html
<!-- inline topic tag สำหรับใช้ใน cross-topic section -->
<span class="topic-tag topic-rti">🚗 RTI</span>
<span class="topic-tag topic-mental">🧠 สุขภาพจิต</span>
<span class="topic-tag topic-ncd">🍎 NCD</span>

CSS:
  .topic-tag        { @apply text-xs font-medium px-2 py-0.5 rounded-full; }
  .topic-rti        { @apply bg-red-50 text-red-700; }
  .topic-mental     { @apply bg-amber-50 text-amber-700; }
  .topic-ncd        { @apply bg-emerald-50 text-emerald-700; }
```

### 8.5 Copy Button

```
Position: absolute top-3 right-3
Style: bg-gray-100 hover:bg-gray-200 text-gray-500 rounded-lg p-1.5
Icon: 📋 (เปลี่ยนเป็น ✓ 1 วินาทีหลัง copy)
```

---

## 9. JavaScript Functions

### 9.1 Core Functions

| Function | คำอธิบาย | Input | Output |
|----------|----------|-------|--------|
| `generateBrief()` | ส่ง POST /api/policy-brief | province, topics, year | PolicyBriefResponse |
| `renderPolicyBrief(data)` | แสดงผล Policy Brief ทั้งหมด | response JSON | DOM update |
| `renderSection(topic, data)` | render แต่ละ topic section | topic, section data | DOM update |
| `renderCrossLinks(links)` | render linkage cards | string[] | DOM update |
| `renderCitations(citations)` | render citation list | Citation[] | DOM update |
| `renderPipeline(metadata)` | update pipeline diagram | metadata | DOM update |
| `streamAgentLog(msg)` | append log line | log string | DOM append |
| `updateAgentNode(id, state)` | เปลี่ยน state ของ node | agent_id, state | DOM update |
| `switchResultTab(topic)` | เปลี่ยน inner tab | topic string | DOM update |
| `copyToClipboard(text)` | copy content | text | clipboard |
| `runNlmAsk()` | ทดสอบ nlm_ask tool | province, topic | response text |
| `checkHealth()` | (reuse Phase 2) | – | badge update |

### 9.2 State Object

```javascript
const state = {
    // Input
    selectedProvince: 'อุบลราชธานี',
    selectedTopics:   ['rti', 'mental', 'ncd'],
    selectedYear:     2564,

    // Pipeline
    isLoading:    false,
    agentStates:  { A0:'waiting', A1:'waiting', A2:'waiting',
                    A3:'waiting', A4:'waiting', A5:'waiting', A6:'waiting' },
    elapsed:      0,

    // Result
    lastResponse: null,
    activeResultTab: 'rti',
};
```

### 9.3 API Call

```javascript
async function generateBrief() {
    const payload = {
        province: state.selectedProvince,
        topics:   state.selectedTopics,
        year:     state.selectedYear,
        format:   'markdown'
    };

    const res = await fetch('/api/policy-brief', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload)
    });

    const data = await res.json();
    renderPolicyBrief(data);
}
```

---

## 10. File Structure

```
Agent/
├── static/
│   ├── test_ui.html                ← Phase 2 (ไม่แก้ไข)
│   ├── citation_test_ui.html       ← Phase 2 (ไม่แก้ไข)
│   └── policy_brief_ui.html        ← NEW Phase 3 (สร้างใหม่)
└── doc/
    ├── AGENT_FLOW_V2.md            ← Architecture ref
    └── DESIGN_TEST_AGENT_V2.md     ← เอกสารนี้
```

**เข้าถึงผ่าน:**
```
http://localhost:8000/static/policy_brief_ui.html
```

---

## 11. HTML Boilerplate

```html
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Musya Agent — Policy Brief UI</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@300;400;500;600;700&display=swap');
    body { font-family: 'IBM Plex Sans Thai', sans-serif; }

    /* Prose (Markdown) — reuse Phase 2 */
    .prose h2 { font-size:1.15rem; font-weight:600; margin-top:1rem; margin-bottom:0.4rem; }
    .prose h3 { font-size:1.05rem; font-weight:600; margin-top:0.8rem; margin-bottom:0.3rem; }
    .prose ul, .prose ol { padding-left:1.5rem; margin:0.3rem 0; }
    .prose li { margin:0.15rem 0; }
    .prose p  { margin:0.3rem 0; }
    .prose table { border-collapse:collapse; width:100%; margin:0.5rem 0; font-size:0.85rem; }
    .prose th, .prose td { border:1px solid #d1d5db; padding:4px 8px; text-align:left; }
    .prose th { background:#f0fdfa; font-weight:600; }  /* teal tint */

    /* Animations — reuse Phase 2 */
    .chat-bubble { animation: fadeIn 0.3s ease-in; }
    @keyframes fadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
    @keyframes pulse  { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
    @keyframes spin   { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }
    .loading-dots span { animation: pulse 1.4s infinite; }
    .loading-dots span:nth-child(2) { animation-delay:0.2s; }
    .loading-dots span:nth-child(3) { animation-delay:0.4s; }
    .spin { animation: spin 1s linear infinite; }

    /* Charts */
    .chart-card { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:16px; margin-top:10px; }
    .chart-card canvas { height:300px !important; width:100% !important; }

    /* Pipeline log */
    #pipeline-log { font-family:monospace; background:#0f172a; color:#94a3b8;
                    border-radius:0.75rem; padding:1rem; height:320px; overflow-y:auto; }

    /* Scrollbar */
    ::-webkit-scrollbar { width:6px; }
    ::-webkit-scrollbar-thumb { background:#cbd5e1; border-radius:3px; }
  </style>
</head>
<body class="bg-gray-50 min-h-screen">
  <!-- Header: from-teal-500 to-emerald-600 logo gradient -->
  <!-- Tabs: Policy | Pipeline | Tools | Data -->
  <!-- Panels: see sections 4-7 above -->
</body>
</html>
```

---

## 12. สรุปความแตกต่างจาก test_ui.html (Phase 2)

| ด้าน | Phase 2 test_ui.html | Phase 3 policy_brief_ui.html |
|------|---------------------|------------------------------|
| **Color theme** | Purple/Indigo | Teal/Emerald |
| **Main tab** | Chat (free text) | Policy (province + topics) |
| **Input** | Text input | Province selector + Topic checkboxes |
| **Output tabs** | (none) | RTI / Mental / NCD / Cross / Citations |
| **Mental Health** | ไม่มี | ⚠️ Disclaimer card บังคับ |
| **Pipeline tab** | ไม่มี | ✅ Real-time agent node + log |
| **Tools tab** | DB tools only | + nlm_ask tool section |
| **Data tab** | DB overview | + NotebookLM sources table |
| **Cross-topic** | ไม่มี | ✅ Linkage cards |
| **Endpoint** | `/api/chat` | `/api/policy-brief` |

---

*Last updated: 2026-04-14 | Musya Agent Phase 3 — Policy Brief Test UI Design*

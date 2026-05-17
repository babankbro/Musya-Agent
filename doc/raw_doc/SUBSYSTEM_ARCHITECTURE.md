# Subsystem Architecture — Musya Agent

> Version 1.0 | 2026-04-16
> แยก Agent Pipeline ออกเป็น Subsystem อิสระ เพื่อลดการ coupling และเพิ่มความยืดหยุ่น

---

## 1. Problem Statement

### 1.1 สถานะปัจจุบัน (Monolithic)

ระบบปัจจุบันเป็น monolith ที่ agents, tools, RAG, citation, และ database access ผูกติดกัน:

```
orchestrator.py
  ├── imports ทุก agent file โดยตรง
  ├── agents import tools โดยตรง
  ├── tools import db/pool โดยตรง
  ├── tools import rag/ โดยตรง
  └── citation agent import schemas + db + apa_formatter โดยตรง
```

**ปัญหา:**
- เปลี่ยนเช่น APA format → ต้องแก้ทั้ง citation agent, tools/common, rag/document_rag, routers/evidence
- เพิ่ม data source ใหม่ (ThaiJO) → ต้องแก้ retrieval agent, citation agent, schemas, config, router
- Test แต่ละส่วนยาก เพราะ import chain ลึก
- Agent 2 (Retrieval) มี 10+ tools ปนกัน (document + accident + geography)
- Citation logic กระจายอยู่ใน 4+ files

### 1.2 เป้าหมาย

แยกระบบเป็น **8 subsystems** ที่มี:
- **Clear boundary** — แต่ละ subsystem มี interface ชัดเจน
- **Independent lifecycle** — พัฒนา test deploy แยกกันได้
- **Plug-in architecture** — เพิ่ม data source ใหม่โดยไม่กระทบ subsystem อื่น
- **Shared contract** — subsystems สื่อสารผ่าน schema ที่กำหนดไว้

---

## 2. Subsystem Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            API Gateway                                  │
│                     (FastAPI Routers Layer)                              │
│  /api/chat  /api/policy-brief  /api/documents  /api/thaijo  /api/health │
└──────────────┬───────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    Orchestration Subsystem                               │
│              (Pipeline routing, agent coordination)                      │
│                                                                          │
│  Request Router → Foundation Builder → Pipeline Executor → Response      │
└──────┬────────────────┬────────────────┬────────────────┬────────────────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Document    │ │    APA &     │ │   ThaiJO     │ │  Database    │
│  RAG         │ │  Citation    │ │   Search     │ │  RAG         │
│  Subsystem   │ │  Subsystem   │ │  Subsystem   │ │  Subsystem   │
│              │ │              │ │              │ │              │
│ • Ingest     │ │ • Evidence   │ │ • Search API │ │ • Accident   │
│ • Embed      │ │ • APA format │ │ • Summarize  │ │ • SQL tools  │
│ • Search     │ │ • Citation   │ │ • Normalize  │ │ • Mart query │
│ • MinIO      │ │ • Coverage   │ │ • Cache      │ │ • Geography  │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                                │
               ┌────────────────┼────────────────┐
               ▼                ▼                ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │   Report     │ │   Chart      │ │  NotebookLM  │
      │   Engine     │ │   Builder    │ │  Bridge      │
      │  Subsystem   │ │  Subsystem   │ │  Subsystem   │
      │              │ │              │ │              │
      │ • Analyst    │ │ • 7 chart    │ │ • NLM CLI    │
      │ • Synthesize │ │   generators │ │ • Province   │
      │ • Deep anal. │ │ • ChartSpec  │ │ • Topic mgmt │
      │ • Compose    │ │ • Styling    │ │ • PDF parse  │
      └──────────────┘ └──────────────┘ └──────────────┘
               │                │                │
               └────────────────┴────────────────┘
                                │
                                ▼
                   ┌──────────────────────┐
                   │   Shared Infra       │
                   │                      │
                   │ • DB Pool (pg)       │
                   │ • MinIO Client       │
                   │ • Config / Settings  │
                   │ • Logging / Tracing  │
                   └──────────────────────┘
```

---

## 3. Subsystem Contracts

### 3.1 Inter-Subsystem Communication

Subsystems สื่อสารกันผ่าน **typed data objects** ไม่ใช่ function call โดยตรง:

```python
# ทุก subsystem return ผลลัพธ์เป็น typed object
# Orchestrator เป็นคนเดียวที่เรียกแต่ละ subsystem

Orchestrator
  ├── calls DocumentRAG.search()     → RetrievalResult
  ├── calls DatabaseRAG.query()      → RetrievalResult
  ├── calls ThaiJO.search()          → RetrievalResult
  ├── calls NotebookLM.ask()         → RetrievalResult
  │
  ├── merges all RetrievalResult     → CombinedEvidence
  │
  ├── calls Citation.process()       → CitationContext
  ├── calls ReportEngine.analyze()   → AnalysisResult
  ├── calls ChartBuilder.build()     → list[ChartSpec]
  └── calls ReportEngine.compose()   → FinalReport
```

### 3.2 Shared Data Contracts

```python
# ============================================================
# contracts.py — Shared types between all subsystems
# ============================================================

class RetrievalResult(BaseModel):
    """ผลลัพธ์จาก data source ใดๆ (Document RAG, Database RAG, ThaiJO, NLM)"""
    source_type: Literal[
        "document_rag",
        "database",
        "thaijo_article",
        "notebooklm_pdf",
        "external_api",
    ]
    items: list[RetrievalItem]
    metadata: dict  # search term, query params, timing

class RetrievalItem(BaseModel):
    """หน่วยข้อมูลเดียว ที่สามารถ normalize เป็น evidence ได้"""
    content: str                          # ข้อมูล/สรุป/ข้อความ
    source_ref: str                       # identifier (file path, pdf_url, table name)
    title: str | None = None
    page_ref: str | None = None
    section_label: str | None = None

    # APA-ready metadata (ถ้ามี)
    apa_type: str | None = None           # article, report, dataset, website, law
    apa_authors: str | None = None
    apa_year: str | None = None
    apa_publisher: str | None = None
    apa_url: str | None = None

    # Traceability
    trust_level: Literal["high", "medium", "low"] = "medium"
    open_url: str | None = None           # clickable link to source

    # Source-specific extras
    extras: dict = {}                     # {pdf_url, summary, reference, ...}


class CitationContext(BaseModel):
    """ผลลัพธ์จาก Citation Subsystem"""
    evidence_items: list[EvidenceItem]
    claims: list[Claim]
    citations: list[EnhancedCitation]
    source_notes: dict[str, str]          # chart_id → "ที่มา: [C-001]"
    coverage: CoverageReport


class AnalysisResult(BaseModel):
    """ผลลัพธ์จาก Report Engine"""
    key_findings: list[str]
    risk_areas: list[str]
    risk_groups: list[str]
    trends: list[str]
    recommendations: list[str]
    narrative_blocks: list[NarrativeBlock]
    deep_analysis: DeepAnalysis | None = None


class FinalReport(BaseModel):
    """ผลลัพธ์สุดท้ายจาก Report Composer"""
    content: str                          # Markdown report
    topic: str
    charts: list[ChartSpec]
    tables: list[TableSpec]
    citations: list[EnhancedCitation]
    follow_ups: list[str]
    metadata: dict
```

---

## 4. Subsystem Detail Design

---

### 4.1 Document RAG Subsystem

**Responsibility:** จัดการ document lifecycle ทั้งหมด — upload, ingest, chunk, embed, search

**Boundary:**
```
src/subsystems/document_rag/
├── __init__.py              # Public API exports
├── service.py               # DocumentRAGService (facade)
├── ingestion.py             # Ingest pipeline (download → extract → chunk → embed)
├── search.py                # Vector search + metadata enrichment
├── chunker.py               # Text splitting strategies
├── extractor.py             # PDF/DOCX/TXT text extraction
├── tools.py                 # CrewAI @tool functions for agents
└── schemas.py               # Subsystem-internal models
```

**Public Interface:**

```python
class DocumentRAGService:
    """Facade สำหรับ Document RAG Subsystem"""

    async def ingest_all(self) -> IngestReport:
        """Scan MinIO → ingest all new/updated documents"""

    async def ingest_single(self, file_path: str, metadata: dict) -> IngestResult:
        """Ingest one document with explicit metadata"""

    async def search(self, topic: str, keywords: str, n_results: int = 5) -> RetrievalResult:
        """Vector similarity search + metadata enrichment
        Returns RetrievalResult with source_type='document_rag'"""

    async def get_document_info(self, document_id: str) -> DocumentInfo:
        """Get document metadata from registry"""

    async def download(self, file_path: str) -> bytes:
        """Download raw document from MinIO"""

    async def delete(self, document_id: str) -> bool:
        """Remove document from registry + embeddings"""
```

**CrewAI Tools (for Agent 2):**

```python
@tool("search_documents")
def search_documents(topic: str, keywords: str, n_results: int = 5) -> str:
    """ค้นหาเอกสารจาก Document RAG (pgvector)"""
    # delegates to DocumentRAGService.search()
```

**Dependencies:**
- Shared Infra: DB Pool (pgvector queries), MinIO Client
- External: Gemini Embedding API

**Database Tables Owned:**
- `document_registry` (structure only, APA columns shared with Citation)
- `document_embeddings` (pgvector 3072-dim)

---

### 4.2 APA & Citation Subsystem

**Responsibility:** Evidence normalization, APA formatting, citation code allocation, claim-evidence linking, coverage validation

**Boundary:**
```
src/subsystems/citation/
├── __init__.py              # Public API exports
├── service.py               # CitationService (facade)
├── normalizer.py            # Raw data → EvidenceItem conversion
├── apa_formatter.py         # APA 7th Edition formatting engine
├── code_allocator.py        # Citation code range management (C-001, C-100, C-200)
├── coverage.py              # Coverage validation & scoring
├── tools.py                 # CrewAI @tool functions for Agent 4
├── schemas.py               # EvidenceItem, Claim, EnhancedCitation, CoverageReport
└── agent.py                 # Citation & Evidence Agent factory
```

**Public Interface:**

```python
class CitationService:
    """Facade สำหรับ APA & Citation Subsystem"""

    def normalize_evidence(
        self,
        retrieval_results: list[RetrievalResult],
    ) -> list[EvidenceItem]:
        """Convert RetrievalResult items from ANY source → EvidenceItem
        Handles: document_rag, database, thaijo_article, notebooklm_pdf"""

    def allocate_citation_codes(
        self,
        evidence_items: list[EvidenceItem],
    ) -> list[EnhancedCitation]:
        """Assign C-xxx codes based on source_type ranges
        Deduplicate by source_ref — one document = one code"""

    def format_apa_reference(
        self,
        evidence: EvidenceItem,
    ) -> APAReference:
        """Generate APA 7th Edition bibliography + inline citation"""

    def link_claims_to_evidence(
        self,
        claims: list[Claim],
        evidence: list[EvidenceItem],
    ) -> list[ClaimEvidenceLink]:
        """Map claims to supporting evidence"""

    def validate_coverage(
        self,
        claims: list[Claim],
        links: list[ClaimEvidenceLink],
    ) -> CoverageReport:
        """Calculate coverage score, flag unsupported claims"""

    def process(
        self,
        retrieval_results: list[RetrievalResult],
        session_id: str | None = None,
    ) -> CitationContext:
        """Full pipeline: normalize → allocate → format → return context
        Convenience method combining all steps"""

    async def persist(
        self,
        context: CitationContext,
        session_id: str,
    ) -> None:
        """Persist evidence + claims to database for traceability"""

    def lookup_apa(self, source_ref: str) -> APAReference | None:
        """Look up APA metadata from document_registry"""
```

**Citation Code Allocation Rules:**

```python
class CodeAllocator:
    """จัดการ citation code ranges"""

    RANGES = {
        "document_rag":     (1, 99),      # C-001 to C-099
        "notebooklm_pdf":   (1, 99),      # C-001 to C-099 (same range)
        "database":         (100, 199),    # C-100 to C-199
        "thaijo_article":   (200, 249),    # C-200 to C-249
        "external_api":     (250, 299),    # C-250 to C-299
    }

    def allocate(self, source_type: str, source_ref: str) -> str:
        """Allocate next available code in range.
        Same source_ref always returns same code (idempotent)."""
```

**APA Formatting Engine:**

```python
class APAFormatter:
    """APA 7th Edition — Thai adaptation"""

    def format_report(self, ev: EvidenceItem) -> APAReference:
        """สสจ.{จังหวัด}. ({ปี}). *รายงานตรวจราชการฯ*. กระทรวงสาธารณสุข."""

    def format_dataset(self, ev: EvidenceItem) -> APAReference:
        """Musya Agent. ({ปี}). *{ชื่อตาราง}* [Data set]. Musya Agent Database."""

    def format_article(self, ev: EvidenceItem) -> APAReference:
        """ผู้แต่ง. ({ปี}). ชื่อบทความ. *ชื่อวารสาร*, เล่ม(ฉบับ), หน้า."""

    def format_website(self, ev: EvidenceItem) -> APAReference:
        """{หน่วยงาน}. ({ปี}). *{ชื่อหน้า}*. {URL}"""

    def format_law(self, ev: EvidenceItem) -> APAReference:
        """พ.ร.บ./กฎหมาย formatting"""

    def format_auto(self, ev: EvidenceItem) -> APAReference:
        """Auto-detect apa_type → dispatch to correct formatter"""

    def format_fallback(self, ev: EvidenceItem) -> APAReference:
        """Minimal citation when metadata is incomplete"""
```

**CrewAI Tools (for Agent 4):**

```python
@tool("lookup_document_apa")
def lookup_document_apa(source_ref: str) -> str:
    """ค้นหา APA metadata จาก document_registry"""

@tool("register_evidence")
def register_evidence(evidence_json: str) -> str:
    """บันทึก evidence item ลง evidence_registry"""

@tool("register_claim_links")
def register_claim_links(links_json: str) -> str:
    """บันทึก claim-evidence links"""
```

**Dependencies:**
- Shared Infra: DB Pool
- Receives: `RetrievalResult` from any data source subsystem

**Database Tables Owned:**
- `evidence_registry`
- `claim_evidence_link`
- `document_registry.apa_*` columns (shared ownership with Document RAG)

---

### 4.3 ThaiJO Search Subsystem

**Responsibility:** ค้นหาบทความวิชาการจาก ThaiJO, normalize ผลลัพธ์, จัดการ cache

**Boundary:**
```
src/subsystems/thaijo/
├── __init__.py              # Public API exports
├── service.py               # ThaiJOService (facade)
├── client.py                # HTTP client to ThaiJO microservice
├── normalizer.py            # ThaiJO response → RetrievalResult conversion
├── tools.py                 # CrewAI @tool for Agent 2
└── schemas.py               # ThaiJOSearchRequest, ThaiJOArticle
```

**Public Interface:**

```python
class ThaiJOService:
    """Facade สำหรับ ThaiJO Search Subsystem"""

    async def search(
        self,
        term: str,
        size: int = 5,
        page: int = 1,
        strict: bool = True,
    ) -> RetrievalResult:
        """Search ThaiJO academic articles.
        Returns RetrievalResult with source_type='thaijo_article'

        Each item includes:
        - content: AI-generated summary (Thai, ~3 pages)
        - source_ref: pdf_url on TCI-THAIJO
        - apa_type: 'article'
        - trust_level: 'medium'
        - extras: {reference, search_term}
        """

    async def search_multi_topic(
        self,
        topics: list[str],
        size_per_topic: int = 3,
    ) -> RetrievalResult:
        """Search multiple topics, merge and deduplicate results"""

    def is_available(self) -> bool:
        """Health check — is ThaiJO microservice reachable?"""
```

**Normalizer Logic:**

```python
class ThaiJONormalizer:
    """Convert ThaiJO API response → RetrievalItem[]"""

    def normalize(self, raw_results: list[dict], search_term: str) -> list[RetrievalItem]:
        items = []
        for article in raw_results:
            # Parse APA from reference field (if available)
            apa = self._parse_reference(article.get("reference"))

            items.append(RetrievalItem(
                content=article["summary"],
                source_ref=article["pdf_url"],
                title=apa.title if apa else self._extract_title(article["summary"]),
                apa_type="article",
                apa_authors=apa.authors if apa else None,
                apa_year=apa.year if apa else None,
                apa_publisher=apa.journal if apa else None,
                apa_url=article["pdf_url"],
                trust_level="medium",
                open_url=article["pdf_url"],
                extras={
                    "raw_reference": article.get("reference"),
                    "search_term": search_term,
                },
            ))
        return items

    def _parse_reference(self, ref: str | None) -> ParsedAPA | None:
        """Parse APA citation text → structured fields
        Example input: 'สมชาย ใจดี, & สมหญิง. (2567). ชื่อ. *วารสาร*, 5(2), 1-10.'
        """

    def _extract_title(self, summary: str) -> str:
        """Extract title from first meaningful line of summary"""
```

**CrewAI Tool (for Agent 2):**

```python
@tool("search_thaijo")
def search_thaijo(term: str, size: int = 5) -> str:
    """ค้นหาบทความวิชาการจาก ThaiJO (Thai Journals Online)

    ใช้เมื่อต้องการ:
    - ข้อมูลวิจัย/บทความวิชาการสนับสนุนการวิเคราะห์
    - evidence-based support จากวารสารไทย

    Args:
        term: คำค้นหาภาษาไทย 2-5 คำ
        size: จำนวนบทความ (1-10)
    """
    # delegates to ThaiJOService.search()
```

**Dependencies:**
- External: ThaiJO microservice (HTTP)
- Shared Infra: Config (THAIJO_API_URL, THAIJO_TIMEOUT)

**Database Tables Owned:** None (stateless — caching is in ThaiJO microservice's Redis)

---

### 4.4 Database RAG Subsystem

**Responsibility:** Structured data queries — accident domain, mart tables, SQL execution, geography

**Boundary:**
```
src/subsystems/database_rag/
├── __init__.py              # Public API exports
├── service.py               # DatabaseRAGService (facade)
├── accident/
│   ├── __init__.py
│   ├── service.py           # AccidentDataService
│   ├── tools.py             # 7 accident @tool functions
│   └── schemas.py           # AccidentSummary, Hotspot, TimeDistribution
├── sql/
│   ├── __init__.py
│   ├── executor.py          # Safe SQL execution (SELECT/WITH only)
│   ├── tools.py             # execute_custom_sql, explain_schema
│   └── validator.py         # SQL safety validation
├── geography/
│   ├── __init__.py
│   ├── service.py           # GeographyService
│   └── tools.py             # get_geography_profile, get_indicator_catalog
└── schemas.py               # Shared data models
```

**Public Interface:**

```python
class DatabaseRAGService:
    """Facade สำหรับ Database RAG Subsystem"""

    # --- Accident Domain ---
    async def get_accident_summary(self, geography: str, date_range: str) -> RetrievalResult:
    async def get_hotspots(self, geography: str, top_n: int) -> RetrievalResult:
    async def get_time_distribution(self, geography: str) -> RetrievalResult:
    async def get_road_condition_risk(self, road: str) -> RetrievalResult:
    async def get_province_year(self, province: str, year: int) -> RetrievalResult:
    async def get_province_roads(self, province: str, year: int) -> RetrievalResult:
    async def get_all_provinces_ranking(self, year: int) -> RetrievalResult:

    # --- SQL Execution ---
    async def execute_sql(self, query: str) -> RetrievalResult:
        """Execute validated SQL query (SELECT/WITH only)"""
    async def explain_schema(self, table_name: str) -> str:
        """Return table schema documentation"""

    # --- Geography ---
    async def get_geography_profile(self, name: str) -> RetrievalResult:
    async def get_indicator_catalog(self, topic: str) -> RetrievalResult:

    # --- All tools for agent registration ---
    def get_retrieval_tools(self) -> list:
        """Return all CrewAI @tool functions for Agent 2"""
    def get_sql_tools(self) -> list:
        """Return all CrewAI @tool functions for Agent 3"""
```

**Domain Extensibility:**

เมื่อเพิ่ม domain ใหม่ (mental health, NCD) สร้าง subdirectory เพิ่ม:

```
src/subsystems/database_rag/
├── accident/     # existing
├── mental/       # NEW — future Phase 2
│   ├── service.py
│   ├── tools.py
│   └── schemas.py
├── ncd/          # NEW — future Phase 2
│   ├── service.py
│   ├── tools.py
│   └── schemas.py
└── ...
```

**Dependencies:**
- Shared Infra: DB Pool (PostgreSQL queries)

**Database Tables Owned:**
- `fact_accident_event`, `fact_accident_person`
- `dim_geography`, `dim_road_segment`, `dim_time`, `dim_source`
- `mart_accident_summary`, `mart_accident_hotspot`, `mart_province_year`, `mart_province_road`
- `indicator_catalog`

---

### 4.5 Report Engine Subsystem

**Responsibility:** Data analysis, narrative synthesis, deep analysis, final report composition

**Boundary:**
```
src/subsystems/report_engine/
├── __init__.py              # Public API exports
├── service.py               # ReportEngineService (facade)
├── agents/
│   ├── analyst.py           # Accident Analyst agent factory
│   ├── synthesizer.py       # Research Synthesizer agent factory
│   ├── deep_analyst.py      # Deep Policy Analyst agent factory
│   └── composer.py          # Report Composer agent factory
├── prompts/
│   ├── analyst.py           # Analyst prompt templates
│   ├── synthesizer.py       # Synthesizer prompt templates
│   ├── deep_analyst.py      # Deep analysis prompt templates
│   └── composer.py          # Report composition prompt templates
└── schemas.py               # AnalysisResult, NarrativeBlock, DeepAnalysis
```

**Public Interface:**

```python
class ReportEngineService:
    """Facade สำหรับ Report Engine Subsystem"""

    def create_analysis_agents(self, llm_pro) -> list[Agent]:
        """Create agents 5-9 for chat pipeline"""

    def create_analysis_tasks(
        self,
        agents: list[Agent],
        retrieval_context: str,
        citation_context: str,
    ) -> list[Task]:
        """Create tasks for agents 5-9"""

    def create_policy_agents(self, llm_pro) -> list[Agent]:
        """Create agents for policy brief pipeline (RTI/Mental/NCD + Writer)"""

    def create_policy_tasks(
        self,
        agents: list[Agent],
        retrieval_context: str,
        citation_context: str,
        province: str,
        topics: list[str],
    ) -> list[Task]:
        """Create tasks for policy brief agents"""
```

**Dependencies:**
- Receives: context strings from Orchestrator (retrieval output, citation output)
- External: Gemini API (via CrewAI LLM)

**Database Tables Owned:** None (agents are pure LLM computation)

---

### 4.6 Chart Builder Subsystem

**Responsibility:** Data visualization — query data, build Chart.js specs

**Boundary:**
```
src/subsystems/chart_builder/
├── __init__.py              # Public API exports
├── service.py               # ChartBuilderService (facade)
├── generators/
│   ├── trend.py             # Line/bar trend charts
│   ├── comparison.py        # Bar comparison charts
│   ├── distribution.py      # Pie/doughnut distribution charts
│   └── hotspot.py           # Geographic hotspot charts
├── styling.py               # Color palettes, font config, theme
├── tools.py                 # 7 CrewAI @tool functions
└── schemas.py               # ChartSpec, ChartDataset
```

**Public Interface:**

```python
class ChartBuilderService:
    """Facade สำหรับ Chart Builder Subsystem"""

    def get_tools(self) -> list:
        """Return all CrewAI @tool functions for Agent 6"""

    def create_agent(self, llm_pro) -> Agent:
        """Create Chart Builder agent"""

    def create_task(self, agent: Agent, analysis_context: str) -> Task:
        """Create chart building task"""
```

**Dependencies:**
- Shared Infra: DB Pool (queries for chart data)

**Database Tables Owned:** None (reads from mart tables owned by Database RAG)

---

### 4.7 NotebookLM Bridge Subsystem

**Responsibility:** Integration with NotebookLM CLI for policy brief inspector reports

**Boundary:**
```
src/subsystems/notebooklm/
├── __init__.py              # Public API exports
├── service.py               # NotebookLMService (facade)
├── client.py                # Subprocess CLI wrapper
├── tools.py                 # nlm_ask, get_supported_provinces @tools
├── config.py                # Province-notebook mapping
└── schemas.py               # NLMResponse, ProvinceConfig
```

**Public Interface:**

```python
class NotebookLMService:
    """Facade สำหรับ NotebookLM Bridge Subsystem"""

    async def ask(
        self,
        province: str,
        topic: str,
        query: str | None = None,
        notebook_id: str | None = None,
    ) -> RetrievalResult:
        """Query NotebookLM for province inspection data.
        Returns RetrievalResult with source_type='notebooklm_pdf'"""

    def get_supported_provinces(self) -> list[ProvinceConfig]:
        """List provinces with NotebookLM notebooks configured"""

    def is_province_supported(self, province: str) -> bool:
        """Check if province has NotebookLM data"""

    def get_tools(self) -> list:
        """Return CrewAI @tool functions"""
```

**Dependencies:**
- External: NotebookLM CLI (subprocess)

**Database Tables Owned:** None

---

### 4.8 Orchestration Subsystem

**Responsibility:** Pipeline routing, agent coordination, progress tracking, response assembly

**Boundary:**
```
src/subsystems/orchestration/
├── __init__.py              # Public API exports
├── router.py                # Request Router (chat vs policy brief)
├── chat_pipeline.py         # Chat pipeline builder (9 agents)
├── policy_pipeline.py       # Policy brief pipeline builder (7 agents)
├── foundation.py            # Shared foundation agents builder (4 agents)
├── executor.py              # CrewAI Crew executor + result parser
├── progress.py              # Progress tracking (SSE events)
└── schemas.py               # PipelineConfig, ProgressEvent
```

**Public Interface:**

```python
class Orchestrator:
    """Main entry point — coordinates all subsystems"""

    def __init__(
        self,
        document_rag: DocumentRAGService,
        database_rag: DatabaseRAGService,
        thaijo: ThaiJOService,
        notebooklm: NotebookLMService,
        citation: CitationService,
        report_engine: ReportEngineService,
        chart_builder: ChartBuilderService,
    ):
        """Inject all subsystem services"""

    async def run_chat(
        self,
        message: str,
        session_id: str,
    ) -> AgentResponse:
        """Execute full chat pipeline (9 agents)"""

    async def run_policy_brief(
        self,
        province: str,
        topics: list[str],
        year: int,
    ) -> PolicyBriefResponse:
        """Execute policy brief pipeline (7 agents)"""

    async def run_unified(
        self,
        message: str,
        session_id: str,
    ) -> AgentResponse | PolicyBriefResponse:
        """Auto-route to correct pipeline"""

    async def run_chat_stream(
        self,
        message: str,
        session_id: str,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Execute chat pipeline with SSE progress events"""
```

**Pipeline Assembly:**

```python
# Chat Pipeline Assembly (inside Orchestrator)
async def run_chat(self, message, session_id):
    # 1. Build foundation agents
    interpreter = self._build_interpreter(llm_fast)
    retrieval = self._build_retrieval(llm_fast)     # gets tools from subsystems
    sql_specialist = self._build_sql(llm_fast)
    citation_agent = self._build_citation(llm_fast)

    # 2. Register tools from subsystems
    retrieval.tools = [
        *self.document_rag.get_tools(),      # search_documents
        *self.database_rag.get_retrieval_tools(),  # 7 accident + 2 geography
        *self.thaijo.get_tools(),            # search_thaijo
    ]
    sql_specialist.tools = self.database_rag.get_sql_tools()
    citation_agent.tools = self.citation.get_tools()

    # 3. Build analysis agents from Report Engine
    analysis_agents = self.report_engine.create_analysis_agents(llm_pro)
    chart_agent = self.chart_builder.create_agent(llm_pro)

    # 4. Assemble CrewAI Crew
    crew = Crew(
        agents=[interpreter, retrieval, sql_specialist, citation_agent,
                *analysis_agents, chart_agent],
        tasks=[...],
        process=Process.sequential,
    )

    # 5. Execute and parse
    result = crew.kickoff(inputs={"user_message": message})
    return self._parse_response(result, session_id)
```

**Tool Registration Pattern (Key Design):**

```
Orchestrator สร้าง Agent แล้วฉีด tools จากแต่ละ subsystem

Agent 2 (Retrieval) receives tools from:
  ├── DocumentRAG.get_tools()     → [search_documents]
  ├── DatabaseRAG.get_retrieval_tools() → [7 accident + 2 geography tools]
  ├── ThaiJO.get_tools()          → [search_thaijo]
  └── NotebookLM.get_tools()      → [nlm_ask, get_supported_provinces]  (policy only)

Agent 3 (SQL) receives tools from:
  └── DatabaseRAG.get_sql_tools() → [execute_custom_sql, explain_schema]

Agent 4 (Citation) receives tools from:
  └── Citation.get_tools()        → [lookup_document_apa, register_evidence, register_claim_links]

Agent 6 (Chart) receives tools from:
  └── ChartBuilder.get_tools()    → [7 build_* chart tools]
```

---

## 5. Dependency Injection

### 5.1 Service Registry

```python
# src/subsystems/registry.py

from src.subsystems.document_rag import DocumentRAGService
from src.subsystems.citation import CitationService
from src.subsystems.thaijo import ThaiJOService
from src.subsystems.database_rag import DatabaseRAGService
from src.subsystems.report_engine import ReportEngineService
from src.subsystems.chart_builder import ChartBuilderService
from src.subsystems.notebooklm import NotebookLMService
from src.subsystems.orchestration import Orchestrator


def create_services(settings) -> dict:
    """Create and wire all subsystem services"""

    # Infrastructure
    db_pool = create_db_pool(settings)
    minio = create_minio_client(settings)

    # Subsystems (no cross-dependencies between them)
    document_rag = DocumentRAGService(db_pool=db_pool, minio=minio, settings=settings)
    database_rag = DatabaseRAGService(db_pool=db_pool)
    thaijo = ThaiJOService(settings=settings)
    notebooklm = NotebookLMService(settings=settings)
    citation = CitationService(db_pool=db_pool, settings=settings)
    report_engine = ReportEngineService(settings=settings)
    chart_builder = ChartBuilderService(db_pool=db_pool)

    # Orchestrator (depends on all subsystems)
    orchestrator = Orchestrator(
        document_rag=document_rag,
        database_rag=database_rag,
        thaijo=thaijo,
        notebooklm=notebooklm,
        citation=citation,
        report_engine=report_engine,
        chart_builder=chart_builder,
    )

    return {
        "document_rag": document_rag,
        "database_rag": database_rag,
        "thaijo": thaijo,
        "notebooklm": notebooklm,
        "citation": citation,
        "report_engine": report_engine,
        "chart_builder": chart_builder,
        "orchestrator": orchestrator,
    }
```

### 5.2 FastAPI Integration

```python
# src/main.py

from contextlib import asynccontextmanager
from src.subsystems.registry import create_services

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    services = create_services(settings)

    # Store in app state for router access
    app.state.services = services

    yield

    # Cleanup
    await services["document_rag"].close()
    await services["database_rag"].close()

app = FastAPI(lifespan=lifespan)

# Routers access subsystems via app.state.services
# e.g., request.app.state.services["orchestrator"].run_chat(...)
```

---

## 6. Subsystem Dependency Matrix

```
                    DocRAG  Citation  ThaiJO  DbRAG  Report  Chart  NLM  Orchestrator
DocRAG               -       -         -       -       -      -      -       -
Citation             -       -         -       -       -      -      -       -
ThaiJO               -       -         -       -       -      -      -       -
DbRAG                -       -         -       -       -      -      -       -
Report               -       -         -       -       -      -      -       -
Chart                -       -         -       -       -      -      -       -
NLM                  -       -         -       -       -      -      -       -
Orchestrator         ✓       ✓         ✓       ✓       ✓      ✓      ✓       -

Legend: ✓ = depends on (calls service interface)
```

**Key insight:** Subsystems 1-7 มี **zero cross-dependency** — only Orchestrator knows about all of them. This is intentional:
- เพิ่ม subsystem ใหม่ → แก้แค่ Orchestrator
- Test subsystem เดียว → mock nothing (ยกเว้น infra)
- ลบ subsystem (e.g. ปิด ThaiJO) → แก้แค่ Orchestrator config

---

## 7. Data Flow: Complete Example

### 7.1 Chat Query with ThaiJO

```
User: "สถานการณ์อุบัติเหตุทางถนนในอุบลราชธานี 2567 และงานวิจัยที่เกี่ยวข้อง"

═══ Orchestrator.run_chat() ═══

Step 1: Request Interpreter (Agent 1)
  Input:  user message
  Output: {
    topics: ["accident"],
    geography: "อุบลราชธานี",
    time_range: "2567",
    academic_search_needed: true,
    search_keywords: "อุบัติเหตุทางถนน อุบลราชธานี"
  }

Step 2: Data Retrieval (Agent 2)
  Agent เรียก tools ตาม intent:

  ┌─ DocumentRAG.search_documents("อุบัติเหตุ อุบลราชธานี")
  │   → RetrievalResult(source_type="document_rag", items=[...])
  │
  ├─ DatabaseRAG.get_province_year("อุบลราชธานี", 2567)
  │   → RetrievalResult(source_type="database", items=[...])
  │
  ├─ DatabaseRAG.get_accident_hotspots("อุบลราชธานี", top_n=10)
  │   → RetrievalResult(source_type="database", items=[...])
  │
  └─ ThaiJO.search_thaijo("อุบัติเหตุทางถนน อุบลราชธานี", size=5)
      → RetrievalResult(source_type="thaijo_article", items=[
          {content: "สรุปบทความ...", source_ref: "https://tci-thaijo.org/.../1",
           apa_authors: "สมชาย ใจดี", apa_year: "2567", ...},
          {content: "สรุปบทความ...", source_ref: "https://tci-thaijo.org/.../2",
           ...},
        ])

Step 3: SQL Specialist (Agent 3)
  Optional — runs only if complex queries needed
  → RetrievalResult(source_type="database", items=[...])

Step 4: Citation & Evidence (Agent 4)
  Input: all RetrievalResult[] from step 2-3

  Citation.process([all_retrieval_results])
    ├── normalize_evidence()
    │     doc_rag items  → EvidenceItem(type="document", trust="high")
    │     database items → EvidenceItem(type="database", trust="high")
    │     thaijo items   → EvidenceItem(type="thaijo_article", trust="medium")
    │
    ├── allocate_citation_codes()
    │     EV-001 (doc)    → C-001
    │     EV-002 (mart)   → C-100
    │     EV-003 (thaijo) → C-200
    │     EV-004 (thaijo) → C-201
    │
    ├── format_apa_reference() for each
    │     C-001: "สสจ.อุบลราชธานี. (2567). *รายงาน...*"
    │     C-100: "Musya Agent. (2568). *mart_province_year* [Data set]."
    │     C-200: "สมชาย ใจดี. (2567). ชื่อบทความ. *วารสาร...*"
    │     C-201: "วิจิตร สุขสมบูรณ์. (2566). ชื่อบทความ. *วารสาร...*"
    │
    └── validate_coverage()
          → CoverageReport(score=0.85, supported=6, total=7)

  → CitationContext

Step 5-8: Analysis + Chart + Synthesis + Deep Analysis
  Agents use citation context for inline references [C-xxx]

Step 9: Report Composer
  Writes final markdown with:
  - Inline citations [C-001], [C-100], [C-200], [C-201]
  - Bibliography section
  - Follow-up questions

═══ Response ═══
AgentResponse(
  content="## สถานการณ์อุบัติเหตุ...\n\n... [C-001] ... [C-200] ...",
  citations=[C-001, C-100, C-200, C-201],
  charts=[...],
  metadata={thaijo_search: {term: "...", articles_found: 2}}
)
```

---

## 8. Adding a New Data Source (Extension Guide)

เมื่อต้องการเพิ่ม data source ใหม่ (เช่น WHO API, HDC Service, PubMed):

### Step 1: Create Subsystem

```
src/subsystems/who_api/
├── __init__.py
├── service.py       # WHOService with search() → RetrievalResult
├── client.py        # HTTP client
├── normalizer.py    # WHO response → RetrievalItem
├── tools.py         # CrewAI @tool
└── schemas.py
```

### Step 2: Implement RetrievalResult Contract

```python
class WHOService:
    async def search(self, indicator: str, country: str) -> RetrievalResult:
        # Must return RetrievalResult with:
        # - source_type: "external_api" (or new type)
        # - items: list[RetrievalItem] with apa_* metadata
        # - metadata: search params + timing
```

### Step 3: Register in Citation Code Allocator

```python
# src/subsystems/citation/code_allocator.py
RANGES = {
    ...existing...,
    "who_api": (250, 269),    # C-250 to C-269
}
```

### Step 4: Register in Orchestrator

```python
# src/subsystems/orchestration/chat_pipeline.py
retrieval.tools = [
    *self.document_rag.get_tools(),
    *self.database_rag.get_retrieval_tools(),
    *self.thaijo.get_tools(),
    *self.who_api.get_tools(),       # ← NEW
]
```

### Step 5: Add APA Format (if needed)

```python
# src/subsystems/citation/apa_formatter.py
def format_who_dataset(self, ev: EvidenceItem) -> APAReference:
    """World Health Organization. ({year}). *{indicator}* [Data set]. WHO GHO. {url}"""
```

**ไม่ต้องแก้:** Report Engine, Chart Builder, other subsystems

---

## 9. Directory Structure (Complete)

```
src/
├── main.py                          # FastAPI app + lifespan
├── config.py                        # Settings (all subsystem configs)
│
├── subsystems/
│   ├── __init__.py
│   ├── registry.py                  # Service factory + DI wiring
│   ├── contracts.py                 # Shared types (RetrievalResult, etc.)
│   │
│   ├── document_rag/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── ingestion.py
│   │   ├── search.py
│   │   ├── chunker.py
│   │   ├── extractor.py
│   │   ├── tools.py
│   │   └── schemas.py
│   │
│   ├── citation/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── normalizer.py
│   │   ├── apa_formatter.py
│   │   ├── code_allocator.py
│   │   ├── coverage.py
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   └── agent.py
│   │
│   ├── thaijo/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── client.py
│   │   ├── normalizer.py
│   │   ├── tools.py
│   │   └── schemas.py
│   │
│   ├── database_rag/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── accident/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   ├── tools.py
│   │   │   └── schemas.py
│   │   ├── sql/
│   │   │   ├── __init__.py
│   │   │   ├── executor.py
│   │   │   ├── tools.py
│   │   │   └── validator.py
│   │   └── geography/
│   │       ├── __init__.py
│   │       ├── service.py
│   │       └── tools.py
│   │
│   ├── report_engine/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── agents/
│   │   │   ├── analyst.py
│   │   │   ├── synthesizer.py
│   │   │   ├── deep_analyst.py
│   │   │   └── composer.py
│   │   ├── prompts/
│   │   │   ├── analyst.py
│   │   │   ├── synthesizer.py
│   │   │   ├── deep_analyst.py
│   │   │   └── composer.py
│   │   └── schemas.py
│   │
│   ├── chart_builder/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── generators/
│   │   │   ├── trend.py
│   │   │   ├── comparison.py
│   │   │   ├── distribution.py
│   │   │   └── hotspot.py
│   │   ├── styling.py
│   │   ├── tools.py
│   │   └── schemas.py
│   │
│   ├── notebooklm/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── client.py
│   │   ├── tools.py
│   │   ├── config.py
│   │   └── schemas.py
│   │
│   └── orchestration/
│       ├── __init__.py
│       ├── router.py
│       ├── chat_pipeline.py
│       ├── policy_pipeline.py
│       ├── foundation.py
│       ├── executor.py
│       ├── progress.py
│       └── schemas.py
│
├── routers/                         # Thin API layer (delegates to subsystems)
│   ├── chat.py
│   ├── policy_brief.py
│   ├── documents.py
│   ├── evidence.py
│   ├── citation.py
│   ├── thaijo.py
│   ├── upload.py
│   ├── ingest.py
│   ├── health.py
│   └── test_ui.py
│
├── db/                              # Shared infrastructure
│   ├── pool.py
│   └── minio_client.py
│
└── database/                        # SQL migrations
    ├── 001_shared_core.sql
    ├── ...
    └── 015_thaijo_evidence.sql
```

---

## 10. Migration Path (Current → Subsystems)

### Phase 1: Create contracts + subsystem shells (1-2 days)

| Task | Detail |
|------|--------|
| Create `contracts.py` | Define RetrievalResult, RetrievalItem, CitationContext |
| Create subsystem directories | Empty `__init__.py` + `service.py` skeleton for each |
| Create `registry.py` | Service factory with current code wrapped in facades |

### Phase 2: Extract Document RAG (1-2 days)

| Task | Detail |
|------|--------|
| Move `rag/document_rag.py` → `subsystems/document_rag/ingestion.py` | |
| Move `rag/vector_store.py` → `subsystems/document_rag/search.py` | |
| Move `tools/common.py:search_documents` → `subsystems/document_rag/tools.py` | |
| Create `DocumentRAGService` facade | Wrap existing functions |
| Update imports in orchestrator | Point to new locations |

### Phase 3: Extract Citation (1-2 days)

| Task | Detail |
|------|--------|
| Move `agents/citation_evidence.py` → `subsystems/citation/agent.py` | |
| Move `utils/apa_formatter.py` → `subsystems/citation/apa_formatter.py` | |
| Move `schemas/evidence.py` → `subsystems/citation/schemas.py` | |
| Create `CitationService` facade | |
| Create `CodeAllocator` from inline logic | |
| Create `normalizer.py` | Extract from citation agent prompt → code |

### Phase 4: Extract Database RAG (1-2 days)

| Task | Detail |
|------|--------|
| Move `tools/accident.py` → `subsystems/database_rag/accident/tools.py` | |
| Move `tools/sql_tools.py` → `subsystems/database_rag/sql/` | |
| Move `tools/common.py:get_geography_*` → `subsystems/database_rag/geography/` | |
| Create `DatabaseRAGService` facade | |

### Phase 5: Add ThaiJO subsystem (1-2 days)

| Task | Detail |
|------|--------|
| Create `subsystems/thaijo/` | New code (from THAIJO_AGENT_IMPLEMENTATION.md) |
| Implement ThaiJOService | |
| Register tools in orchestrator | |
| Add migration 015 | |

### Phase 6: Extract remaining subsystems (2-3 days)

| Task | Detail |
|------|--------|
| Move chart tools → `subsystems/chart_builder/` | |
| Move NLM tools → `subsystems/notebooklm/` | |
| Move analysis agents → `subsystems/report_engine/` | |
| Refactor orchestrator to use subsystem interfaces | |

### Phase 7: Refactor orchestrator (1-2 days)

| Task | Detail |
|------|--------|
| Rewrite `orchestrator.py` → `subsystems/orchestration/` | |
| Use dependency injection via `registry.py` | |
| Update all routers to use `app.state.services` | |
| Remove old `src/agents/`, `src/tools/`, `src/rag/` directories | |

**Total: ~10-15 days**

---

## 11. Testing Strategy per Subsystem

| Subsystem | Unit Test Focus | Integration Test | Mock Strategy |
|-----------|----------------|------------------|---------------|
| Document RAG | chunker, extractor, search ranking | Ingest → search round-trip | Mock MinIO + pgvector |
| Citation | APA formatting, code allocation, coverage calc | normalize → cite → validate | Mock DB, provide RetrievalResult fixtures |
| ThaiJO | normalizer, reference parser, error handling | HTTP call → RetrievalResult | Mock httpx (ThaiJO microservice) |
| Database RAG | SQL validator, query builders | Tool → DB round-trip | Use test PostgreSQL with fixtures |
| Report Engine | Prompt templates, output parsing | Agent → markdown output | Mock LLM with canned responses |
| Chart Builder | ChartSpec structure, color assignment | Tool → ChartSpec | Mock DB queries |
| NotebookLM | CLI wrapper, timeout handling | NLM → RetrievalResult | Mock subprocess |
| Orchestration | Pipeline assembly, tool registration, routing | Full pipeline E2E | Mock all subsystem services |

```bash
# Run tests per subsystem
pytest tests/subsystems/document_rag/ -v
pytest tests/subsystems/citation/ -v
pytest tests/subsystems/thaijo/ -v
pytest tests/subsystems/database_rag/ -v
pytest tests/subsystems/orchestration/ -v

# Full integration
pytest tests/integration/ -v
```

---

## 12. Benefits Summary

| Before (Monolithic) | After (Subsystems) |
|---------------------|-------------------|
| 10+ tools in one agent | Tools grouped by domain |
| Citation logic in 4+ files | Single Citation subsystem |
| Adding ThaiJO touches 6+ files | New subsystem + Orchestrator only |
| Can't test RAG without full pipeline | Test each subsystem independently |
| Import chain 4+ levels deep | Max 2 levels (router → orchestrator → subsystem) |
| Agent prompt has all responsibility | Each subsystem owns its prompts |
| No clear ownership of DB tables | Each subsystem owns its tables |
| Adding new data source = surgery | Plug-in: implement service + register |

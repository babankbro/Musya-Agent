# Document Tables Analysis
**Last updated:** 2026-04-14  
**Based on:** live database `chat-aio` (container `chatv1_postgres`)

---

## Current State (Row Counts)

| Table | Rows | Has Data | Status |
|-------|------|----------|--------|
| `document_registry` | **4** | ✅ Yes | Active — master catalogue |
| `document_embeddings` | **6** | ✅ Yes | Active — vector store |
| `document_chunks` | — | — | 🗑️ **DROPPED** (migration 014) |

---

## What Each Table Does

### 1. `document_registry` — Master catalogue (APA lives here)

**Created by:** `002_document_rag.sql` + expanded in `012_document_upload_enhanced.sql`

This is the **source of truth** for every document in the system. It stores:
- Document identity: `title`, `topic`, `document_type`
- File locations: `file_path`, `minio_path`
- Ingestion lifecycle: `ingestion_status` (`pending` → `completed` / `failed`), `chunk_count`
- **All APA metadata fields:**

| Column | APA role |
|--------|----------|
| `apa_authors` | Author(s) or organisation |
| `apa_year` | Publication year |
| `apa_publisher` | Publisher / organisation |
| `apa_doi` | DOI identifier |
| `apa_url` | URL for web/online sources |
| `apa_accessed` | Access date (websites) |
| `apa_edition` | Edition |
| `apa_volume` | Volume / issue |
| `apa_pages` | Page range |
| `apa_type` | Reference type: `report`, `book`, `article`, `website`, `dataset`, `law` |
| `apa_approval_status` | `pending` → `draft` → **`approved`** / `rejected` |

**➡ APA data is stored here and ONLY here.**  
The `apa_citation` string shown in the UI is **computed on the fly** by `format_apa_reference()` in `src/utils/apa_formatter.py` from these columns — it is **not stored as a column**.

---

### 2. `document_embeddings` — Active vector store (pgvector)

**Created by:** `011_pgvector.sql`  
**Replaces:** ChromaDB collection `musya_documents`

| Column | Purpose |
|--------|---------|
| `id` | MD5 hash of `source::chunk_index` |
| `document` | Raw chunk text (used for search result display) |
| `embedding` | `vector(3072)` — Google Gemini `gemini-embedding-001` |
| `source` | MinIO object path, e.g. `accident/road_safety_policy_2025.txt` |
| `title` | Filename-derived title |
| `topic` | Folder-derived topic |
| `chunk_index` | Chunk position (0-based) |
| `total_chunks` | Total chunks in this document |
| `page_ref`, `section_label` | Structural metadata |

**What the 6 rows contain (actual data):**

| source | title | chunks |
|--------|-------|--------|
| `nutrition/nutrition_standards.txt` | nutrition standards | 1 |
| `accident/road_safety_policy_2025.txt` | road safety policy 2025 | 2 |
| `mental_health/mental_health_guidelines.txt` | mental health guidelines | 1 |
| `accident/accident_statistics_2024.txt` | accident statistics 2024 | 2 |

The 4 registry rows were back-filled in session 2026-04-14 using a one-time SQL insert from `document_embeddings`.  
Going forward both tables are always written together by all ingest paths.

---

## Where APA Is Stored

| Location | What's there |
|----------|-------------|
| `document_registry` columns (`apa_*`) | ✅ **The only APA store** — raw editable fields |
| `document_embeddings.title` / `.topic` | ⚠️ Filename-derived only, no full APA fields |
| UI `apa_citation` string | Computed at runtime by `src/utils/apa_formatter.py` — not persisted |

---

## Current Architecture (Clean — post migration 014)

```
document_registry  (1 row per document)
  │  title, topic, document_type, minio_path, file_path
  │  ingestion_status, chunk_count, apa_approval_status
  │  apa_authors, apa_year, apa_publisher, apa_doi,
  │  apa_type, apa_edition, apa_volume, apa_pages
  │
  └──► document_embeddings  (N rows = N chunks per document)
         id (MD5 of source::chunk_index)
         document  (chunk text)
         embedding (vector 3072-dim, Gemini gemini-embedding-001)
         source, title, topic, chunk_index, total_chunks
         page_ref, section_label
         Soft-linked: document_embeddings.source = document_registry.minio_path
```

No foreign key between the two tables — join via `source = minio_path`.

---

## Ingest Paths (both write to both tables)

```
Path A — Scan & Ingest All  (POST /api/ingest)
  MinIO file → ingest_all_documents()
    ├── extract text → chunk → embed → document_embeddings  ✅
    └── _upsert_registry()                → document_registry   ✅

Path B — Approve single file  (POST /api/documents/minio/approve)
  MinIO file → minio_approve()
    ├── INSERT/UPDATE document_registry (with APA fields)     ✅
    └── ingest_single_document()
          └── add_documents() → document_embeddings            ✅

Path C — Upload new file  (POST /api/documents/upload)
  → upload_to_minio() → ingest_single_document()
    ├── document_embeddings                                    ✅
    └── document_registry (via _insert_document_registry)     ✅
```

---

## Removed Table

| Table | Removed in | Reason |
|-------|-----------|--------|
| `document_chunks` | migration 014 | ChromaDB-era design. Chunk text + vectors now live together in `document_embeddings`. Was empty (0 rows) since pgvector migration (011). |

---
title: Glossary
type: meta
tags: [meta, glossary]
updated: 2026-05-16
---

# 📖 Glossary

Domain & technical terms used across the Musya Agent vault.

## Pipelines

- **Chat pipeline** — Default 10-agent CrewAI pipeline (Router → Interpreter → Retrieval → SQL → Citation → Analyst → Chart → Synthesizer → Deep Analyst → Composer). See [[02.01 - Agent Workflows]].
- **Policy Brief pipeline** — 9 agents (reuses Agents 1–4 + RTI/Mental/NCD analysts + Policy Report Writer + NLM data fetcher).
- **Short Chat pipeline** — 3-agent fast path (Router → Quick Retrieval → Quick Answer Writer), targets 30–60s. See [[03.03 - Short Chat Pipeline]].

## Agents (Chat pipeline)

- **Router** (Agent 0) — picks chat vs policy_brief pipeline; mode flag for short chat.
- **Interpreter** (Agent 1) — turns user message into structured JSON `{ topics, geography, time_range, focus, language }`.
- **Retrieval** (Agent 2) — searches Document RAG + DB + ThaiJO (11 tools).
- **SQL Specialist** (Agent 3) — writes/runs custom SQL. See [[02.02 - Agent - SQL Specialist]].
- **Citation & Evidence** (Agent 4) — normalize evidence, register, APA. See [[02.03 - Agent - Citation & Evidence]].
- **Accident Analyst** (Agent 5) — applies Haddon Matrix, identifies trends/risk areas.
- **Chart Builder** (Agent 6) — produces `ChartSpec` JSON for Chart.js.
- **Research Synthesizer** (Agent 7) — narrative prose (1,200–2,000 words).
- **Deep Analyst** (Agent 8) — root cause / policy gap (1,000–1,500 words).
- **Report Composer** (Agent 9) — final Thai-language report (2,000–4,000 words).

## Subsystems

- **Document RAG** — PDF/DOCX → MinIO → pgvector (3072-dim Gemini embeddings).
- **Database RAG** — Postgres mart tables, queried by retrieval/SQL tools.
- **ThaiJO** — TCI-THAIJO academic article search microservice. Citation range C-200~C-299.
- **NotebookLM bridge** — `nlm_ask` tool for province-specific summaries (Policy Brief).

## Data domains

- **RTI** — Road Traffic Injury (the primary domain in Phase 1).
- **Mental Health** — Includes suicide prevention; requires safety guardrails.
- **NCD** — Non-Communicable Disease + Nutrition (3-flow framework: upstream/midstream/downstream).

## Database

- **Fact tables** — `fact_accident_event`, `fact_accident_person` (granular events).
- **Dimension tables** — `dim_geography`, `dim_road_segment`, `dim_time`, `dim_source`.
- **Mart tables** — `mart_accident_summary`, `mart_accident_hotspot`, `mart_province_year`, `mart_province_road` (pre-aggregated for fast queries).
- **document_registry** — All document metadata + APA fields.
- **document_embeddings** — pgvector table (3072-dim chunks).
- **evidence_registry** — Evidence items registered by Citation Agent (supports `thaijo_article` source type since migration 015/017).
- **thaijo_search_cache** — Persisted ThaiJO search results (introduced in migration 018 to fix URL hallucination; see [[06.04 - ThaiJO Fix History]]).

## Citation code ranges

- `C-001 – C-099` — Documents/reports (Document RAG)
- `C-100 – C-199` — Database query results
- `C-200 – C-299` — ThaiJO articles
- `C-300+` — External / other

## Infrastructure

- **PostgreSQL** — `chat-aio` database (shared with ChatV1 frontend).
- **MinIO** — Object storage for uploaded PDFs/DOCX (bucket: `uploads`).
- **pgvector** — Postgres extension for vector similarity (`pgvector/pgvector:pg16`).
- **Gemini** — LLM (Fast: `gemini-2.0-flash`, Pro: `gemini-2.5-pro`) + embedding (`models/gemini-embedding-001`).

## Conventions

- **LLM tier — fast** — `gemini-2.0-flash`, used for deterministic/parsing tasks.
- **LLM tier — pro** — `gemini-2.5-pro`, used for analysis/synthesis/writing.
- **`.replace()` not `.format()`** — prompt templates use `.replace("{user_message}", ...)` because JSON braces conflict with Python's `.format()`.

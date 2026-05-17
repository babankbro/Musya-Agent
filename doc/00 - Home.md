---
title: Musya Agent — Knowledge Vault
type: moc
tags: [home, moc, index]
updated: 2026-05-16
---

# 🧭 Musya Agent — Knowledge Vault

> **Project:** Musya Agent — Agentic AI + RAG backend for Thai road-accident / public health analytics
> **Stack:** Python · FastAPI · CrewAI · PostgreSQL · pgvector · MinIO · Google Gemini
> **Vault structure:** numbered folders, YAML frontmatter, `[[wikilinks]]`, archived originals under `_archive/`

---

## 🚀 Start Here

| If you are… | Read first |
|---|---|
| **New to the project** | [[07.01 - Project Documentation]] → [[01.01 - System Architecture]] |
| **Building an agent** | [[02.01 - Agent Workflows]] → relevant agent page in `02 - Agents/` |
| **Working on database** | [[01.03 - Database & API Reference]] |
| **Designing a report** | [[05.01 - Report Writing Style]] |
| **Debugging ThaiJO** | [[06.04 - ThaiJO Fix History]] → [[03.01 - ThaiJO Integration]] |
| **Looking for current pulse** | [[06.01 - Implementation Status]] |

---

## 🗺️ Maps of Content

### 01 — Architecture
- [[01.01 - System Architecture]] — current state (v2.1), tech stack, 10-agent pipeline, RAG layers
- [[01.02 - Strategic Design & Roadmap]] — 3-domain vision, subsystem refactoring proposal
- [[01.03 - Database & API Reference]] — unified DB schema, migrations, connection pools, API endpoints

### 02 — Agents (Chat Pipeline · 10 agents)
- [[02.01 - Agent Workflows]] — Chat / Policy Brief / Short Chat pipelines, routing, style-guide alignment
- [[02.02 - Agent - SQL Specialist]] — Agent 3, query patterns, schema knowledge
- [[02.03 - Agent - Citation & Evidence]] — Agent 4, evidence registry, claim linking, testing
- [[02.04 - Reference - APA Format]] — APA 7th formatting rules, citation code ranges
- [[02.05 - Plan - Field Enricher Agent]] — ThaiJO Evidence Sync Agent (p04 plan)
- [[02.06 - Plan - Accident Policy Agent]] — Zone 10 specific policy questions agent

### 03 — Subsystems
- [[03.01 - ThaiJO Integration]] — `search_thaijo` tool, C-200~C-299 citations
- [[03.02 - ThaiJO Research SRS]] — 6-agent research-report pipeline (FR-TJR-001..006)
- [[03.03 - Short Chat Pipeline]] — fast-path 3-agent design (30–60s responses)
- [[03.04 - Document Upload & RAG]] — upload → MinIO → pgvector, APA approval flow

### 04 — Testing & QA
- [[04.01 - Test UI - Unified Router]] — multi-pipeline test harness (5 tabs)
- [[04.02 - Test UI - Policy Brief]] — Policy Brief UI design (4 tabs, Tailwind+Thai)
- [[04.03 - Plan - ThaiJO Test Tab]] — ThaiJO Agent Test tab (5th tab, URL fix)

### 05 — Style Guides
- [[05.01 - Report Writing Style]] — Policy Brief tone/structure for RTI/Mental/NCD

### 06 — Status & Plans
- [[06.01 - Implementation Status]] — **current pulse** (v7.1, what's shipped)
- [[06.02 - Plan - Shared Agent Verify]] — active ThaiJO hallucination fix plan (p01)
- [[06.03 - Log - Shared Agent Implementation]] — Shared Foundation hardening tasks (c01)
- [[06.04 - ThaiJO Fix History]] — chronological fix archive (FIX + d01 + d02 + p03)

### 07 — Project Overview
- [[07.01 - Project Documentation]] — comprehensive ~500-line reference (architecture + setup + agents + APIs)

---

## 🏷️ Tag Taxonomy

See [[_meta/Tags]] for the full taxonomy. Common tags:

- `#architecture` — system-level design
- `#agent` — individual agent specs
- `#subsystem` — ThaiJO, RAG, citation, document-upload
- `#api` — endpoint specs
- `#database` — schema, migrations
- `#testing` — test UIs and procedures
- `#plan` — active implementation plans
- `#log` — implementation logs / debug histories
- `#style-guide` — writing/output conventions
- `#status/active` `#status/done` `#status/archived` — lifecycle

---

## 📁 Original Documents

All 35 source documents are preserved under [[_archive]] for traceability. Each canonical page lists its source files in its frontmatter `sources:` field.

---

## 🔧 Vault Conventions

- **Filenames:** `NN.NN - Title Case.md` (numeric prefix for stable ordering)
- **Wikilinks:** `[[NN.NN - Page Name]]` — full filename, no `.md`
- **Frontmatter:** every page has `title / type / tags / updated / sources`
- **Status field:** `status: active | done | archived | proposal`
- **Type field:** `moc | architecture | agent-spec | subsystem | plan | log | reference | style-guide | overview`

---
title: 03 — Subsystems (MOC)
type: moc
tags: [moc, subsystem]
updated: 2026-05-16
---

# 🧩 03 — Subsystems

Cross-cutting feature subsystems that span multiple agents and routers.

## Pages

| Page | Scope | Status |
|---|---|---|
| [[03.01 - ThaiJO Integration]] | `search_thaijo` tool, citation range C-200~C-299, evidence schema | `done` |
| [[03.02 - ThaiJO Research SRS]] | 6-agent literature-review pipeline (FR-TJR-001..006) | `proposal` |
| [[03.03 - Short Chat Pipeline]] | 3-agent fast path (30–60s); also documents ThaiJO subsystem & UI mode toggle | `active` |
| [[03.04 - Document Upload & RAG]] | Upload → MinIO → pgvector flow, APA approval, source link resolution | `active` |

## Related

- [[06.04 - ThaiJO Fix History]] — chronological fix archive for ThaiJO
- [[02.03 - Agent - Citation & Evidence]] — citation flow used by all subsystems
- [[01.03 - Database & API Reference]]

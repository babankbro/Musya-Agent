---
title: 02 — Agents (MOC)
type: moc
tags: [moc, agent]
updated: 2026-05-17
---

# 🤖 02 — Agents

Per-agent specifications + the unified workflow doc. The Chat pipeline has 10 agents (Router + 9 sequential); Policy Brief reuses Agents 1–4 and adds domain analysts.

## Pages

| Page | Pipeline role | Status |
|---|---|---|
| [[02.01 - Agent Workflows]] | **MOC for all pipelines** — Chat / Policy Brief / Short Chat + style-guide alignment | `active` |
| [[02.02 - Agent - SQL Specialist]] | Agent 3 — custom SQL with schema awareness | `active` |
| [[02.03 - Agent - Citation & Evidence]] | Agent 4 — evidence registry, APA citations, coverage | `active` |
| [[02.04 - Reference - APA Format]] | APA 7th formatting rules, citation code ranges (companion to 02.03) | `active` |
| [[02.05 - Plan - Field Enricher Agent]] | ThaiJO Evidence Sync Agent — fill null cache fields & register evidence (P04) | `plan` |
| [[02.06 - Plan - Accident Policy Agent]] | Implementation plan for Zone 10 Accident Policy pipeline | `done` |
| [[02.07 - Agent - Accident Policy (Zone 10)]] | **Spec**: 3-agent pipeline (SqlFetcher → PolicyAnalyst → ReportWriter) + 7 SQL tools + Haddon Matrix | `active` |

## Agent roster (chat pipeline)

| # | Role | Tools | LLM tier |
|---|---|---|---|
| 0 | Request Router | — | fast |
| 1 | Request Interpreter | — | fast |
| 2 | Data Retrieval | 11 tools (search_docs, ThaiJO, accident analytics) | fast |
| 3 | SQL Specialist → [[02.02 - Agent - SQL Specialist]] | execute_custom_sql, explain_schema, get_table_row_count | fast |
| 4 | Citation & Evidence → [[02.03 - Agent - Citation & Evidence]] | list_all_documents_apa, lookup_document_apa, register_evidence, register_claim_links | fast |
| 5 | Accident Analyst | — | pro |
| 6 | Chart Builder | 7 chart-building tools | pro |
| 7 | Research Synthesizer | — | pro |
| 8 | Deep Analyst | — | pro |
| 9 | Report Composer | — | pro |

## Related

- [[01.01 - System Architecture]]
- [[05.01 - Report Writing Style]] — output style for reports
- [[06.02 - Plan - Shared Agent Verify]] — active hardening plan

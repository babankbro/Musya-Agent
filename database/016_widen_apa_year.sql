-- Migration 016: Widen apa_year from VARCHAR(10) to VARCHAR(50)
-- APA year values can include ranges like "2020-2023" or "n.d." which exceed 10 chars

ALTER TABLE document_registry
  ALTER COLUMN apa_year TYPE VARCHAR(50);

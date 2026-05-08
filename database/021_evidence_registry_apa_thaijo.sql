-- Migration 021: Add APA metadata + thaijo_summary columns to evidence_registry
-- Required for ThaiJO Evidence Sync Agent (P04) to store bibliographic data
-- alongside standard evidence fields.

ALTER TABLE evidence_registry
  ADD COLUMN IF NOT EXISTS apa_type      VARCHAR(50)  DEFAULT 'article',
  ADD COLUMN IF NOT EXISTS apa_authors   TEXT         DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_year      VARCHAR(50)  DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_publisher VARCHAR(500) DEFAULT '',
  ADD COLUMN IF NOT EXISTS thaijo_summary TEXT        DEFAULT '';

COMMENT ON COLUMN evidence_registry.apa_type      IS 'APA citation type: article, book, report, etc.';
COMMENT ON COLUMN evidence_registry.apa_authors   IS 'APA-formatted author string';
COMMENT ON COLUMN evidence_registry.apa_year      IS 'Publication year (B.E. or C.E.)';
COMMENT ON COLUMN evidence_registry.apa_publisher IS 'Journal name or publisher';
COMMENT ON COLUMN evidence_registry.thaijo_summary IS 'Full GPT-4.1 summary from Redis pdf_cache (untruncated)';

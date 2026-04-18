-- Migration 015: ThaiJO article evidence support
-- Extends evidence_registry for thaijo_article evidence type

-- Add ThaiJO-specific columns to evidence_registry
ALTER TABLE evidence_registry
    ADD COLUMN IF NOT EXISTS thaijo_pdf_url  TEXT,
    ADD COLUMN IF NOT EXISTS thaijo_reference TEXT,
    ADD COLUMN IF NOT EXISTS thaijo_search_term TEXT;

-- Add comments
COMMENT ON COLUMN evidence_registry.thaijo_pdf_url IS
    'Direct PDF URL on TCI-THAIJO portal';
COMMENT ON COLUMN evidence_registry.thaijo_reference IS
    'Raw APA citation text extracted from TCI-THAIJO HTML (div#citationOutput)';
COMMENT ON COLUMN evidence_registry.thaijo_search_term IS
    'Search term used to find this article via ThaiJO microservice';

-- Index for filtering ThaiJO evidence
CREATE INDEX IF NOT EXISTS idx_evidence_thaijo
    ON evidence_registry (evidence_type)
    WHERE evidence_type = 'thaijo_article';

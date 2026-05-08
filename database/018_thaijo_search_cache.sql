-- Migration 018: ThaiJO Search Cache
-- Purpose: Store raw API results immediately after search_thaijo() receives response,
--          before sending JSON to LLM. This is the source of truth for URL verification.
-- Fixes: RC-5 (no persistence of API results before LLM)

CREATE TABLE IF NOT EXISTS thaijo_search_cache (
    cache_key       VARCHAR(64) PRIMARY KEY,   -- sha256(normalized_term|size=N)
    search_term     TEXT NOT NULL,
    normalized_term TEXT NOT NULL,
    results_json    JSONB NOT NULL,            -- raw API results array
    result_count    INTEGER DEFAULT 0,
    api_called_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP NOT NULL,        -- NOW() + THAIJO_CACHE_TTL_DAYS
    hit_count       INTEGER DEFAULT 0,
    last_hit_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_thaijo_cache_term
    ON thaijo_search_cache(normalized_term);

CREATE INDEX IF NOT EXISTS idx_thaijo_cache_expires
    ON thaijo_search_cache(expires_at);

-- GIN index for lookup by pdf_url inside JSONB array
-- Enables query: WHERE results_json @> '[{"pdf_url": "https://..."}]'::jsonb
CREATE INDEX IF NOT EXISTS idx_thaijo_cache_pdf_urls
    ON thaijo_search_cache USING GIN (results_json);

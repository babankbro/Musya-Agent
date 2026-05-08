-- Migration 019: Cleanup ThaiJO evidence_registry — clear URLs not verified in thaijo_search_cache
-- Run AFTER database/018_thaijo_search_cache.sql (Task 1) is in place and cache is populated.
-- Safe to run multiple times (idempotent — already-empty open_url rows are unaffected).
--
-- Step 1: Clear open_url for ThaiJO entries whose URL is NOT found in thaijo_search_cache
UPDATE evidence_registry er
SET open_url = ''
WHERE er.evidence_type = 'thaijo_article'
  AND er.open_url != ''
  AND NOT EXISTS (
      SELECT 1
      FROM thaijo_search_cache tsc
      WHERE tsc.results_json @> jsonb_build_array(
                jsonb_build_object('pdf_url', er.open_url)
            )
        AND tsc.expires_at > NOW()
  );

-- Step 2: Diagnostic summary — how many ThaiJO entries now have empty open_url
SELECT
    COUNT(*) FILTER (WHERE open_url = '')  AS cleared_count,
    COUNT(*) FILTER (WHERE open_url != '') AS confirmed_count,
    COUNT(*)                               AS total_thaijo_entries
FROM evidence_registry
WHERE evidence_type = 'thaijo_article';

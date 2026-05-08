-- Migration 020: Fix download URLs in evidence_registry for thaijo_article rows
-- Normalizes /article/view/NNNNN/MMMMM  →  /article/view/NNNNN
-- Affects open_url, source_ref, original_url columns
-- Safe to run multiple times (idempotent)

-- 1. open_url: strip /download/NNNNN suffix
UPDATE evidence_registry
SET open_url = regexp_replace(open_url, '/download/[0-9]+$', '', 'g')
WHERE evidence_type = 'thaijo_article'
  AND open_url ~ '/download/[0-9]+$';

-- 2. open_url: strip extra /view/NNNNN/MMMMM → /view/NNNNN (trailing segment)
UPDATE evidence_registry
SET open_url = regexp_replace(open_url, '(/article/view/[0-9]+)/[0-9]+$', '\1', 'g')
WHERE evidence_type = 'thaijo_article'
  AND open_url ~ '/article/view/[0-9]+/[0-9]+$';

-- 3. source_ref: same normalization
UPDATE evidence_registry
SET source_ref = regexp_replace(source_ref, '/download/[0-9]+$', '', 'g')
WHERE evidence_type = 'thaijo_article'
  AND source_ref ~ '/download/[0-9]+$';

UPDATE evidence_registry
SET source_ref = regexp_replace(source_ref, '(/article/view/[0-9]+)/[0-9]+$', '\1', 'g')
WHERE evidence_type = 'thaijo_article'
  AND source_ref ~ '/article/view/[0-9]+/[0-9]+$';

-- 4. original_url: same normalization
UPDATE evidence_registry
SET original_url = regexp_replace(original_url, '/download/[0-9]+$', '', 'g')
WHERE evidence_type = 'thaijo_article'
  AND original_url ~ '/download/[0-9]+$';

UPDATE evidence_registry
SET original_url = regexp_replace(original_url, '(/article/view/[0-9]+)/[0-9]+$', '\1', 'g')
WHERE evidence_type = 'thaijo_article'
  AND original_url ~ '/article/view/[0-9]+/[0-9]+$';

-- Verification query (run to confirm result)
-- SELECT evidence_id, open_url, source_ref, original_url
-- FROM evidence_registry
-- WHERE evidence_type = 'thaijo_article'
--   AND (open_url ~ '/download/' OR source_ref ~ '/download/' OR original_url ~ '/download/'
--     OR open_url ~ '/view/[0-9]+/[0-9]+$' OR source_ref ~ '/view/[0-9]+/[0-9]+$');

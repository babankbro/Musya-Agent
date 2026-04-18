-- Migration 017: Fix evidence_type constraint to support thaijo_article
-- Allows the Citation & Evidence agent to register ThaiJO articles correctly

-- First, drop the old constraint if it exists
-- The constraint name might be system-generated (like evidence_registry_evidence_type_check) 
-- or explicit if created as part of the column definition.
-- In PostgreSQL, constraints created inline in CREATE TABLE are often anonymous or named by position.
-- We'll try to drop it by name if we can find it, or just use a DO block to find and drop it.

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'evidence_registry'::regclass
      AND conname LIKE 'evidence_registry_evidence_type_check%';

    IF constraint_name IS NOT NULL THEN
        EXECUTE 'ALTER TABLE evidence_registry DROP CONSTRAINT ' || constraint_name;
    END IF;
END $$;

-- Add the new, expanded constraint
ALTER TABLE evidence_registry
    ADD CONSTRAINT evidence_registry_evidence_type_check
    CHECK (evidence_type IN ('document', 'database', 'api', 'thaijo_article'));

-- Also check trust_level constraint just in case it needs expansion
-- Currently: CHECK (trust_level IN ('high', 'medium', 'low'))
-- This is fine for now as ThaiJO is 'medium'.

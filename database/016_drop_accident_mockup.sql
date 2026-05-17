-- Migration 016: Drop legacy accident mockup table
-- The `accident` table was a flat denormalized mockup (100 rows, Thai BE years 2567-2568).
-- All real accident data lives in fact_accident_event (star schema, 2020-2026 CE).
-- No foreign keys reference accident, so this is safe.

DROP TABLE IF EXISTS accident;

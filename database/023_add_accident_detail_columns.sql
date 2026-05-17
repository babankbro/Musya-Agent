-- Migration 023: Add accident_location and cause_presumed columns to fact_accident_event
-- These map to CSV fields: บริเวณที่เกิดเหตุ and มูลเหตุสันนิษฐาน

ALTER TABLE fact_accident_event
    ADD COLUMN IF NOT EXISTS accident_location VARCHAR(255),
    ADD COLUMN IF NOT EXISTS cause_presumed    VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_accident_location ON fact_accident_event(accident_location);
CREATE INDEX IF NOT EXISTS idx_accident_cause    ON fact_accident_event(cause_presumed);

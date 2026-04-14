-- Migration 013: Add apa_approval_status column to document_registry
-- Tracks whether a file's APA metadata has been reviewed and approved

ALTER TABLE document_registry
  ADD COLUMN IF NOT EXISTS apa_approval_status VARCHAR(20) DEFAULT 'pending'
    CHECK (apa_approval_status IN ('pending', 'draft', 'approved', 'rejected'));

COMMENT ON COLUMN document_registry.apa_approval_status IS
  'pending=not yet reviewed, draft=AI draft generated waiting for user approval, approved=approved by user and ingested, rejected=user rejected';

-- Back-fill existing completed rows as approved
UPDATE document_registry SET apa_approval_status = 'approved'
WHERE ingestion_status = 'completed' AND apa_approval_status = 'pending';

-- Migration 012: Enhanced Document Registry for Upload + APA Citation
-- Adds upload tracking, APA metadata, and source link fields

-- Enhance document_registry with upload tracking and APA metadata
ALTER TABLE document_registry
  ADD COLUMN IF NOT EXISTS file_path        VARCHAR(1000) DEFAULT '',
  ADD COLUMN IF NOT EXISTS file_size        BIGINT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS content_type     VARCHAR(100) DEFAULT '',
  ADD COLUMN IF NOT EXISTS upload_method    VARCHAR(20) DEFAULT 'minio',
  ADD COLUMN IF NOT EXISTS uploaded_by      VARCHAR(100) DEFAULT '',
  ADD COLUMN IF NOT EXISTS ingestion_status VARCHAR(20) DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS chunk_count      INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS error_message    TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS total_pages      INT DEFAULT 0,

  -- APA Metadata Fields
  ADD COLUMN IF NOT EXISTS apa_authors      TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_year         VARCHAR(10) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_publisher    VARCHAR(500) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_doi          VARCHAR(200) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_url          VARCHAR(1000) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_accessed     DATE,
  ADD COLUMN IF NOT EXISTS apa_edition      VARCHAR(100) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_volume       VARCHAR(50) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_pages        VARCHAR(50) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_type         VARCHAR(50) DEFAULT 'report',

  -- Source Link Tracking
  ADD COLUMN IF NOT EXISTS source_type      VARCHAR(20) DEFAULT 'internal',
  ADD COLUMN IF NOT EXISTS external_url     VARCHAR(2000) DEFAULT '',
  ADD COLUMN IF NOT EXISTS minio_path       VARCHAR(1000) DEFAULT '';

-- Indexes for listing and filtering
CREATE INDEX IF NOT EXISTS idx_doc_registry_status ON document_registry(ingestion_status);
CREATE INDEX IF NOT EXISTS idx_doc_registry_uploaded ON document_registry(uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_doc_registry_source_type ON document_registry(source_type);

-- Migration 010: Evidence & Citation tables for Citation & Evidence Agent
-- Creates evidence_registry and claim_evidence_link tables
-- Also enhances document_registry with citation metadata

-- Evidence registry — central store for all evidence items
CREATE TABLE IF NOT EXISTS evidence_registry (
    evidence_id     VARCHAR(20) PRIMARY KEY,
    session_id      VARCHAR(255),
    evidence_type   VARCHAR(20) NOT NULL CHECK (evidence_type IN ('document', 'database', 'api')),
    topic           VARCHAR(100) DEFAULT 'general',

    -- Source identification
    source_ref      VARCHAR(500) NOT NULL,
    title           VARCHAR(500),
    section_label   VARCHAR(200),
    page_ref        VARCHAR(50),
    chunk_id        VARCHAR(255),
    chunk_index     INTEGER,

    -- For database evidence
    query_signature VARCHAR(64),
    query_params    JSONB,

    -- Context
    geography_ref   VARCHAR(200),
    time_range_ref  VARCHAR(100),
    text_snippet    TEXT,

    -- Trust & provenance
    trust_level     VARCHAR(20) DEFAULT 'medium' CHECK (trust_level IN ('high', 'medium', 'low')),
    original_url    VARCHAR(1000),
    open_url        VARCHAR(1000),

    -- Tracking
    used_in_objects TEXT[] DEFAULT '{}',
    extracted_at    TIMESTAMP DEFAULT NOW(),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ev_session ON evidence_registry(session_id);
CREATE INDEX IF NOT EXISTS idx_ev_source ON evidence_registry(source_ref);
CREATE INDEX IF NOT EXISTS idx_ev_topic ON evidence_registry(topic);
CREATE INDEX IF NOT EXISTS idx_ev_query_sig ON evidence_registry(query_signature);

-- Claim-evidence link — maps claims to supporting evidence
CREATE TABLE IF NOT EXISTS claim_evidence_link (
    link_id             BIGSERIAL PRIMARY KEY,
    session_id          VARCHAR(255),
    claim_id            VARCHAR(20) NOT NULL,
    claim_text          TEXT,
    claim_type          VARCHAR(50),
    section_id          VARCHAR(100),
    object_type         VARCHAR(20) DEFAULT 'text',
    object_id           VARCHAR(100),

    evidence_id         VARCHAR(20) NOT NULL REFERENCES evidence_registry(evidence_id),
    support_level       VARCHAR(30) DEFAULT 'supported',
    evidence_strength   VARCHAR(20) DEFAULT 'moderate',
    confidence_note     TEXT,

    citation_code       VARCHAR(20),
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cel_session ON claim_evidence_link(session_id);
CREATE INDEX IF NOT EXISTS idx_cel_claim ON claim_evidence_link(claim_id);
CREATE INDEX IF NOT EXISTS idx_cel_evidence ON claim_evidence_link(evidence_id);
CREATE INDEX IF NOT EXISTS idx_cel_citation ON claim_evidence_link(citation_code);

-- Enhance document_registry with citation-related columns
ALTER TABLE document_registry ADD COLUMN IF NOT EXISTS file_path VARCHAR(1000);
ALTER TABLE document_registry ADD COLUMN IF NOT EXISTS total_pages INTEGER;
ALTER TABLE document_registry ADD COLUMN IF NOT EXISTS original_url VARCHAR(1000);
ALTER TABLE document_registry ADD COLUMN IF NOT EXISTS open_url VARCHAR(1000);

-- Note: document_chunks was dropped in migration 014 (ChromaDB era, replaced by pgvector).

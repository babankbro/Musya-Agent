-- Migration 011: Replace ChromaDB with pgvector (PostgreSQL-native vector search)
-- Requires PostgreSQL 15+ with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Document embeddings table (replaces ChromaDB musya_documents collection)
CREATE TABLE IF NOT EXISTS document_embeddings (
    id              VARCHAR(64) PRIMARY KEY,          -- MD5 hash of source::chunk_index
    collection      VARCHAR(100) NOT NULL DEFAULT 'musya_documents',
    document        TEXT NOT NULL,                    -- raw chunk text
    embedding       vector(3072),                     -- Google Gemini gemini-embedding-001 (3072-dim)
    
    -- Source metadata
    source          VARCHAR(500),                     -- original filename in MinIO
    title           VARCHAR(500),
    topic           VARCHAR(100),
    chunk_index     INTEGER DEFAULT -1,
    total_chunks    INTEGER DEFAULT 0,
    page_ref        VARCHAR(50),
    section_label   VARCHAR(200),
    total_pages     INTEGER DEFAULT 0,
    
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_de_collection  ON document_embeddings(collection);
CREATE INDEX IF NOT EXISTS idx_de_source      ON document_embeddings(source);
CREATE INDEX IF NOT EXISTS idx_de_topic       ON document_embeddings(topic);

-- Note: gemini-embedding-001 produces 3072-dim vectors.
-- pgvector HNSW and IVFFlat indexes are limited to 2000 dimensions.
-- For >2000-dim vectors, exact cosine search (sequential scan) is used automatically.
-- This is fast enough for document collections up to ~50K chunks.
-- If scaling beyond that, consider reducing embedding dimensions via output_dimensionality parameter.

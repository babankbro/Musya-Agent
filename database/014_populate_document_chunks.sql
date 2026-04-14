-- Migration 014: Drop obsolete document_chunks table
--
-- document_chunks was designed in the ChromaDB era (migration 002) as a
-- PostgreSQL mirror of chunks whose vectors lived in ChromaDB.
-- Since migration 011 replaced ChromaDB with pgvector, chunk text AND vectors
-- are both stored in document_embeddings.  document_chunks has been empty
-- (0 rows) and is no longer referenced by any ingest path.
--
-- The authoritative tables going forward are:
--   document_registry    — 1 row per document, APA metadata, ingestion status
--   document_embeddings  — N rows per document (one per chunk), text + vector

DROP TABLE IF EXISTS document_chunks CASCADE;

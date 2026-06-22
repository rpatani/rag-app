-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Tracks each source document and its ingestion status.
CREATE TABLE IF NOT EXISTS documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename      TEXT NOT NULL,
    source_path   TEXT NOT NULL UNIQUE,
    content_hash  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending | processing | completed | failed
    error_message TEXT,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Stores chunked text + embeddings.
-- NOTE: vector(384) matches the default local embedder (all-MiniLM-L6-v2).
-- If you switch EMBEDDER_BACKEND to one with a different dimension,
-- you must ALTER this column (see README "Swapping the embedding model").
CREATE TABLE IF NOT EXISTS doc_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    embedding   VECTOR(384) NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vector similarity index (cosine distance) for fast nearest-neighbor search.
CREATE INDEX IF NOT EXISTS doc_chunks_embedding_hnsw_idx
    ON doc_chunks USING hnsw (embedding vector_cosine_ops);

-- Speeds up "delete all chunks for this document" and joins.
CREATE INDEX IF NOT EXISTS doc_chunks_document_id_idx
    ON doc_chunks (document_id);

-- Speeds up metadata-based filtering (e.g. filter by source type, tags).
CREATE INDEX IF NOT EXISTS doc_chunks_metadata_gin_idx
    ON doc_chunks USING gin (metadata);

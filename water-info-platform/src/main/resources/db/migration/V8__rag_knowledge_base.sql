-- Knowledge base schema for AI RAG

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS kb_document (
    id              VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    title           VARCHAR(255) NOT NULL,
    source_type     VARCHAR(32) NOT NULL DEFAULT 'upload',
    source_uri      TEXT NOT NULL DEFAULT '',
    mime            VARCHAR(128) NOT NULL DEFAULT 'text/plain',
    lang            VARCHAR(32) NOT NULL DEFAULT 'zh-CN',
    version         INT NOT NULL DEFAULT 1,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    content_hash    VARCHAR(64) NOT NULL DEFAULT '',
    raw_text        TEXT NOT NULL DEFAULT '',
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    chunk_count     INT NOT NULL DEFAULT 0,
    file_size       BIGINT NOT NULL DEFAULT 0,
    embedding_model VARCHAR(128) NOT NULL DEFAULT '',
    created_by      VARCHAR(64) NOT NULL DEFAULT '',
    last_indexed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS kb_chunk (
    id           VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    document_id  VARCHAR(64) NOT NULL REFERENCES kb_document(id) ON DELETE CASCADE,
    chunk_index  INT NOT NULL,
    content      TEXT NOT NULL,
    token_count  INT NOT NULL DEFAULT 0,
    heading_path JSONB NOT NULL DEFAULT '[]'::jsonb,
    search_text  TEXT NOT NULL DEFAULT '',
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS kb_embedding (
    chunk_id   VARCHAR(64) PRIMARY KEY REFERENCES kb_chunk(id) ON DELETE CASCADE,
    model      VARCHAR(128) NOT NULL DEFAULT '',
    dimensions INT NOT NULL DEFAULT 0,
    embedding  vector NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_ingest_job (
    id          VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    document_id VARCHAR(64) NOT NULL REFERENCES kb_document(id) ON DELETE CASCADE,
    status      VARCHAR(32) NOT NULL DEFAULT 'pending',
    error       TEXT,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_kb_document_status_deleted
    ON kb_document(status, deleted, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_kb_document_hash
    ON kb_document(content_hash);

CREATE INDEX IF NOT EXISTS idx_kb_chunk_document
    ON kb_chunk(document_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_kb_chunk_search
    ON kb_chunk USING gin (to_tsvector('simple', search_text));

CREATE INDEX IF NOT EXISTS idx_kb_embedding_model_dims
    ON kb_embedding(model, dimensions);

CREATE INDEX IF NOT EXISTS idx_kb_embedding_hnsw
    ON kb_embedding USING hnsw (embedding vector_cosine_ops);

COMMIT;

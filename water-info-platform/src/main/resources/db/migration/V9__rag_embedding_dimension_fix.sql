-- Align kb_embedding to the configured 1024-dim deployment default so HNSW can be indexed.

BEGIN;

DROP INDEX IF EXISTS idx_kb_embedding_hnsw;

ALTER TABLE kb_embedding
    ALTER COLUMN embedding TYPE vector(1024)
    USING embedding::vector(1024);

CREATE INDEX IF NOT EXISTS idx_kb_embedding_hnsw
    ON kb_embedding USING hnsw (embedding vector_cosine_ops);

COMMIT;

"""Baseline schema: documents + doc_chunks with pgvector.

Idempotent (IF NOT EXISTS throughout) so it is safe to run against both a
fresh database and one already bootstrapped by db/init.sql. Existing
deployments can either run `alembic upgrade head` (no-op on the schema,
records the version) or `alembic stamp 0001`.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            filename      TEXT NOT NULL,
            source_path   TEXT NOT NULL UNIQUE,
            content_hash  TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            chunk_count   INTEGER NOT NULL DEFAULT 0,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS doc_chunks (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content     TEXT NOT NULL,
            embedding   VECTOR(384) NOT NULL,
            metadata    JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS doc_chunks_embedding_hnsw_idx"
        " ON doc_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS doc_chunks_document_id_idx ON doc_chunks (document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS doc_chunks_metadata_gin_idx ON doc_chunks USING gin (metadata)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS doc_chunks")
    op.execute("DROP TABLE IF EXISTS documents")

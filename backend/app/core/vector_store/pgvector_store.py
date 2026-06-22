from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.vector_store.base import VectorStore
from app.db.models import DocChunk
from app.models import ChunkRecord, ScoredChunk


class PgVectorStore(VectorStore):
    """Vector store backed by Postgres + the pgvector extension."""

    def __init__(self, db: Session):
        self.db = db

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return

        rows = [
            DocChunk(
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding=chunk.embedding,
                metadata_=chunk.metadata,
            )
            for chunk in chunks
        ]
        self.db.add_all(rows)
        self.db.commit()

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[ScoredChunk]:
        # cosine_distance() returns 0 for identical vectors and 2 for opposite
        # vectors; we convert it to a 0-1 "similarity" score for the UI.
        distance = DocChunk.embedding.cosine_distance(query_embedding)

        stmt = select(DocChunk, distance.label("distance")).order_by(distance).limit(top_k)

        if filters:
            for key, value in filters.items():
                stmt = stmt.where(DocChunk.metadata_[key].astext == str(value))

        results = self.db.execute(stmt).all()

        return [
            ScoredChunk(
                document_id=str(row.DocChunk.document_id),
                chunk_index=row.DocChunk.chunk_index,
                content=row.DocChunk.content,
                metadata=row.DocChunk.metadata_,
                score=1.0 - float(row.distance) / 2.0,
            )
            for row in results
        ]

    def delete_document(self, document_id: str) -> None:
        self.db.execute(delete(DocChunk).where(DocChunk.document_id == document_id))
        self.db.commit()

    def health_check(self) -> bool:
        try:
            self.db.execute(select(1))
            return True
        except Exception:
            return False

"""
VectorStore interface.

Every vector database backend (pgvector, Qdrant, Pinecone, ...) implements
this interface. Application code (ingestion pipeline, RAG pipeline, API
routes) depends ONLY on this interface, never on a specific backend - so the
backend can be swapped by changing config + the factory, with no changes to
calling code.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.models import ChunkRecord, ScoredChunk


class VectorStore(ABC):
    @abstractmethod
    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        """Insert (or replace) embedded chunks for a document."""
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[ScoredChunk]:
        """Return the top_k most similar chunks to the query embedding."""
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Remove all chunks belonging to a document (e.g. before re-ingesting it)."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the vector store is reachable and ready to serve queries."""
        raise NotImplementedError

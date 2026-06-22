from sqlalchemy.orm import Session

from app.config import Settings
from app.core.vector_store.base import VectorStore
from app.core.vector_store.pgvector_store import PgVectorStore


def get_vector_store(db: Session, settings: Settings) -> VectorStore:
    """
    Return a VectorStore implementation based on settings.vector_store_backend.

    To add a new backend (e.g. Qdrant):
      1. Implement VectorStore in core/vector_store/qdrant_store.py
      2. Add a branch here: if backend == "qdrant": return QdrantStore(...)
      3. Set VECTOR_STORE_BACKEND=qdrant in .env

    No other code (ingestion pipeline, RAG pipeline, API routes) changes.
    """
    backend = settings.vector_store_backend.lower()

    if backend == "pgvector":
        return PgVectorStore(db)

    raise ValueError(f"Unsupported vector store backend: {backend!r}")

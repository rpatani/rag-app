"""
Shared, framework-agnostic data structures.

These are the "currency" passed between the ingestion pipeline, vector store,
embedder, and RAG pipeline. Keeping them independent of SQLAlchemy / Postgres
specifics is what makes the VectorStore swappable.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkRecord:
    """A single chunk of text ready to be embedded and stored."""

    document_id: str
    chunk_index: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass
class ScoredChunk:
    """A chunk returned from a similarity search, with its relevance score."""

    document_id: str
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    score: float


@dataclass
class SourceCitation:
    """A simplified, user-facing reference to a retrieved chunk."""

    document_id: str
    filename: str
    chunk_index: int
    snippet: str
    score: float


@dataclass
class AnswerResult:
    """The final result returned to the API/UI for a user question."""

    answer: str
    sources: list[SourceCitation]

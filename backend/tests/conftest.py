"""
Shared fixtures.

The interface pattern (VectorStore/Embedder/LLM/Reranker base classes) is what
makes the app testable without Postgres, model downloads, or network access:
every heavy dependency is replaced by an in-memory fake implementing the same
interface, injected through FastAPI dependency overrides.
"""

import sys
from pathlib import Path
from typing import Any

import pytest

# Make `app` importable when running pytest from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.embeddings.base import Embedder  # noqa: E402
from app.core.llm.base import LLM  # noqa: E402
from app.core.reranker.base import Reranker  # noqa: E402
from app.core.vector_store.base import VectorStore  # noqa: E402
from app.models import ChunkRecord, ScoredChunk  # noqa: E402


class FakeEmbedder(Embedder):
    """Deterministic 4-dim embeddings based on text length."""

    dimension = 4

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        n = float(len(text) % 7 + 1)
        return [n, n / 2, n / 3, n / 4]


class FakeVectorStore(VectorStore):
    def __init__(self):
        self.chunks: list[ChunkRecord] = []
        self.deleted_document_ids: list[str] = []

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        self.chunks.extend(chunks)

    def search(self, query_embedding: list[float], top_k: int, filters: dict[str, Any] | None = None) -> list[ScoredChunk]:
        return [
            ScoredChunk(
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                content=c.content,
                metadata=c.metadata,
                score=0.9 - 0.1 * i,
            )
            for i, c in enumerate(self.chunks[:top_k])
        ]

    def delete_document(self, document_id: str) -> None:
        self.deleted_document_ids.append(document_id)
        self.chunks = [c for c in self.chunks if c.document_id != document_id]

    def health_check(self) -> bool:
        return True


class FakeReranker(Reranker):
    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int) -> list[ScoredChunk]:
        return chunks[:top_n]


class FakeLLM(LLM):
    def __init__(self, answer: str = "test answer"):
        self.answer = answer
        self.prompts: list[tuple[str, str]] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append((system_prompt, user_prompt))
        return self.answer

    def generate_stream(self, system_prompt: str, user_prompt: str):
        self.prompts.append((system_prompt, user_prompt))
        yield from self.answer.split(" ")


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture
def fake_vector_store():
    return FakeVectorStore()


@pytest.fixture
def fake_reranker():
    return FakeReranker()


@pytest.fixture
def fake_llm():
    return FakeLLM()

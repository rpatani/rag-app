from collections.abc import Iterator

from app.core.embeddings.base import Embedder
from app.core.llm.base import LLM
from app.core.reranker.base import Reranker
from app.core.vector_store.base import VectorStore
from app.models import AnswerResult, SourceCitation

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the "
    "provided context. If the context does not contain enough information "
    "to answer the question, say so clearly instead of guessing. "
    "When you use information from the context, refer to it naturally "
    "(e.g. 'according to the document...') but do not invent sources."
)

_NO_CONTEXT_REPLY = (
    "I couldn't find any relevant information in the knowledge base. "
    "Make sure documents have been ingested."
)


def _build_user_prompt(question: str, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(
        f"[Source {i + 1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
    )
    return (
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer the question using only the context above."
    )


class RAGPipeline:
    def __init__(
        self,
        vector_store: VectorStore,
        embedder: Embedder,
        llm: LLM,
        reranker: Reranker,
        top_k: int = 10,
        top_n: int = 3,
    ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.llm = llm
        self.reranker = reranker
        self.top_k = top_k   # candidates retrieved from vector store
        self.top_n = top_n   # chunks kept after reranking

    def _retrieve(self, question: str):
        query_embedding = self.embedder.embed_query(question)
        candidates = self.vector_store.search(query_embedding, top_k=self.top_k)
        return self.reranker.rerank(question, candidates, top_n=self.top_n)

    def answer(self, question: str) -> AnswerResult:
        reranked = self._retrieve(question)

        if not reranked:
            return AnswerResult(answer=_NO_CONTEXT_REPLY, sources=[])

        prompt = _build_user_prompt(question, [chunk.content for chunk in reranked])
        answer_text = self.llm.generate(SYSTEM_PROMPT, prompt)

        sources = [
            SourceCitation(
                document_id=chunk.document_id,
                filename=chunk.metadata.get("filename", "unknown"),
                chunk_index=chunk.chunk_index,
                snippet=chunk.content[:300],
                score=round(chunk.score, 4),
            )
            for chunk in reranked
        ]
        return AnswerResult(answer=answer_text, sources=sources)

    def answer_stream(self, question: str) -> Iterator[dict]:
        """Yield SSE-ready event dicts: token → sources → done."""
        reranked = self._retrieve(question)

        if not reranked:
            yield {"type": "token", "content": _NO_CONTEXT_REPLY}
            yield {"type": "done"}
            return

        prompt = _build_user_prompt(question, [chunk.content for chunk in reranked])

        for token in self.llm.generate_stream(SYSTEM_PROMPT, prompt):
            yield {"type": "token", "content": token}

        yield {
            "type": "sources",
            "sources": [
                {
                    "filename": chunk.metadata.get("filename", "unknown"),
                    "chunk_index": chunk.chunk_index,
                    "snippet": chunk.content[:300],
                    "score": round(chunk.score, 4),
                }
                for chunk in reranked
            ],
        }
        yield {"type": "done"}

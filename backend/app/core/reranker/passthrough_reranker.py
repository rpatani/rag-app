from app.core.reranker.base import Reranker
from app.models import ScoredChunk


class PassthroughReranker(Reranker):
    """No-op reranker — returns the top_n chunks by their vector similarity score.

    Used when RERANKER_BACKEND=none. Keeps the pipeline shape identical so
    application code never needs to branch on whether reranking is enabled.
    """

    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int) -> list[ScoredChunk]:
        return chunks[:top_n]

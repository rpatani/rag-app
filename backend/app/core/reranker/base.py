from abc import ABC, abstractmethod

from app.models import ScoredChunk


class Reranker(ABC):
    """Re-scores and prunes a candidate list of chunks against the original query.

    Sits between vector retrieval and prompt assembly. Retrieval fetches a
    wide candidate set (top_k); the reranker narrows it to top_n using a
    more expensive but more accurate cross-attention score.
    """

    @abstractmethod
    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int) -> list[ScoredChunk]:
        raise NotImplementedError

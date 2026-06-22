import math

from sentence_transformers import CrossEncoder

from app.core.reranker.base import Reranker
from app.models import ScoredChunk


class CrossEncoderReranker(Reranker):
    """Reranker backed by a sentence-transformers CrossEncoder model.

    The cross-encoder jointly encodes the (query, chunk) pair and produces a
    relevance logit, giving a much stronger signal than the asymmetric
    cosine similarity used during retrieval. Scores are sigmoid-normalised to
    [0, 1] for consistency with the vector similarity scores shown in the UI.

    Default model: cross-encoder/ms-marco-MiniLM-L-6-v2
      ~70 MB, CPU-friendly, trained on MS MARCO passage ranking.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int) -> list[ScoredChunk]:
        if not chunks:
            return []

        pairs = [[query, chunk.content] for chunk in chunks]
        raw_scores: list[float] = self._model.predict(pairs).tolist()

        ranked = sorted(
            zip(chunks, raw_scores),
            key=lambda x: x[1],
            reverse=True,
        )

        result = []
        for chunk, raw_score in ranked[:top_n]:
            normalised = 1.0 / (1.0 + math.exp(-raw_score))
            result.append(
                ScoredChunk(
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    metadata=chunk.metadata,
                    score=round(normalised, 4),
                )
            )
        return result

from sentence_transformers import SentenceTransformer

from app.core.embeddings.base import Embedder


class LocalEmbedder(Embedder):
    """
    Runs a small sentence-transformers model locally on CPU.

    Default model: all-MiniLM-L6-v2 (384 dimensions, ~80MB).
    The model is loaded once and cached for the lifetime of the process.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)
        self.dimension = self._model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self._model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return embedding.tolist()

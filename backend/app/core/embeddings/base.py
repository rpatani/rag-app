from abc import ABC, abstractmethod


class Embedder(ABC):
    """Converts text into vector embeddings. Implementations must report a fixed `dimension`."""

    dimension: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document chunks (used during ingestion)."""
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single user query (used at retrieval time)."""
        raise NotImplementedError

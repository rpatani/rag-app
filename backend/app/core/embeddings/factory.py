from functools import lru_cache

from app.config import get_settings
from app.core.embeddings.base import Embedder
from app.core.embeddings.local_embedder import LocalEmbedder
from app.core.embeddings.openai_embedder import OpenAIEmbedder


@lru_cache
def get_embedder() -> Embedder:
    """
    Return an Embedder based on settings.embedder_backend.

    Cached (no args) so the local model is only loaded into memory once per
    process. NOTE: changing the embedder's dimension requires a matching
    change to the `embedding` column in db/init.sql / db/models.py (see README).
    """
    settings = get_settings()
    backend = settings.embedder_backend.lower()

    if backend == "local":
        return LocalEmbedder(model_name=settings.local_embedding_model)

    if backend == "openai":
        return OpenAIEmbedder(api_key=settings.openai_api_key, model=settings.openai_embedding_model)

    raise ValueError(f"Unsupported embedder backend: {backend!r}")

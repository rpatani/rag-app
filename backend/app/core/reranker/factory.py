from functools import lru_cache

from app.config import get_settings
from app.core.reranker.base import Reranker


@lru_cache
def get_reranker() -> Reranker:
    """Return a Reranker based on settings.reranker_backend.

    Cached so the cross-encoder model is only loaded once per process.
    Concrete adapters are imported lazily so unused backends are never loaded.
    """
    settings = get_settings()
    backend = settings.reranker_backend.lower()

    if backend == "cross_encoder":
        from app.core.reranker.cross_encoder_reranker import CrossEncoderReranker
        return CrossEncoderReranker(model_name=settings.reranker_model)

    if backend == "none":
        from app.core.reranker.passthrough_reranker import PassthroughReranker
        return PassthroughReranker()

    raise ValueError(f"Unsupported reranker backend: {backend!r}")

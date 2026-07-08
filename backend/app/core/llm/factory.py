from functools import lru_cache

from app.config import get_settings
from app.core.llm.base import LLM


@lru_cache
def get_llm() -> LLM:
    """
    Return an LLM based on settings.llm_backend.

    To add a new provider (Anthropic, Azure OpenAI, ...), implement LLM in
    core/llm/<provider>_llm.py, add a branch here, and set LLM_BACKEND.
    Concrete adapters are imported lazily so unused backends are never loaded.
    """
    settings = get_settings()
    backend = settings.llm_backend.lower()

    if backend == "openai":
        from app.core.llm.openai_llm import OpenAILLM
        return OpenAILLM(api_key=settings.openai_api_key, model=settings.openai_model)

    if backend == "ollama":
        from app.core.llm.ollama_llm import OllamaLLM
        return OllamaLLM(base_url=settings.ollama_base_url, model=settings.ollama_model)

    raise ValueError(f"Unsupported LLM backend: {backend!r}")

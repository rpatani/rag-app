from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql+psycopg://user:password@localhost:5432/ragdb"

    # --- Vector store ---
    vector_store_backend: str = "pgvector"

    # --- Embeddings ---
    embedder_backend: str = "local"          # "local" | "openai"
    embedding_dim: int = 384
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_embedding_model: str = "text-embedding-3-small"

    # --- LLM ---
    llm_backend: str = "openai"               # "openai" | "ollama"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # --- Reranker ---
    reranker_backend: str = "cross_encoder"   # "cross_encoder" | "none"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_n: int = 3                   # chunks kept after reranking

    # --- Retrieval / chunking ---
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 10                           # candidates fetched before reranking

    # --- Ingestion ---
    documents_dir: str = "/data/documents"


@lru_cache
def get_settings() -> Settings:
    """Settings are cached so the embedding model etc. are only loaded once."""
    return Settings()

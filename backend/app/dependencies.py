from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.embeddings.base import Embedder
from app.core.embeddings.factory import get_embedder
from app.core.llm.base import LLM
from app.core.llm.factory import get_llm
from app.core.rag_pipeline import RAGPipeline
from app.core.reranker.base import Reranker
from app.core.reranker.factory import get_reranker
from app.core.vector_store.base import VectorStore
from app.core.vector_store.factory import get_vector_store
from app.db.session import get_db

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
LLMDep = Annotated[LLM, Depends(get_llm)]
RerankerDep = Annotated[Reranker, Depends(get_reranker)]


def get_vector_store_dep(db: DbDep, settings: SettingsDep) -> VectorStore:
    return get_vector_store(db, settings)


VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store_dep)]


def get_rag_pipeline(
    vector_store: VectorStoreDep,
    embedder: EmbedderDep,
    llm: LLMDep,
    reranker: RerankerDep,
    settings: SettingsDep,
) -> RAGPipeline:
    return RAGPipeline(
        vector_store=vector_store,
        embedder=embedder,
        llm=llm,
        reranker=reranker,
        top_k=settings.top_k,
        top_n=settings.reranker_top_n,
    )


RAGPipelineDep = Annotated[RAGPipeline, Depends(get_rag_pipeline)]

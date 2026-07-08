"""RAG pipeline orchestration with fake backends."""

from app.core.rag_pipeline import RAGPipeline
from app.models import ChunkRecord


def _pipeline(fake_vector_store, fake_embedder, fake_llm, fake_reranker, seed_chunks=3):
    for i in range(seed_chunks):
        fake_vector_store.upsert_chunks(
            [
                ChunkRecord(
                    document_id="doc1",
                    chunk_index=i,
                    content=f"chunk {i} content",
                    metadata={"filename": "test.pdf"},
                    embedding=[1.0, 2.0, 3.0, 4.0],
                )
            ]
        )
    return RAGPipeline(
        vector_store=fake_vector_store,
        embedder=fake_embedder,
        llm=fake_llm,
        reranker=fake_reranker,
        top_k=10,
        top_n=2,
    )


def test_answer_includes_sources(fake_vector_store, fake_embedder, fake_llm, fake_reranker):
    p = _pipeline(fake_vector_store, fake_embedder, fake_llm, fake_reranker)
    result = p.answer("what is chunk 0?")
    assert result.answer == "test answer"
    assert len(result.sources) == 2  # top_n
    assert result.sources[0].filename == "test.pdf"


def test_answer_with_empty_store_returns_no_context_reply(fake_vector_store, fake_embedder, fake_llm, fake_reranker):
    p = _pipeline(fake_vector_store, fake_embedder, fake_llm, fake_reranker, seed_chunks=0)
    result = p.answer("anything")
    assert "couldn't find" in result.answer.lower()
    assert result.sources == []
    assert fake_llm.prompts == []  # LLM must not be called without context


def test_context_chunks_reach_llm_prompt(fake_vector_store, fake_embedder, fake_llm, fake_reranker):
    p = _pipeline(fake_vector_store, fake_embedder, fake_llm, fake_reranker)
    p.answer("question")
    _, user_prompt = fake_llm.prompts[0]
    assert "chunk 0 content" in user_prompt
    assert "chunk 1 content" in user_prompt
    assert "chunk 2 content" not in user_prompt  # pruned by top_n=2


def test_stream_yields_tokens_sources_done(fake_vector_store, fake_embedder, fake_llm, fake_reranker):
    p = _pipeline(fake_vector_store, fake_embedder, fake_llm, fake_reranker)
    events = list(p.answer_stream("question"))
    types = [e["type"] for e in events]
    assert types[0] == "token"
    assert "sources" in types
    assert types[-1] == "done"

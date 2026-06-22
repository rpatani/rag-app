# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
# First time — copy env and start everything
cp .env.example .env          # then fill in OPENAI_API_KEY or switch to Ollama
docker compose up --build

# Subsequent runs
docker compose up -d

# Rebuild only the backend (after Python/frontend changes)
docker compose up -d --build backend

# Wipe the database volume and re-ingest from scratch (required after changing embedding model)
docker compose down -v && docker compose up --build
```

The UI is at **http://localhost:8000**. FastAPI's OpenAPI UI is at **http://localhost:8000/docs**.

## Backend development (without Docker)

```bash
cd backend
pip install -r requirements.txt
DATABASE_URL=postgresql+psycopg://raguser:ragpassword@localhost:5432/ragdb \
  uvicorn app.main:app --reload --port 8000
```

There are no tests yet. Smoke-test the key routes:

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/documents/ingest
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" -d '{"question": "..."}'
# Streaming variant (SSE):
curl -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" -d '{"question": "..."}' --no-buffer
```

## Architecture

```
documents/ ──> ingestion pipeline ──> embeddings ──> pgvector (Postgres)
                                                            │
web UI ──> FastAPI ──> RAG pipeline ──> retriever ─────────┘
                              │
                              └──> LLM ──> streamed tokens + citations ──> web UI
```

### The interface pattern (most important concept)

Three domain capabilities — vector store, embedder, LLM — each have:
- `app/core/<domain>/base.py` — abstract base class (the contract)
- `app/core/<domain>/factory.py` — reads `Settings` and returns the right concrete class
- Concrete adapters alongside (`pgvector_store.py`, `local_embedder.py`, `openai_llm.py`, `ollama_llm.py`, …)

**Application code (`ingestion/pipeline.py`, `core/rag_pipeline.py`, `api/`) depends only on these base classes, never on concrete adapters.** To add a new backend: implement the base class, add a branch to the factory, change one env var.

### Data flow

1. **Ingestion** (`app/ingestion/pipeline.py`): file → `loaders.py` (text extraction) → `chunking.py` (fixed-size overlap splitter) → `Embedder.embed_documents()` → `VectorStore.upsert_chunks()`. Each file is tracked by content hash in the `documents` table; unchanged files are skipped.

2. **Query** (`app/core/rag_pipeline.py`): question → `Embedder.embed_query()` → `VectorStore.search()` (cosine similarity, top-K candidates) → `Reranker.rerank()` (cross-encoder, narrows to top-N) → prompt assembly → `LLM.generate_stream()` → SSE token stream to browser, sources appended at end.

3. **Streaming** (`app/api/routes_query.py`): `answer_stream()` runs in a daemon thread; events are bridged to the async event loop via `asyncio.Queue` and yielded as SSE (`data: {...}\n\n`). Event types: `token`, `sources`, `done`, `error`.

### Shared data types (`app/models.py`)

Framework-agnostic dataclasses that flow between layers:
- `ChunkRecord` — chunk ready for embedding/storage
- `ScoredChunk` — chunk returned from similarity search
- `SourceCitation` — user-facing citation
- `AnswerResult` — final answer + citations (non-streaming path)

### Database schema (`db/init.sql`)

Two tables: `documents` (metadata + status + content hash) and `doc_chunks` (text + `vector(384)` embedding + JSONB metadata). HNSW index on the embedding column for ANN search; GIN index on metadata for filtered search.

### Key constraint: embedding dimension

`vector(384)` in `db/init.sql` and `Vector(384)` in `app/db/models.py` must match `EMBEDDING_DIM` in `.env`. Changing the embedding model requires updating both schema locations **and** dropping and recreating the database volume (`docker compose down -v`).

## Configuration

All config is in `.env` / `app/config.py` (pydantic-settings, cached via `@lru_cache`):

| Variable | Effect |
|---|---|
| `EMBEDDER_BACKEND` | `local` (all-MiniLM-L6-v2, 384 dims) or `openai` (text-embedding-3-small, 1536 dims) |
| `LLM_BACKEND` | `openai` or `ollama` |
| `OLLAMA_MODEL` | Model name; thinking models (e.g. `qwen3.5`) must have `"think": False` set in `ollama_llm.py` — already done |
| `OLLAMA_BASE_URL` | Use `http://host.docker.internal:11434` when Ollama runs on the host |
| `RERANKER_BACKEND` | `cross_encoder` (local, CPU) or `none` (passthrough) |
| `RERANKER_MODEL` | Cross-encoder model name; default `cross-encoder/ms-marco-MiniLM-L-6-v2` (~70 MB) |
| `RERANKER_TOP_N` | Chunks passed to the LLM after reranking (default 3) |
| `TOP_K` | Candidates fetched from vector store before reranking (default 10); should be > `RERANKER_TOP_N` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Text splitter parameters |
| `DOCUMENTS_DIR` | `/data/documents` inside the container; the `documents/` folder is bind-mounted there |

## File upload

Documents can be uploaded via the UI (drag-and-drop) or the API:

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@/path/to/doc.pdf"
# Delete a document:
curl -X DELETE http://localhost:8000/api/documents/doc.pdf
```

Supported types: `.pdf`, `.docx`, `.txt`, `.md`. Max 50 MB per file. Upload auto-ingests immediately.

# RAG Knowledge Assistant

A small but production-shaped Retrieval-Augmented Generation (RAG) application:
a documents folder, an ingestion pipeline, a Postgres + pgvector vector store,
an LLM, a FastAPI backend, and a simple web UI.

## Architecture

```
documents/ ──> ingestion pipeline ──> embeddings ──> pgvector (Postgres)
                                                            │
web UI ──> FastAPI ──> RAG pipeline ──> retriever ─────────┘
                              │
                              └──> LLM ──> answer + citations ──> web UI
```

Key design decision: the **vector store, embedder, and LLM are all behind
small interfaces** (`app/core/vector_store/base.py`,
`app/core/embeddings/base.py`, `app/core/llm/base.py`). Application code
(ingestion, RAG pipeline, API routes) only depends on these interfaces, never
on pgvector/OpenAI/etc. directly. Swapping an implementation means:

1. Write a new class implementing the interface.
2. Add a branch to the corresponding `factory.py`.
3. Change one env var.

No changes to the ingestion pipeline, RAG pipeline, or API routes are needed.

## Quick start

1. Copy the example environment file and fill in your OpenAI API key (or
   switch to Ollama - see below):

   ```bash
   cp .env.example .env
   ```

2. Start everything:

   ```bash
   docker compose up --build
   ```

3. Open the UI at <http://localhost:8000>.

4. Click **Run ingestion** to load the sample documents in `documents/`
   into the vector store. (You can also drop your own PDF/DOCX/TXT/MD files
   into that folder before running ingestion.)

5. Ask a question, e.g. *"How much can I spend on hotels when traveling?"*
   The answer will include expandable source citations from the ingested
   documents.

API docs are available at <http://localhost:8000/docs> (FastAPI's automatic
OpenAPI UI).

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `VECTOR_STORE_BACKEND` | Currently `pgvector`. See "Swapping the vector store" below. |
| `EMBEDDER_BACKEND` | `local` (sentence-transformers, free, CPU) or `openai`. |
| `EMBEDDING_DIM` | Must match the embedder's output dimension and the `vector(N)` column in `db/init.sql`. |
| `LLM_BACKEND` | `openai` or `ollama`. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Controls the text splitter in `app/core/chunking.py`. |
| `TOP_K` | Number of chunks retrieved per query. |

## Swapping the embedding model

The default (`local`, all-MiniLM-L6-v2) produces 384-dimensional vectors,
matching `vector(384)` in `db/init.sql` and `Vector(384)` in
`app/db/models.py`.

To switch to `openai` (`text-embedding-3-small`, 1536 dims):

1. Set `EMBEDDER_BACKEND=openai` and `OPENAI_API_KEY=...` in `.env`.
2. Update both `vector(384)` in `db/init.sql` and `Vector(384)` in
   `app/db/models.py` to `vector(1536)` / `Vector(1536)`.
3. Re-create the database volume (`docker compose down -v`) and re-ingest,
   since existing embeddings are not compatible with the new dimension.

This is a real production consideration, not just a quirk of this demo -
any vector database requires a fixed dimension per collection/table, so
changing embedding models always means a migration.

## Swapping the LLM

Set `LLM_BACKEND=ollama`, run [Ollama](https://ollama.com) locally, pull a
model (`ollama pull llama3.1`), and make sure `OLLAMA_BASE_URL` points to it
(`http://host.docker.internal:11434` from inside Docker on Mac/Windows).
No code changes needed - `app/core/llm/factory.py` already has an
`OllamaLLM` implementation.

## Swapping the vector store

This is the scenario the abstraction was built for. To add, say, Qdrant:

1. Create `app/core/vector_store/qdrant_store.py` implementing
   `VectorStore` (`upsert_chunks`, `search`, `delete_document`,
   `health_check`) using the Qdrant Python client.
2. Add a branch in `app/core/vector_store/factory.py`:
   ```python
   if backend == "qdrant":
       return QdrantStore(...)
   ```
3. Set `VECTOR_STORE_BACKEND=qdrant` in `.env` and add a Qdrant service to
   `docker-compose.yml`.

`app/ingestion/pipeline.py`, `app/core/rag_pipeline.py`, and the API routes
do not change.

## Project structure

```
docker-compose.yml         Postgres (pgvector) + backend
db/init.sql                 Schema: documents, doc_chunks (+ HNSW index)
backend/app/
  config.py                 Settings (env-driven)
  main.py                    FastAPI app, mounts API + frontend
  models.py                  Shared dataclasses (ChunkRecord, ScoredChunk, ...)
  dependencies.py             FastAPI dependency wiring
  db/
    models.py                 SQLAlchemy ORM models
    session.py                 Engine/session factory
  core/
    chunking.py                Text splitter
    rag_pipeline.py            Retrieval + prompt + generation
    vector_store/              VectorStore interface + pgvector adapter + factory
    embeddings/                Embedder interface + local/openai adapters + factory
    llm/                       LLM interface + openai/ollama adapters + factory
  ingestion/
    loaders.py                  PDF/DOCX/TXT/MD text extraction
    pipeline.py                  Ingestion orchestration
  api/
    routes_query.py             POST /api/query
    routes_documents.py          GET/POST /api/documents
    routes_health.py             GET /api/health
frontend/                    Plain HTML/CSS/JS chat UI
documents/                  Source documents (sample policy docs included)
```

## What's intentionally simple (and what production would add next)

This is a learning-oriented but realistically-shaped baseline. A few things
deliberately left out, with pointers on what you'd add for a larger
deployment:

- **Ingestion is synchronous** (triggered via API call). A larger system
  would run it as a background worker (Celery/RQ) or scheduled job, and/or
  watch the folder for changes.
- **No reranking step.** After vector search, a cross-encoder reranker
  (e.g. `bge-reranker`) is commonly added before the LLM step to improve
  precision.
- **No authentication.** Add an API key or OAuth layer in front of FastAPI
  for any non-local deployment.
- **No caching.** Repeated identical queries currently re-embed and re-call
  the LLM; Redis is a common addition for caching embeddings/answers.
- **No observability.** Structured logging, request tracing, and retrieval
  evaluation (does the right chunk get retrieved?) are the next things
  worth adding once the core loop works.

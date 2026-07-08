"""API integration tests: full FastAPI app with fake backends via dependency
overrides. Covers auth on real routes, query, retrieve, upload validation,
path traversal defenses, and the async upload flow."""

import io
import time

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.rag_pipeline import RAGPipeline
from app.dependencies import get_rag_pipeline
from app.models import ChunkRecord
from tests.conftest import FakeEmbedder, FakeLLM, FakeReranker, FakeVectorStore

API_KEY = "test-api-key-42"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_API_KEY", API_KEY)
    monkeypatch.setenv("DOCUMENTS_DIR", str(tmp_path / "docs"))
    get_settings.cache_clear()

    from app.main import app  # import after env is set

    store = FakeVectorStore()
    store.upsert_chunks(
        [
            ChunkRecord(
                document_id="d1",
                chunk_index=0,
                content="the expense limit is $50",
                metadata={"filename": "policy.md"},
                embedding=[1, 2, 3, 4],
            )
        ]
    )
    pipeline = RAGPipeline(
        vector_store=store,
        embedder=FakeEmbedder(),
        llm=FakeLLM(answer="the limit is $50"),
        reranker=FakeReranker(),
        top_k=10,
        top_n=3,
    )
    app.dependency_overrides[get_rag_pipeline] = lambda: pipeline

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _auth():
    return {"X-API-Key": API_KEY}


# ── Auth on real routes ──────────────────────────────────────────────────────

def test_query_requires_auth(client):
    assert client.post("/api/query", json={"question": "hi"}).status_code == 401


def test_health_is_open(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "disk_free_gb" in body and "pending_jobs" in body


# ── Query paths ──────────────────────────────────────────────────────────────

def test_query_returns_answer_and_sources(client):
    r = client.post("/api/query", json={"question": "what is the expense limit?"}, headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "the limit is $50"
    assert body["sources"][0]["filename"] == "policy.md"


def test_retrieve_returns_chunks_without_llm(client):
    r = client.post("/api/retrieve", json={"query": "expense limit"}, headers=_auth())
    assert r.status_code == 200
    chunks = r.json()["chunks"]
    assert chunks and chunks[0]["content"] == "the expense limit is $50"


def test_query_stream_emits_sse(client):
    with client.stream(
        "POST", "/api/query/stream", json={"question": "limit?"}, headers=_auth()
    ) as r:
        assert r.status_code == 200
        payload = "".join(r.iter_text())
    assert 'data: {"type": "token"' in payload
    assert '"type": "done"' in payload


# ── Upload validation & security ─────────────────────────────────────────────

def test_upload_rejects_unsupported_type(client):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        headers=_auth(),
    )
    assert r.status_code == 422


def test_upload_rejects_oversized_file(client):
    big = io.BytesIO(b"x" * (51 * 1024 * 1024))
    r = client.post(
        "/api/documents/upload",
        files={"file": ("big.txt", big, "text/plain")},
        headers=_auth(),
    )
    assert r.status_code == 413


def test_upload_path_traversal_is_neutralized(client, tmp_path, monkeypatch):
    """A hostile filename must not escape the documents dir."""
    monkeypatch.setattr("app.api.routes_documents.ingest_path_job", lambda p: None)
    monkeypatch.setattr("app.api.routes_documents.mark_document_pending", lambda db, p: None)
    r = client.post(
        "/api/documents/upload",
        files={"file": ("../../outside.txt", io.BytesIO(b"attack"), "text/plain")},
        headers=_auth(),
    )
    # Either rejected outright or flattened to basename inside docs dir.
    assert r.status_code in (202, 400)
    assert not (tmp_path / "outside.txt").exists()  # never lands outside docs dir


def test_upload_queues_and_returns_202(client, monkeypatch):
    """Upload returns immediately with 'queued'; ingestion happens in background."""
    processed = []
    monkeypatch.setattr(
        "app.api.routes_documents.ingest_path_job", lambda p: processed.append(p)
    )
    monkeypatch.setattr(
        "app.api.routes_documents.mark_document_pending", lambda db, p: None
    )

    r = client.post(
        "/api/documents/upload",
        files={"file": ("note.txt", io.BytesIO(b"hello world"), "text/plain")},
        headers=_auth(),
    )
    assert r.status_code == 202
    assert r.json()["status"] == "queued"

    deadline = time.time() + 5
    while time.time() < deadline and not processed:
        time.sleep(0.02)
    assert len(processed) == 1 and processed[0].endswith("note.txt")


def test_request_id_header_present(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Request-ID")

"""
End-to-end simulation against a real Postgres + pgvector instance.

Runs only when E2E_DATABASE_URL is set (scripts/run_e2e.sh starts a throwaway
container, applies the Alembic baseline, runs this, and tears down).

What is real here: Postgres, pgvector cosine search, the Alembic-created
schema, the ingestion pipeline (hashing, chunking, status transitions), the
job queue, auth middleware, and every API route.
What is fake: the embedder (deterministic 384-dim vectors) and the LLM —
so the run needs no models and no network.
"""

import io
import os
import time

import pytest

E2E_URL = os.environ.get("E2E_DATABASE_URL")

pytestmark = pytest.mark.skipif(not E2E_URL, reason="E2E_DATABASE_URL not set")

API_KEY = "e2e-test-key"


class FakeEmbedder384:
    dimension = 384

    def _vec(self, text: str) -> list[float]:
        # Deterministic, content-sensitive vector: cosine-similar for
        # overlapping vocabulary, dissimilar otherwise.
        vec = [0.0] * 384
        for token in text.lower().split():
            vec[hash(token) % 384] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    docs_dir = tmp_path_factory.mktemp("docs")
    os.environ["DATABASE_URL"] = E2E_URL
    os.environ["APP_API_KEY"] = API_KEY
    os.environ["DOCUMENTS_DIR"] = str(docs_dir)
    os.environ["RERANKER_BACKEND"] = "none"

    from app.config import get_settings

    get_settings.cache_clear()

    import app.core.embeddings.factory as embedder_factory
    from fastapi.testclient import TestClient

    fake = FakeEmbedder384()

    # Patch at the factory level so BOTH the request path and the job-queue
    # worker (which builds its own adapters) get the fake.
    original = embedder_factory.get_embedder
    embedder_factory.get_embedder = lambda: fake

    import app.dependencies as deps_module

    from app.main import app

    # dependencies.py binds get_embedder at import time; rebind.
    app.dependency_overrides[deps_module.get_embedder] = lambda: fake

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    embedder_factory.get_embedder = original


def _auth():
    return {"X-API-Key": API_KEY}


def _wait_for_status(client, filename, wanted, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = client.get("/api/documents", headers=_auth()).json()
        doc = next((d for d in docs if d["filename"] == filename), None)
        if doc and doc["status"] == wanted:
            return doc
        if doc and doc["status"] == "failed":
            pytest.fail(f"Ingestion failed: {doc['error_message']}")
        time.sleep(0.25)
    pytest.fail(f"Timed out waiting for {filename} to reach {wanted}")


def test_full_upload_ingest_query_cycle(client):
    # 1. Upload a document → 202 queued
    content = (
        "The office expense reimbursement limit is fifty dollars per meal. "
        "Receipts must be submitted within thirty days of purchase. "
        "Travel bookings require manager approval in advance."
    )
    r = client.post(
        "/api/documents/upload",
        files={"file": ("expense_policy.txt", io.BytesIO(content.encode()), "text/plain")},
        headers=_auth(),
    )
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "queued"

    # 2. Background job ingests it (status pending/processing → completed)
    doc = _wait_for_status(client, "expense_policy.txt", "completed")
    assert doc["chunk_count"] >= 1

    # 3. Retrieval finds the right chunk via real pgvector cosine search
    r = client.post(
        "/api/retrieve",
        json={"query": "expense reimbursement limit meal"},
        headers=_auth(),
    )
    assert r.status_code == 200
    chunks = r.json()["chunks"]
    assert chunks, "retrieval returned nothing"
    assert "fifty dollars" in chunks[0]["content"]

    # 4. Re-upload identical content → ingestion skips (hash unchanged) or completes
    r = client.post(
        "/api/documents/upload",
        files={"file": ("expense_policy.txt", io.BytesIO(content.encode()), "text/plain")},
        headers=_auth(),
    )
    assert r.status_code == 202
    _wait_for_status(client, "expense_policy.txt", "completed")

    # 5. Delete → row and file gone
    r = client.delete("/api/documents/expense_policy.txt", headers=_auth())
    assert r.status_code == 204
    docs = client.get("/api/documents", headers=_auth()).json()
    assert all(d["filename"] != "expense_policy.txt" for d in docs)


def test_unauthenticated_requests_rejected(client):
    assert client.post("/api/query", json={"question": "x"}).status_code == 401
    assert client.get("/api/documents").status_code == 401


def test_health_reports_real_db(client):
    body = client.get("/api/health").json()
    assert body["vector_store_ok"] is True
    assert body["documents_dir_ok"] is True

"""API-key auth: enforced when configured, disabled when not, timing-safe path."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi import Depends

from app.config import get_settings
from app.core.auth import require_api_key


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_api_key)])
    def protected():
        return {"ok": True}

    return TestClient(app)


def _set_key(monkeypatch, value: str):
    monkeypatch.setenv("APP_API_KEY", value)
    get_settings.cache_clear()


def test_rejects_missing_key(client, monkeypatch):
    _set_key(monkeypatch, "secret-key-123")
    assert client.get("/protected").status_code == 401


def test_rejects_wrong_key(client, monkeypatch):
    _set_key(monkeypatch, "secret-key-123")
    assert client.get("/protected", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/protected", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_accepts_bearer_header(client, monkeypatch):
    _set_key(monkeypatch, "secret-key-123")
    r = client.get("/protected", headers={"Authorization": "Bearer secret-key-123"})
    assert r.status_code == 200


def test_accepts_x_api_key_header(client, monkeypatch):
    _set_key(monkeypatch, "secret-key-123")
    r = client.get("/protected", headers={"X-API-Key": "secret-key-123"})
    assert r.status_code == 200


def test_auth_disabled_when_key_unset(client, monkeypatch):
    _set_key(monkeypatch, "")
    assert client.get("/protected").status_code == 200


def test_partial_key_rejected(client, monkeypatch):
    """A prefix of the real key must not pass (compare_digest, not startswith)."""
    _set_key(monkeypatch, "secret-key-123")
    assert client.get("/protected", headers={"X-API-Key": "secret-key"}).status_code == 401

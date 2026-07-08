"""DocumentSource adapters: local directory listing/filtering, S3 via stubbed client."""

from pathlib import Path

from app.core.document_source.local_source import LocalDirSource
from app.core.document_source.s3_source import S3Source

EXT = {".pdf", ".txt", ".md"}


# ── LocalDirSource ───────────────────────────────────────────────────────────

def test_local_lists_only_supported_files(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.exe").write_text("nope")
    (tmp_path / "c.PDF").write_text("pdf")  # extension check is case-insensitive
    (tmp_path / "subdir").mkdir()

    docs = LocalDirSource(str(tmp_path), EXT).list_documents()
    names = [d.name for d in docs]
    assert names == ["a.txt", "c.PDF"]
    assert all(d.version for d in docs)


def test_local_missing_directory_returns_empty():
    assert LocalDirSource("/nonexistent/dir", EXT).list_documents() == []


def test_local_fetch_returns_original_path_and_cleanup_preserves_it(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    source = LocalDirSource(str(tmp_path), EXT)
    doc = source.list_documents()[0]

    local = source.fetch(doc)
    assert local == f
    source.cleanup(doc, local)
    assert f.exists()  # local source must never delete originals


def test_local_version_changes_when_file_changes(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("v1")
    source = LocalDirSource(str(tmp_path), EXT)
    v1 = source.list_documents()[0].version
    f.write_text("v2 with more bytes")
    v2 = source.list_documents()[0].version
    assert v1 != v2


# ── S3Source (stubbed client — no network) ───────────────────────────────────

class StubS3Client:
    """Minimal stand-in for boto3 S3 client."""

    def __init__(self, objects: list[dict], payload: bytes = b"content"):
        self._objects = objects
        self._payload = payload
        self.downloads: list[tuple[str, str, str]] = []

    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        objects = self._objects

        class _Paginator:
            def paginate(self, Bucket: str, Prefix: str):
                yield {"Contents": objects}

        return _Paginator()

    def download_file(self, bucket: str, key: str, filename: str):
        self.downloads.append((bucket, key, filename))
        Path(filename).write_bytes(self._payload)


def test_s3_requires_bucket():
    import pytest

    with pytest.raises(ValueError):
        S3Source(bucket="", prefix="", extensions=EXT)


def test_s3_lists_and_filters(tmp_path: Path):
    client = StubS3Client(
        [
            {"Key": "docs/a.pdf", "Size": 10, "ETag": '"abc123"'},
            {"Key": "docs/b.exe", "Size": 20, "ETag": '"def456"'},
            {"Key": "docs/", "Size": 0, "ETag": '"dir"'},  # folder marker
        ]
    )
    source = S3Source(bucket="test-bucket", prefix="docs/", extensions=EXT, client=client)
    docs = source.list_documents()
    assert [d.name for d in docs] == ["a.pdf"]
    assert docs[0].uri == "s3://test-bucket/docs/a.pdf"
    assert docs[0].version == "abc123"


def test_s3_fetch_downloads_to_temp_and_cleanup_removes(tmp_path: Path):
    client = StubS3Client([{"Key": "docs/a.pdf", "Size": 10, "ETag": '"abc"'}])
    source = S3Source(bucket="test-bucket", prefix="docs/", extensions=EXT, client=client)
    doc = source.list_documents()[0]

    local = source.fetch(doc)
    assert local.exists()
    assert local.read_bytes() == b"content"
    assert client.downloads[0][:2] == ("test-bucket", "docs/a.pdf")

    source.cleanup(doc, local)
    assert not local.exists()


def test_s3_hostile_key_cannot_escape_temp_dir():
    """A key with path traversal components must be flattened to its basename."""
    client = StubS3Client([{"Key": "docs/../../etc/passwd.txt", "Size": 5, "ETag": '"x"'}])
    source = S3Source(bucket="b", prefix="", extensions=EXT, client=client)
    docs = source.list_documents()
    assert docs[0].name == "passwd.txt"

    local = source.fetch(docs[0])
    # The local file must be inside the temp dir, named by basename only.
    assert local.name == "passwd.txt"
    assert "rag_s3_" in str(local.parent)
    source.cleanup(docs[0], local)

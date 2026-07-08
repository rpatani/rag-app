"""Chunking behavior and text loaders (txt/md paths; OCR paths need tesseract)."""

from pathlib import Path

import pytest

from app.core.chunking import chunk_text
from app.ingestion.loaders import SUPPORTED_EXTENSIONS, load_text


def test_chunk_respects_size():
    text = " ".join(f"Sentence number {i}." for i in range(200))
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert all(len(c) <= 120 for c in chunks)  # size + overlap tolerance
    assert len(chunks) > 1


def test_chunk_overlap_carries_context():
    text = ". ".join(f"Sentence {i}" for i in range(50)) + "."
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=30)
    for prev, nxt in zip(chunks, chunks[1:]):
        # The start of each chunk should repeat the tail of the previous one.
        assert nxt[:10] in prev or prev[-30:][:10] in nxt


def test_chunk_empty_text():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_long_sentence_hard_split():
    text = "x" * 2500
    chunks = chunk_text(text, chunk_size=800, chunk_overlap=120)
    assert all(len(c) <= 800 for c in chunks)
    assert "".join(chunks) == text


def test_load_txt_and_md(tmp_path: Path):
    f = tmp_path / "note.txt"
    f.write_text("hello world", encoding="utf-8")
    assert load_text(f) == "hello world"

    m = tmp_path / "note.md"
    m.write_text("# Title\nbody", encoding="utf-8")
    assert "Title" in load_text(m)


def test_load_rejects_unsupported_type(tmp_path: Path):
    f = tmp_path / "evil.exe"
    f.write_bytes(b"MZ")
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_text(f)


def test_supported_extensions_are_lowercase_with_dots():
    assert all(e.startswith(".") and e == e.lower() for e in SUPPORTED_EXTENSIONS)

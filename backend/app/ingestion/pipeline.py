import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.chunking import chunk_text
from app.core.embeddings.base import Embedder
from app.core.vector_store.base import VectorStore
from app.db.models import Document
from app.ingestion.loaders import SUPPORTED_EXTENSIONS, load_text
from app.models import ChunkRecord


@dataclass
class IngestResult:
    filename: str
    status: str
    chunk_count: int = 0
    error: str | None = None


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest_documents(db: Session, vector_store: VectorStore, embedder: Embedder, settings: Settings) -> list[IngestResult]:
    """
    Scan settings.documents_dir for supported files and (re)ingest any that
    are new or have changed since the last run (based on content hash).
    Already-ingested, unchanged files are skipped.
    """
    docs_dir = Path(settings.documents_dir)
    results: list[IngestResult] = []

    if not docs_dir.exists():
        return results

    for path in sorted(docs_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        results.append(_ingest_one(db, vector_store, embedder, settings, path))

    return results


def _ingest_one(db: Session, vector_store: VectorStore, embedder: Embedder, settings: Settings, path: Path) -> IngestResult:
    content_hash = _hash_file(path)
    source_path = str(path)

    existing = db.execute(select(Document).where(Document.source_path == source_path)).scalar_one_or_none()

    if existing and existing.content_hash == content_hash and existing.status == "completed":
        return IngestResult(filename=path.name, status="skipped (unchanged)", chunk_count=existing.chunk_count)

    if existing:
        document = existing
        document.content_hash = content_hash
        document.status = "processing"
        document.error_message = None
        vector_store.delete_document(str(document.id))
    else:
        document = Document(filename=path.name, source_path=source_path, content_hash=content_hash, status="processing")
        db.add(document)

    db.commit()
    db.refresh(document)

    try:
        text = load_text(path)
        pieces = chunk_text(text, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)

        if not pieces:
            document.status = "completed"
            document.chunk_count = 0
            db.commit()
            return IngestResult(filename=path.name, status="completed (no text found)", chunk_count=0)

        embeddings = embedder.embed_documents(pieces)

        chunk_records = [
            ChunkRecord(
                document_id=str(document.id),
                chunk_index=i,
                content=piece,
                metadata={"filename": document.filename, "source_path": source_path},
                embedding=embedding,
            )
            for i, (piece, embedding) in enumerate(zip(pieces, embeddings))
        ]

        vector_store.upsert_chunks(chunk_records)

        document.status = "completed"
        document.chunk_count = len(chunk_records)
        db.commit()

        return IngestResult(filename=path.name, status="completed", chunk_count=len(chunk_records))

    except Exception as exc:  # noqa: BLE001 - we want to record any failure and continue
        db.rollback()
        document.status = "failed"
        document.error_message = str(exc)
        db.commit()
        return IngestResult(filename=path.name, status="failed", error=str(exc))

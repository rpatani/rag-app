import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
from app.core.chunking import chunk_text
from app.core.embeddings.base import Embedder
from app.core.vector_store.base import VectorStore
from app.db.models import Document
from app.ingestion.loaders import load_text
from app.models import ChunkRecord


@dataclass
class IngestResult:
    filename: str
    status: str
    chunk_count: int = 0
    error: str | None = None


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest_documents(
    db: Session,
    vector_store: VectorStore,
    embedder: Embedder,
    settings: Settings,
    source: "DocumentSource | None" = None,
) -> list[IngestResult]:
    """
    Enumerate documents from the configured DocumentSource and (re)ingest any
    that are new or have changed since the last run (based on content hash).
    Already-ingested, unchanged files are skipped.
    """
    from app.core.document_source.factory import get_document_source

    if source is None:
        source = get_document_source(settings)

    results: list[IngestResult] = []
    for sdoc in source.list_documents():
        local_path = source.fetch(sdoc)
        try:
            results.append(
                _ingest_one(db, vector_store, embedder, settings, local_path, source_uri=sdoc.uri)
            )
        finally:
            source.cleanup(sdoc, local_path)

    return results


def _ingest_one(
    db: Session,
    vector_store: VectorStore,
    embedder: Embedder,
    settings: Settings,
    path: Path,
    source_uri: str | None = None,
) -> IngestResult:
    content_hash = _hash_file(path)
    source_path = source_uri or str(path)

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


# ── Background-job entry points ──────────────────────────────────────────────
# These are self-contained: they open (and close) their own DB session and
# build their own adapters, because they run on the job-queue worker thread
# outside any HTTP request context.


def mark_document_pending(db: Session, path: Path) -> None:
    """Create or reset the document row so the UI shows 'pending' immediately."""
    existing = db.execute(
        select(Document).where(Document.source_path == str(path))
    ).scalar_one_or_none()

    if existing:
        existing.status = "pending"
        existing.error_message = None
    else:
        db.add(Document(filename=path.name, source_path=str(path), content_hash="", status="pending"))
    db.commit()


def ingest_path_job(path_str: str) -> None:
    """Ingest a single file (used by the upload endpoint)."""
    from app.core.embeddings.factory import get_embedder
    from app.core.vector_store.factory import get_vector_store
    from app.db.session import SessionLocal

    settings = get_settings()
    db = SessionLocal()
    try:
        vector_store = get_vector_store(db, settings)
        result = _ingest_one(db, vector_store, get_embedder(), settings, Path(path_str))
        logger.info("Ingestion of %s finished: %s (%d chunks)", path_str, result.status, result.chunk_count)
    finally:
        db.close()


def ingest_all_job() -> None:
    """Scan the documents directory and ingest anything new or changed."""
    from app.core.embeddings.factory import get_embedder
    from app.core.vector_store.factory import get_vector_store
    from app.db.session import SessionLocal

    settings = get_settings()
    db = SessionLocal()
    try:
        vector_store = get_vector_store(db, settings)
        results = ingest_documents(db, vector_store, get_embedder(), settings)
        logger.info("Bulk ingestion finished: %d files processed", len(results))
    finally:
        db.close()

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.dependencies import DbDep, EmbedderDep, SettingsDep, VectorStoreDep
from app.db.models import Document
from app.ingestion.loaders import SUPPORTED_EXTENSIONS
from app.ingestion.pipeline import _ingest_one, ingest_documents

router = APIRouter(prefix="/api/documents", tags=["documents"])

_UPLOAD_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


class DocumentResponse(BaseModel):
    filename: str
    status: str
    chunk_count: int
    error_message: str | None = None


class IngestResultResponse(BaseModel):
    filename: str
    status: str
    chunk_count: int = 0
    error: str | None = None


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: DbDep) -> list[DocumentResponse]:
    documents = db.execute(select(Document).order_by(Document.filename)).scalars().all()
    return [
        DocumentResponse(
            filename=d.filename,
            status=d.status,
            chunk_count=d.chunk_count,
            error_message=d.error_message,
        )
        for d in documents
    ]


@router.post("/ingest", response_model=list[IngestResultResponse])
def trigger_ingestion(
    db: DbDep,
    vector_store: VectorStoreDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
) -> list[IngestResultResponse]:
    results = ingest_documents(db, vector_store, embedder, settings)
    return [
        IngestResultResponse(filename=r.filename, status=r.status, chunk_count=r.chunk_count, error=r.error)
        for r in results
    ]


@router.post("/upload", response_model=IngestResultResponse)
async def upload_document(
    file: UploadFile,
    db: DbDep,
    vector_store: VectorStoreDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
) -> IngestResultResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    safe_filename = Path(file.filename or "upload").name
    dest = (Path(settings.documents_dir) / safe_filename).resolve()
    docs_dir = Path(settings.documents_dir).resolve()

    if not str(dest).startswith(str(docs_dir) + "/"):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename: path traversal detected.",
        )

    dest.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    if len(content) > _UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    dest.write_bytes(content)

    result = _ingest_one(db, vector_store, embedder, settings, dest)
    return IngestResultResponse(
        filename=result.filename,
        status=result.status,
        chunk_count=result.chunk_count,
        error=result.error,
    )


@router.delete("/{filename}", status_code=204)
def delete_document(
    filename: str,
    db: DbDep,
    vector_store: VectorStoreDep,
    settings: SettingsDep,
) -> None:
    doc = db.execute(select(Document).where(Document.filename == filename)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    vector_store.delete_document(str(doc.id))
    db.delete(doc)
    db.commit()

    safe_filename = Path(filename).name
    file_path = (Path(settings.documents_dir) / safe_filename).resolve()
    docs_dir = Path(settings.documents_dir).resolve()

    if not str(file_path).startswith(str(docs_dir) + "/"):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename: path traversal detected.",
        )

    if file_path.exists():
        file_path.unlink()

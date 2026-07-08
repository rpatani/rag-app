import shutil
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import SettingsDep, VectorStoreDep

router = APIRouter(tags=["health"])

# Warn when the documents volume has less than this much free space.
_MIN_FREE_DISK_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


class HealthResponse(BaseModel):
    status: str
    vector_store: str
    vector_store_ok: bool
    documents_dir_ok: bool
    disk_free_gb: float
    disk_ok: bool
    pending_jobs: int
    embedder_backend: str
    llm_backend: str


@router.get("/api/health", response_model=HealthResponse)
def health(vector_store: VectorStoreDep, settings: SettingsDep) -> HealthResponse:
    """Liveness + readiness probe. Unauthenticated by design so external
    monitors can poll it; exposes operational state only, never data."""
    from app.core.jobs import _job_queue

    vector_store_ok = vector_store.health_check()

    docs_dir = Path(settings.documents_dir)
    documents_dir_ok = docs_dir.is_dir()

    if documents_dir_ok:
        usage = shutil.disk_usage(docs_dir)
    else:
        usage = shutil.disk_usage("/")
    disk_ok = usage.free >= _MIN_FREE_DISK_BYTES

    all_ok = vector_store_ok and documents_dir_ok and disk_ok
    return HealthResponse(
        status="ok" if all_ok else "degraded",
        vector_store=settings.vector_store_backend,
        vector_store_ok=vector_store_ok,
        documents_dir_ok=documents_dir_ok,
        disk_free_gb=round(usage.free / (1024**3), 2),
        disk_ok=disk_ok,
        pending_jobs=_job_queue.pending_count if _job_queue is not None else 0,
        embedder_backend=settings.embedder_backend,
        llm_backend=settings.llm_backend,
    )

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import SettingsDep, VectorStoreDep

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    vector_store: str
    vector_store_ok: bool
    embedder_backend: str
    llm_backend: str


@router.get("/api/health", response_model=HealthResponse)
def health(vector_store: VectorStoreDep, settings: SettingsDep) -> HealthResponse:
    vector_store_ok = vector_store.health_check()
    return HealthResponse(
        status="ok" if vector_store_ok else "degraded",
        vector_store=settings.vector_store_backend,
        vector_store_ok=vector_store_ok,
        embedder_backend=settings.embedder_backend,
        llm_backend=settings.llm_backend,
    )

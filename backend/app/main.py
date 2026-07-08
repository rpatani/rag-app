import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import routes_documents, routes_health, routes_query
from app.config import get_settings
from app.core.auth import require_api_key
from app.core.observability import RequestContextMiddleware, configure_logging

configure_logging(logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not get_settings().app_api_key:
        logger.warning(
            "APP_API_KEY is not set — API authentication is DISABLED. "
            "Set APP_API_KEY before exposing this service."
        )
    yield
    from app.core.jobs import _job_queue

    if _job_queue is not None:
        _job_queue.stop()


app = FastAPI(
    title="RAG Application",
    description="A production-style Retrieval-Augmented Generation app with a swappable vector store.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)

# Health stays unauthenticated so external monitors can probe it.
app.include_router(routes_health.router)
app.include_router(routes_query.router, dependencies=[Depends(require_api_key)])
app.include_router(routes_documents.router, dependencies=[Depends(require_api_key)])


# Serve the simple web UI (built without any framework/build step).
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import routes_documents, routes_health, routes_query

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="RAG Application",
    description="A production-style Retrieval-Augmented Generation app with a swappable vector store.",
    version="0.1.0",
)

app.include_router(routes_health.router)
app.include_router(routes_query.router)
app.include_router(routes_documents.router)

# Serve the simple web UI (built without any framework/build step).
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

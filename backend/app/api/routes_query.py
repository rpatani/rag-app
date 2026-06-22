import asyncio
import json
import threading

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.dependencies import RAGPipelineDep
from app.models import SourceCitation

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    question: str


class SourceResponse(BaseModel):
    filename: str
    chunk_index: int
    snippet: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]


def _to_response(source: SourceCitation) -> SourceResponse:
    return SourceResponse(
        filename=source.filename,
        chunk_index=source.chunk_index,
        snippet=source.snippet,
        score=source.score,
    )


@router.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest, pipeline: RAGPipelineDep) -> QueryResponse:
    result = pipeline.answer(request.question)
    return QueryResponse(answer=result.answer, sources=[_to_response(s) for s in result.sources])


@router.post("/api/query/stream")
async def query_stream(request: QueryRequest, pipeline: RAGPipelineDep) -> StreamingResponse:
    """Stream tokens via Server-Sent Events as they arrive from the LLM."""

    async def event_generator():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _produce() -> None:
            try:
                for event in pipeline.answer_stream(request.question):
                    asyncio.run_coroutine_threadsafe(queue.put(event), loop).result()
            except Exception as exc:  # noqa: BLE001
                asyncio.run_coroutine_threadsafe(
                    queue.put({"type": "error", "message": str(exc)}), loop
                ).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()

        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

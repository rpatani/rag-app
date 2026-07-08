"""
Request tracing and structured logging.

Every request gets a short request ID (from the X-Request-ID header if the
caller supplies one, otherwise generated). The ID is:
- stored in a contextvar so any log line emitted while handling the request
  is automatically tagged with it,
- returned in the X-Request-ID response header so users can quote it in
  support requests,
- logged with method, path, status, and latency for every request.

`log_timing` is a small context manager for measuring pipeline stages.
"""

import contextvars
import logging
import time
import uuid
from contextlib import contextmanager

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

logger = logging.getLogger("app.request")


class RequestIdFilter(logging.Filter):
    """Injects the current request ID into every log record as %(request_id)s."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(req_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "%s %s -> 500 (%.1fms)", request.method, request.url.path, elapsed_ms
            )
            raise
        finally:
            request_id_var.reset(token)

        elapsed_ms = (time.perf_counter() - start) * 1000
        # Skip static-asset noise; log every API call.
        if request.url.path.startswith("/api"):
            logger.info(
                "%s %s -> %d (%.1fms)",
                request.method, request.url.path, response.status_code, elapsed_ms,
            )
        response.headers["X-Request-ID"] = req_id
        return response


@contextmanager
def log_timing(stage: str, target_logger: logging.Logger):
    """Log how long a pipeline stage took: `with log_timing("retrieve", logger): ...`"""
    start = time.perf_counter()
    try:
        yield
    finally:
        target_logger.info("%s took %.1fms", stage, (time.perf_counter() - start) * 1000)


def configure_logging(level: int = logging.INFO) -> None:
    """Structured-ish single-line format with request IDs. Idempotent."""
    root = logging.getLogger()
    if getattr(root, "_rag_app_configured", False):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)
    root.setLevel(level)
    root._rag_app_configured = True  # type: ignore[attr-defined]

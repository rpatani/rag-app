"""
In-process background job queue.

Sized for the single-server appliance deployment: one worker thread executes
jobs sequentially (ingestion is CPU-bound; running uploads one at a time
protects query latency), a bounded queue applies backpressure instead of
letting memory grow without limit, and every job is logged with its outcome.

This is intentionally not Celery/RQ: no broker to operate, no extra
containers. The interface is small enough that swapping in a distributed
queue later means reimplementing two methods (`submit`, `pending_count`).

Jobs must be self-contained callables that manage their own resources
(e.g. open and close their own DB session) — they run outside any request
context.
"""

import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    name: str
    fn: Callable[..., Any]
    args: tuple = field(default_factory=tuple)


class JobQueue:
    def __init__(self, max_pending: int = 100):
        self._queue: "queue.Queue[_Job | None]" = queue.Queue(maxsize=max_pending)
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self._run, name="job-worker", daemon=True)
            self._worker.start()
        logger.info("Job queue worker started")

    def stop(self, timeout: float = 10.0) -> None:
        """Signal the worker to exit after finishing the current job."""
        worker = self._worker
        if worker is None or not worker.is_alive():
            return
        self._queue.put(None)  # sentinel
        worker.join(timeout=timeout)

    def submit(self, name: str, fn: Callable[..., Any], *args: Any) -> bool:
        """Enqueue a job. Returns False (without blocking) if the queue is full."""
        try:
            self._queue.put_nowait(_Job(name=name, fn=fn, args=args))
        except queue.Full:
            logger.warning("Job queue full (%d pending) — rejected job %r", self.pending_count, name)
            return False
        logger.info("Queued job %r (%d pending)", name, self.pending_count)
        return True

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                self._queue.task_done()
                return
            try:
                job.fn(*job.args)
                logger.info("Job %r completed", job.name)
            except Exception:
                # Job failures must never kill the worker thread.
                logger.exception("Job %r failed", job.name)
            finally:
                self._queue.task_done()


_job_queue: JobQueue | None = None


def get_job_queue() -> JobQueue:
    """Process-wide job queue singleton. start() is idempotent and revives
    the worker if it was stopped (e.g. app restart in tests)."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    _job_queue.start()
    return _job_queue

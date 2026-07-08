"""Job queue: execution order, failure isolation, backpressure, shutdown."""

import threading
import time

from app.core.jobs import JobQueue


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_jobs_execute_in_order():
    q = JobQueue()
    q.start()
    results = []
    for i in range(5):
        q.submit(f"job{i}", results.append, i)
    assert _wait_for(lambda: len(results) == 5)
    assert results == [0, 1, 2, 3, 4]
    q.stop()


def test_failing_job_does_not_kill_worker():
    q = JobQueue()
    q.start()
    results = []

    def boom():
        raise RuntimeError("simulated failure")

    q.submit("boom", boom)
    q.submit("after", results.append, "survived")
    assert _wait_for(lambda: results == ["survived"])
    q.stop()


def test_queue_full_rejects_instead_of_blocking():
    q = JobQueue(max_pending=2)
    # Worker NOT started: jobs stay queued.
    assert q.submit("a", lambda: None) is True
    assert q.submit("b", lambda: None) is True
    assert q.submit("c", lambda: None) is False  # full -> rejected, no block


def test_stop_waits_for_current_job():
    q = JobQueue()
    q.start()
    started = threading.Event()
    finished = []

    def slow():
        started.set()
        time.sleep(0.2)
        finished.append(True)

    q.submit("slow", slow)
    assert started.wait(timeout=2)
    q.stop(timeout=5)
    assert finished == [True]

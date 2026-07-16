"""Unit tests for InProcessJobQueue."""
from __future__ import annotations

import threading

from backend.app.jobs.in_process_job_queue import InProcessJobQueue


def test_enqueue_runs_the_function():
    queue = InProcessJobQueue(max_workers=1)
    done = threading.Event()
    result = {}

    def _work() -> None:
        result["ran"] = True
        done.set()

    queue.enqueue("job-1", _work)

    assert done.wait(timeout=2.0)
    assert result.get("ran") is True
    queue.shutdown()


def test_exception_in_one_job_does_not_break_the_queue():
    queue = InProcessJobQueue(max_workers=1)
    first_done = threading.Event()
    second_done = threading.Event()

    def _boom() -> None:
        first_done.set()
        raise RuntimeError("kaboom")

    def _ok() -> None:
        second_done.set()

    queue.enqueue("job-1", _boom)
    assert first_done.wait(timeout=2.0)

    queue.enqueue("job-2", _ok)
    assert second_done.wait(timeout=2.0)

    queue.shutdown()

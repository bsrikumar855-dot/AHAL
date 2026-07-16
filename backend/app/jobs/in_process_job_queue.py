"""ThreadPoolExecutor-backed JobQueue.

Indexing is blocking (subprocess git clone/log, ast.parse), so a thread pool
keeps the FastAPI event loop responsive without a broker that has nowhere to
run without Docker. `fn` (services.indexing_service.run_index_job) is
responsible for recording its own failure via IndexJobRepository.mark_failed
-- this queue only logs an unhandled exception as a last-resort safety net,
mirroring how a real Celery task records failure in its own result backend
rather than crashing the worker process.
"""
from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

logger = logging.getLogger(__name__)


class InProcessJobQueue:
    def __init__(self, max_workers: int) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="ahal-job")

    def enqueue(self, job_id: str, fn: Callable[[], None]) -> None:
        future = self._executor.submit(fn)
        future.add_done_callback(lambda f: self._log_if_unhandled(job_id, f))

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

    def _log_if_unhandled(self, job_id: str, future: Future) -> None:
        exc = future.exception()
        if exc is not None:
            logger.error("index job %s raised an unhandled exception", job_id, exc_info=exc)

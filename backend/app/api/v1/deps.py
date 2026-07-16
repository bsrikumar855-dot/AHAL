"""FastAPI dependency providers for the v1 API.

Centralizes how routes obtain a DB session, the configured GraphRepository,
and the JobQueue singleton, so route handlers (api/v1/repos.py) stay thin.
Tests override every one of these via `app.dependency_overrides` rather than
monkeypatching module state (see backend/tests/conftest.py).
"""
from __future__ import annotations

from backend.app.config import Settings, settings
from backend.app.db.session import get_session_factory  # noqa: F401 -- re-exported for routes
from backend.app.graph.graph_repository import GraphRepository
from backend.app.graph.networkx_graph_repository import NetworkXGraphRepository
from backend.app.jobs.in_process_job_queue import InProcessJobQueue
from backend.app.jobs.job_queue import JobQueue

_graph_repo: GraphRepository = NetworkXGraphRepository(settings.graph_store_dir)
_job_queue: InProcessJobQueue = InProcessJobQueue(max_workers=settings.index_worker_threads)


def get_settings_dep() -> Settings:
    return settings


def get_graph_repository() -> GraphRepository:
    return _graph_repo


def get_job_queue() -> JobQueue:
    return _job_queue

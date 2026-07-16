"""Shared fixtures for backend tests.

Every fixture builds its own isolated SQLite file + graph-store directory
per test (no shared global state), and `fixture_repo` provides a tiny real
local git repo so indexing tests exercise `ahal.extract` directly rather
than mocks -- consistent with how ahal/tests/test_verifier.py exercises
real StructuralGraph/CoChangeIndex fixtures instead of mocking them.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.v1 import deps
from backend.app.config import Settings
from backend.app.db import models  # noqa: F401 -- registers ORM models before create_all
from backend.app.db.base import build_session_factory
from backend.app.db.session import get_db
from backend.app.graph.networkx_graph_repository import NetworkXGraphRepository
from backend.app.main import create_app


def _git(repo_dir: Path, *args: str) -> None:
    # stdin=DEVNULL: avoids inheriting a possibly-invalidated parent stdin
    # handle on Windows after a FastAPI TestClient's async lifecycle has run
    # earlier in the same test session ("WinError 6: the handle is invalid").
    subprocess.run(["git", "-C", str(repo_dir), *args],
                    check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """A tiny local git repo with one real import edge (a.py -> b.py) and
    one real co-change (both files touched in both commits)."""
    repo_dir = tmp_path / "fixture_repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "--quiet")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")

    (repo_dir / "a.py").write_text("import b\n")
    (repo_dir / "b.py").write_text("x = 1\n")
    _git(repo_dir, "add", ".")
    _git(repo_dir, "commit", "--quiet", "-m", "initial")

    (repo_dir / "a.py").write_text("import b\nprint(b.x)\n")
    (repo_dir / "b.py").write_text("x = 2\n")
    _git(repo_dir, "add", ".")
    _git(repo_dir, "commit", "--quiet", "-m", "update both")

    return repo_dir


@pytest.fixture
def session_factory(tmp_path: Path) -> sessionmaker[Session]:
    return build_session_factory(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def graph_repo(tmp_path: Path) -> NetworkXGraphRepository:
    return NetworkXGraphRepository(tmp_path / "graphs")


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'unused.db'}",
        graph_store_dir=tmp_path / "graphs",
        clone_cache_dir=tmp_path / "clones",
        max_commits_to_index=2000,
        max_files_per_commit=50,
        index_worker_threads=1,
    )


class SynchronousJobQueue:
    """Test double for JobQueue: runs enqueued work immediately, in-thread,
    so API tests don't need to poll for a background thread to finish."""

    def enqueue(self, job_id: str, fn: Callable[[], None]) -> None:
        fn()


@pytest.fixture
def api_client(session_factory, graph_repo, test_settings):
    app = create_app()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[deps.get_session_factory] = lambda: session_factory
    app.dependency_overrides[deps.get_graph_repository] = lambda: graph_repo
    app.dependency_overrides[deps.get_job_queue] = lambda: SynchronousJobQueue()
    app.dependency_overrides[deps.get_settings_dep] = lambda: test_settings

    with TestClient(app) as client:
        yield client

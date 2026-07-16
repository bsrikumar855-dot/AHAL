"""SQLAlchemy declarative base + session-factory construction.

`build_session_factory` is a factory, not a bare module-level engine, so
tests can point at an isolated database file without monkeypatching global
state — the same dependency-injection discipline used throughout this
backend (see graph/graph_repository.py, jobs/job_queue.py for the other two
swappable-infra seams).
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    """Create the tables (if absent) and return a session factory bound to
    `database_url`.

    SQLite needs `check_same_thread=False` because the in-process job queue
    (jobs/in_process_job_queue.py) runs indexing on a worker thread, not the
    request thread that created the session factory -- and that's also why
    `expire_on_commit=False`: with the default (True), an object touched
    after a *later* commit on the same session (e.g. `repo` after
    `IndexJobRepository.create()` commits) is marked expired, so the next
    attribute access issues a lazy SELECT to refresh it. If that lazy SELECT
    happens to land while a concurrent worker-thread session is mid-write to
    the very same row, it can intermittently come back empty and raise
    `ObjectDeletedError` even though the row exists -- reproduced directly
    against `services/repo_service.connect_repo` racing
    `services/indexing_service.run_index_job`. `expire_on_commit=False`
    removes the lazy refresh entirely; repositories that need current DB
    state after a write already call `session.refresh()` explicitly and
    synchronously, which isn't affected by this setting.
    """
    _ensure_sqlite_parent_dir_exists(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine: Engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _ensure_sqlite_parent_dir_exists(database_url: str) -> None:
    """SQLite fails outright if the target file's directory doesn't exist
    yet; create it. No-op for in-memory or non-SQLite URLs."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return
    path = database_url[len(prefix):]
    if path == ":memory:":
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)

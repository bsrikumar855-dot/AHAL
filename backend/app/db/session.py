"""FastAPI dependency providing a request-scoped SQLAlchemy session.

Built from `settings.database_url` (config.py) by default; tests override
this dependency entirely (see backend/tests/conftest.py) rather than
monkeypatching the module-level factory, per FastAPI's standard testing
pattern.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import settings
from backend.app.db import models  # noqa: F401 -- registers ORM models before create_all
from backend.app.db.base import build_session_factory

_session_factory: sessionmaker[Session] = build_session_factory(settings.database_url)


def get_db() -> Generator[Session, None, None]:
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> sessionmaker[Session]:
    """Exposes the module's session factory for callers that need to open
    their own session outside the request lifecycle (services/repo_service.py's
    background indexing thread), without reaching into `_session_factory`
    directly."""
    return _session_factory

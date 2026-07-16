"""Data-access layer for `Repo` rows (Repository pattern).

Every read/write against the `repos` table goes through this class; nothing
above it (services/) or below it (db/models.py) should issue SQLAlchemy
queries directly. Swapping SQLite for Postgres later means changing
`config.database_url` only — this class is unaware of the underlying engine.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Repo, RepoStatus


class RepoRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, url: str, name: str) -> Repo:
        repo = Repo(url=url, name=name, status=RepoStatus.PENDING)
        self._session.add(repo)
        self._session.commit()
        self._session.refresh(repo)
        return repo

    def get(self, repo_id: str) -> Repo | None:
        return self._session.get(Repo, repo_id)

    def list_all(self) -> list[Repo]:
        stmt = select(Repo).order_by(Repo.created_at.desc())
        return list(self._session.scalars(stmt))

    def set_status(self, repo: Repo, status: RepoStatus) -> Repo:
        repo.status = status
        self._session.commit()
        self._session.refresh(repo)
        return repo

    def record_graph_summary(self, repo: Repo, *, node_count: int, edge_count: int,
                              commit_count: int, indexed_at: datetime) -> Repo:
        """Called once an index job succeeds: stamps the graph summary and
        flips status to READY in a single update."""
        repo.node_count = node_count
        repo.edge_count = edge_count
        repo.commit_count = commit_count
        repo.last_indexed_at = indexed_at
        repo.status = RepoStatus.READY
        self._session.commit()
        self._session.refresh(repo)
        return repo

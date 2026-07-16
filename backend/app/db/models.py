"""ORM models for Increment 1: a connected repository and its index runs.

Importing this module registers `Repo`/`IndexJob` on `Base.metadata`; it
must happen before `build_session_factory` (db/base.py) is called, or
`create_all` will create no tables. `db/session.py` and every test that
builds its own session factory import this module first for that reason.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RepoStatus(str, enum.Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class IndexJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Repo(Base):
    """A repository the user has connected. `node_count`/`edge_count`/
    `commit_count` mirror the latest successful indexing run's
    GraphRepository summary (graph/graph_repository.py)."""

    __tablename__ = "repos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RepoStatus] = mapped_column(
        Enum(RepoStatus), default=RepoStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    last_indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    node_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    commit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    jobs: Mapped[list["IndexJob"]] = relationship(
        back_populates="repo", cascade="all, delete-orphan")


class IndexJob(Base):
    """One run of the indexing pipeline (services/indexing_service.py)
    against a Repo: clone -> ahal.extract.* -> GraphRepository.save_snapshot.
    """

    __tablename__ = "index_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    repo_id: Mapped[str] = mapped_column(String(36), ForeignKey("repos.id"), nullable=False)
    status: Mapped[IndexJobStatus] = mapped_column(
        Enum(IndexJobStatus), default=IndexJobStatus.PENDING, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    commits_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    repo: Mapped["Repo"] = relationship(back_populates="jobs")

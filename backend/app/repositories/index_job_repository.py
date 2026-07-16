"""Data-access layer for `IndexJob` rows (Repository pattern)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.db.models import IndexJob, IndexJobStatus


class IndexJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, repo_id: str) -> IndexJob:
        job = IndexJob(repo_id=repo_id, status=IndexJobStatus.PENDING)
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def get(self, job_id: str) -> IndexJob | None:
        return self._session.get(IndexJob, job_id)

    def mark_running(self, job: IndexJob) -> IndexJob:
        job.status = IndexJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_succeeded(self, job: IndexJob, *, commits_processed: int) -> IndexJob:
        job.status = IndexJobStatus.SUCCEEDED
        job.finished_at = datetime.now(timezone.utc)
        job.commits_processed = commits_processed
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_failed(self, job: IndexJob, *, error_message: str) -> IndexJob:
        job.status = IndexJobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = error_message
        self._session.commit()
        self._session.refresh(job)
        return job

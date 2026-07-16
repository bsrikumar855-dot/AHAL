"""Unit tests for IndexJobRepository against a real SQLite db (no mocking)."""
from __future__ import annotations

from backend.app.db.models import IndexJobStatus
from backend.app.repositories.index_job_repository import IndexJobRepository
from backend.app.repositories.repo_repository import RepoRepository


def _make_repo(session_factory):
    session = session_factory()
    return RepoRepository(session).create(url="https://x/1.git", name="x/1"), session


def test_create_and_get_round_trip(session_factory):
    repo, session = _make_repo(session_factory)
    jobs = IndexJobRepository(session)

    created = jobs.create(repo_id=repo.id)
    fetched = jobs.get(created.id)

    assert fetched is not None
    assert fetched.repo_id == repo.id
    assert fetched.status is IndexJobStatus.PENDING


def test_mark_running_then_succeeded(session_factory):
    repo, session = _make_repo(session_factory)
    jobs = IndexJobRepository(session)
    job = jobs.create(repo_id=repo.id)

    jobs.mark_running(job)
    assert job.status is IndexJobStatus.RUNNING
    assert job.started_at is not None

    jobs.mark_succeeded(job, commits_processed=7)
    assert job.status is IndexJobStatus.SUCCEEDED
    assert job.finished_at is not None
    assert job.commits_processed == 7


def test_mark_failed_records_error_message(session_factory):
    repo, session = _make_repo(session_factory)
    jobs = IndexJobRepository(session)
    job = jobs.create(repo_id=repo.id)

    jobs.mark_failed(job, error_message="clone failed")

    assert job.status is IndexJobStatus.FAILED
    assert job.error_message == "clone failed"
    assert job.finished_at is not None

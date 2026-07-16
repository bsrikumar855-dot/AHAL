"""Orchestrates connecting a repo: create rows, enqueue indexing.

This is the only entry point API routes call for repo connection; it wires
together RepoRepository, IndexJobRepository, GraphRepository, and JobQueue
without any of them knowing about each other.
"""
from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import Settings
from backend.app.core.exceptions import IndexJobNotFoundError, RepoNotFoundError
from backend.app.db.models import IndexJob, Repo
from backend.app.graph.graph_repository import GraphRepository
from backend.app.jobs.job_queue import JobQueue
from backend.app.repositories.index_job_repository import IndexJobRepository
from backend.app.repositories.repo_repository import RepoRepository
from backend.app.services.indexing_service import run_index_job


def connect_repo(*, url: str, session: Session, session_factory: sessionmaker,
                  graph_repo: GraphRepository, job_queue: JobQueue,
                  settings: Settings) -> tuple[Repo, IndexJob]:
    """Create a Repo + its first IndexJob, and enqueue indexing.

    `session` persists the two new rows synchronously so the caller gets a
    real repo/job id back immediately; `session_factory` builds a *separate*
    session for the background thread the job actually runs on, since the
    request-scoped `session` closes once this function returns.
    """
    repos = RepoRepository(session)
    jobs = IndexJobRepository(session)

    repo = repos.create(url=url, name=_derive_name(url))
    job = jobs.create(repo_id=repo.id)

    def _run() -> None:
        worker_session = session_factory()
        try:
            run_index_job(
                repo_id=repo.id, job_id=job.id, url=url,
                session=worker_session, graph_repo=graph_repo, settings=settings,
            )
        finally:
            worker_session.close()

    job_queue.enqueue(job.id, _run)
    return repo, job


def get_repo_or_raise(repo_id: str, session: Session) -> Repo:
    repo = RepoRepository(session).get(repo_id)
    if repo is None:
        raise RepoNotFoundError(repo_id)
    return repo


def list_repos(session: Session) -> list[Repo]:
    return RepoRepository(session).list_all()


def get_index_job_or_raise(repo_id: str, job_id: str, session: Session) -> IndexJob:
    job = IndexJobRepository(session).get(job_id)
    if job is None or job.repo_id != repo_id:
        raise IndexJobNotFoundError(job_id)
    return job


def _derive_name(url: str) -> str:
    """`owner/repo` from a git URL, falling back to the last path segment."""
    trimmed = url.rstrip("/")
    if trimmed.endswith(".git"):
        trimmed = trimmed[: -len(".git")]
    parts = [p for p in trimmed.replace(":", "/").split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

"""Repo connection + status endpoints.

Increment 1 scope: connect a repo, index it, query status/graph summary.
No prediction endpoint yet (Increment 2, see docs/roadmap.md) -- this file
is intentionally HTTP-concerns-only; all orchestration lives in
services/repo_service.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.v1.deps import (
    get_graph_repository,
    get_job_queue,
    get_session_factory,
    get_settings_dep,
)
from backend.app.config import Settings
from backend.app.db.session import get_db
from backend.app.domain.schemas import (
    IndexJobRead,
    RepoCreate,
    RepoCreateResponse,
    RepoRead,
)
from backend.app.graph.graph_repository import GraphRepository
from backend.app.jobs.job_queue import JobQueue
from backend.app.services import repo_service

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("", response_model=RepoCreateResponse, status_code=status.HTTP_201_CREATED)
def create_repo(
    payload: RepoCreate,
    session: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
    graph_repo: GraphRepository = Depends(get_graph_repository),
    job_queue: JobQueue = Depends(get_job_queue),
    settings: Settings = Depends(get_settings_dep),
) -> RepoCreateResponse:
    repo, job = repo_service.connect_repo(
        url=payload.url,
        session=session,
        session_factory=session_factory,
        graph_repo=graph_repo,
        job_queue=job_queue,
        settings=settings,
    )
    return RepoCreateResponse(
        repo=RepoRead.model_validate(repo),
        job=IndexJobRead.model_validate(job),
    )


@router.get("", response_model=list[RepoRead])
def list_repos(session: Session = Depends(get_db)) -> list[RepoRead]:
    repos = repo_service.list_repos(session)
    return [RepoRead.model_validate(r) for r in repos]


@router.get("/{repo_id}", response_model=RepoRead)
def get_repo(repo_id: str, session: Session = Depends(get_db)) -> RepoRead:
    repo = repo_service.get_repo_or_raise(repo_id, session)
    return RepoRead.model_validate(repo)


@router.get("/{repo_id}/jobs/{job_id}", response_model=IndexJobRead)
def get_index_job(
    repo_id: str, job_id: str, session: Session = Depends(get_db),
) -> IndexJobRead:
    job = repo_service.get_index_job_or_raise(repo_id, job_id, session)
    return IndexJobRead.model_validate(job)

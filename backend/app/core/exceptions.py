"""Domain-level exceptions.

Services and repositories raise these, never `fastapi.HTTPException` —
that keeps them framework-agnostic. The API layer (api/v1/repos.py)
translates each into the appropriate HTTP status code.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all AHAL backend domain errors."""


class RepoNotFoundError(DomainError):
    def __init__(self, repo_id: str) -> None:
        super().__init__(f"repo not found: {repo_id}")
        self.repo_id = repo_id


class IndexJobNotFoundError(DomainError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"index job not found: {job_id}")
        self.job_id = job_id

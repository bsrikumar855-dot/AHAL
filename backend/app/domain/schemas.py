"""Pydantic request/response models for the public API.

Kept separate from the SQLAlchemy ORM models (db/models.py) so the HTTP
contract can evolve independently of the storage schema — the API layer
depends on these, never on ORM rows directly.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RepoCreate(BaseModel):
    url: str = Field(..., min_length=1,
                      description="Git remote URL or local path to clone and index.")


class RepoRead(BaseModel):
    id: str
    url: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_indexed_at: datetime | None
    node_count: int
    edge_count: int
    commit_count: int

    model_config = {"from_attributes": True}


class IndexJobRead(BaseModel):
    id: str
    repo_id: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    commits_processed: int

    model_config = {"from_attributes": True}


class RepoCreateResponse(BaseModel):
    repo: RepoRead
    job: IndexJobRead


class PredictionItem(BaseModel):
    target: str
    score: float
    basis: str
    calibrated_score: float | None = None

    model_config = {"from_attributes": True}


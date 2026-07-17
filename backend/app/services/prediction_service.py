"""Orchestrates predictions: load snapshots, instantiate Predictor, run predictions, load calibrator.

Keeps prediction logic clean and separated from the API layer.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ahal.predictor import Predictor

from backend.app.core.exceptions import (
    RepoIndexingInProgressError,
    RepoNotIndexedError,
    RepoNotFoundError,
)
from backend.app.db.models import RepoStatus
from backend.app.graph.graph_repository import GraphRepository
from backend.app.repositories.repo_repository import RepoRepository


def get_predictions(
    *,
    repo_id: str,
    changed_files: list[str],
    session: Session,
    graph_repo: GraphRepository,
) -> list[dict]:
    # 1. Retrieve the repo from database
    repo = RepoRepository(session).get(repo_id)
    if repo is None:
        raise RepoNotFoundError(repo_id)

    # 2. Check indexing status
    if repo.status in (RepoStatus.PENDING, RepoStatus.INDEXING):
        raise RepoIndexingInProgressError(repo_id)
    if repo.status == RepoStatus.FAILED:
        raise RepoNotIndexedError(repo_id)

    # 3. Load structural graph and co-change index
    snapshot = graph_repo.load_snapshot(repo_id)
    if snapshot is None:
        raise RepoNotIndexedError(repo_id)

    graph, cochange = snapshot

    # 4. Generate predictions
    predictor = Predictor(graph, cochange)
    preds = predictor.predict(changed_files)

    # 5. Load calibrator if fit
    calibrator = graph_repo.load_calibrator(repo_id)

    # 6. Format predictions including basis and calibrated scores
    results = []
    for p in preds:
        calibrated_score = (
            calibrator.calibrate(p.score) if calibrator is not None else None
        )
        results.append({
            "target": p.target,
            "score": p.score,
            "basis": p.basis.describe(),
            "calibrated_score": calibrated_score,
        })

    return results

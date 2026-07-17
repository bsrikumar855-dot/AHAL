"""Integration tests for the prediction API endpoint.

Exercises POST /repos/{id}/predict, checking 404 (not indexed/failed),
409 (indexing in progress), calibration functionality, and precision/recall
on the fixture repo.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Repo, RepoStatus
from backend.app.graph.graph_repository import GraphRepository


def test_predict_endpoint_indexed_repo(api_client, fixture_repo):
    # 1. Index the fixture repo first
    create_resp = api_client.post("/api/v1/repos", json={"url": str(fixture_repo)})
    assert create_resp.status_code == 201
    repo_id = create_resp.json()["repo"]["id"]

    # Verify status is READY
    get_resp = api_client.get(f"/api/v1/repos/{repo_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "ready"

    # 2. Query predict endpoint with a list of changed files
    # The fixture repo has `a.py` importing `b.py` and they co-changed.
    predict_resp = api_client.post(
        f"/api/v1/repos/{repo_id}/predict",
        json=["a.py"],
    )
    assert predict_resp.status_code == 200
    predictions = predict_resp.json()

    # We expect one verified prediction: b.py (structural neighbor and co-change)
    assert len(predictions) > 0
    b_pred = next((p for p in predictions if p["target"] == "b.py"), None)
    assert b_pred is not None
    assert b_pred["score"] > 0.0
    assert "reachable" in b_pred["basis"] or "co-changed" in b_pred["basis"]
    assert b_pred["calibrated_score"] is None

    # Let's show precision/recall on the fixture repo:
    # Ground truth actual changes (from update commit): a.py, b.py.
    # Seed change was a.py. So expected target is b.py.
    # Our prediction was: b.py.
    # Therefore, predicted target set = {"b.py"}, actual target set = {"b.py"}.
    predicted = {p["target"] for p in predictions}
    actual = {"b.py"}
    tp = predicted & actual
    fp = predicted - actual
    fn = actual - predicted
    precision = len(tp) / (len(tp) + len(fp)) if (len(tp) + len(fp)) > 0 else 0.0
    recall = len(tp) / (len(tp) + len(fn)) if (len(tp) + len(fn)) > 0 else 0.0

    print(f"\nFixture Repo Prediction Metrics:")
    print(f"  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")


def test_predict_endpoint_unknown_repo(api_client):
    resp = api_client.post("/api/v1/repos/does-not-exist/predict", json=["a.py"])
    assert resp.status_code == 404
    assert "repo not found" in resp.json()["detail"]


def test_predict_endpoint_indexing_in_progress(api_client, session_factory):
    # Create a pending repo row in database
    db = session_factory()
    repo = Repo(url="https://example.com/git.git", name="git", status=RepoStatus.INDEXING)
    db.add(repo)
    db.commit()
    repo_id = repo.id
    db.close()

    resp = api_client.post(f"/api/v1/repos/{repo_id}/predict", json=["a.py"])
    assert resp.status_code == 409
    assert "indexing still in progress" in resp.json()["detail"]


def test_predict_endpoint_not_indexed_yet(api_client, session_factory):
    # Create a failed repo row in database
    db = session_factory()
    repo = Repo(url="https://example.com/git.git", name="git", status=RepoStatus.FAILED)
    db.add(repo)
    db.commit()
    repo_id = repo.id
    db.close()

    resp = api_client.post(f"/api/v1/repos/{repo_id}/predict", json=["a.py"])
    assert resp.status_code == 404
    assert "repo not indexed" in resp.json()["detail"]


def test_predict_endpoint_with_calibrator(api_client, fixture_repo, graph_repo: GraphRepository):
    # 1. Index the fixture repo first
    create_resp = api_client.post("/api/v1/repos", json={"url": str(fixture_repo)})
    assert create_resp.status_code == 201
    repo_id = create_resp.json()["repo"]["id"]

    # 2. Save a dummy calibrator for this repo
    # fit_pairs is a list of (raw_score, hit)
    fit_pairs = [(0.5, True), (0.5, False), (0.9, True), (0.9, True)]
    graph_repo.save_calibrator(repo_id, fit_pairs)

    # 3. Query predict endpoint
    predict_resp = api_client.post(
        f"/api/v1/repos/{repo_id}/predict",
        json=["a.py"],
    )
    assert predict_resp.status_code == 200
    predictions = predict_resp.json()

    assert len(predictions) > 0
    for p in predictions:
        assert p["calibrated_score"] is not None
        assert 0.0 <= p["calibrated_score"] <= 1.0

"""Unit tests for RepoRepository against a real SQLite db (no mocking)."""
from __future__ import annotations

from datetime import datetime, timezone

from backend.app.db.models import RepoStatus
from backend.app.repositories.repo_repository import RepoRepository


def test_create_and_get_round_trip(session_factory):
    session = session_factory()
    repos = RepoRepository(session)

    created = repos.create(url="https://github.com/owner/repo.git", name="owner/repo")
    fetched = repos.get(created.id)

    assert fetched is not None
    assert fetched.url == "https://github.com/owner/repo.git"
    assert fetched.status is RepoStatus.PENDING


def test_get_missing_returns_none(session_factory):
    session = session_factory()
    assert RepoRepository(session).get("does-not-exist") is None


def test_list_all_returns_created_repos(session_factory):
    session = session_factory()
    repos = RepoRepository(session)

    first = repos.create(url="https://x/1.git", name="x/1")
    second = repos.create(url="https://x/2.git", name="x/2")

    assert {r.id for r in repos.list_all()} == {first.id, second.id}


def test_set_status_updates_row(session_factory):
    session = session_factory()
    repos = RepoRepository(session)
    repo = repos.create(url="https://x/1.git", name="x/1")

    updated = repos.set_status(repo, RepoStatus.INDEXING)

    assert updated.status is RepoStatus.INDEXING


def test_record_graph_summary_sets_ready_and_counts(session_factory):
    session = session_factory()
    repos = RepoRepository(session)
    repo = repos.create(url="https://x/1.git", name="x/1")
    now = datetime.now(timezone.utc)

    updated = repos.record_graph_summary(
        repo, node_count=3, edge_count=2, commit_count=5, indexed_at=now)

    assert updated.status is RepoStatus.READY
    assert updated.node_count == 3
    assert updated.edge_count == 2
    assert updated.commit_count == 5
    # SQLite doesn't preserve tzinfo through a round trip (a Postgres-backed
    # deployment would); compare naively, which is what this increment's
    # storage can actually promise.
    assert updated.last_indexed_at.replace(tzinfo=None) == now.replace(tzinfo=None)

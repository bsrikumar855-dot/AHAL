"""End-to-end test of indexing_service.run_index_job against a real local
git fixture repo -- exercises ahal.extract directly, no mocks."""
from __future__ import annotations

from backend.app.db.models import IndexJobStatus, RepoStatus
from backend.app.repositories.index_job_repository import IndexJobRepository
from backend.app.repositories.repo_repository import RepoRepository
from backend.app.services.indexing_service import run_index_job


def test_run_index_job_succeeds_against_real_repo(
    session_factory, graph_repo, test_settings, fixture_repo,
):
    session = session_factory()
    repos = RepoRepository(session)
    jobs = IndexJobRepository(session)

    repo = repos.create(url=str(fixture_repo), name="fixture")
    job = jobs.create(repo_id=repo.id)

    run_index_job(
        repo_id=repo.id, job_id=job.id, url=str(fixture_repo),
        session=session, graph_repo=graph_repo, settings=test_settings,
    )

    updated_repo = repos.get(repo.id)
    updated_job = jobs.get(job.id)

    assert updated_repo.status is RepoStatus.READY
    assert updated_repo.node_count == 2  # a.py, b.py
    assert updated_repo.edge_count == 1  # a.py -> b.py
    assert updated_repo.commit_count == 2  # both commits touched both files
    assert updated_job.status is IndexJobStatus.SUCCEEDED
    assert updated_job.commits_processed == 2

    snapshot = graph_repo.load_snapshot(repo.id)
    assert snapshot is not None
    graph, cochange = snapshot
    assert graph.reaches("a.py", "b.py", 1)
    assert cochange.cochange_count("a.py", "b.py") == 2


def test_run_index_job_marks_failed_on_bad_source(session_factory, graph_repo, test_settings):
    session = session_factory()
    repos = RepoRepository(session)
    jobs = IndexJobRepository(session)

    bad_url = "/definitely/not/a/repo"
    repo = repos.create(url=bad_url, name="bad")
    job = jobs.create(repo_id=repo.id)

    run_index_job(
        repo_id=repo.id, job_id=job.id, url=bad_url,
        session=session, graph_repo=graph_repo, settings=test_settings,
    )

    updated_repo = repos.get(repo.id)
    updated_job = jobs.get(job.id)

    assert updated_repo.status is RepoStatus.FAILED
    assert updated_job.status is IndexJobStatus.FAILED
    assert updated_job.error_message

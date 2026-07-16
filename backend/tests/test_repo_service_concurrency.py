"""Regression test for a real race between connect_repo() and the
background indexing thread it starts.

With the default SQLAlchemy `expire_on_commit=True`, `repo` gets marked
expired by IndexJobRepository.create()'s commit; serializing it afterwards
(RepoRead.model_validate in api/v1/repos.py) triggers a lazy SELECT that can
land mid-write from the concurrent indexing thread's own session and
intermittently raise ObjectDeletedError -- reproduced directly against the
real InProcessJobQueue (the SynchronousJobQueue test double used elsewhere
can't catch this, since it never actually runs concurrently). Fixed by
`expire_on_commit=False` in db/base.py; this test exercises the real queue
so a regression of that setting would fail here, not just in production.
"""
from __future__ import annotations

from backend.app.domain.schemas import RepoRead
from backend.app.jobs.in_process_job_queue import InProcessJobQueue
from backend.app.services.repo_service import connect_repo


def test_connect_repo_result_survives_concurrent_indexing(
    session_factory, graph_repo, test_settings, fixture_repo,
):
    queue = InProcessJobQueue(max_workers=1)
    try:
        for _ in range(10):
            session = session_factory()
            repo, job = connect_repo(
                url=str(fixture_repo), session=session, session_factory=session_factory,
                graph_repo=graph_repo, job_queue=queue, settings=test_settings,
            )
            # Serializing immediately after enqueue is exactly what the API
            # route does, and is where the race manifested.
            read = RepoRead.model_validate(repo)
            assert read.id == repo.id
            assert read.url == str(fixture_repo)
    finally:
        queue.shutdown()

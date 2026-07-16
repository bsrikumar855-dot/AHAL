"""Runs one indexing job: clone -> ahal.extract.* -> GraphRepository.save.

This wraps the existing, tested `ahal` engine (no new graph-building logic
lives here) and fails closed: any exception during cloning or extraction is
recorded as a failed IndexJob rather than left to crash the worker thread or
leave a Repo stuck in "indexing" forever — the same fail-closed discipline
the whitepaper requires of model calls (Section 3.9), applied here to the
indexing pipeline.
"""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ahal.extract import build_cochange_index, build_structural_graph

from backend.app.config import Settings
from backend.app.db.models import RepoStatus
from backend.app.graph.graph_repository import GraphRepository
from backend.app.repositories.index_job_repository import IndexJobRepository
from backend.app.repositories.repo_repository import RepoRepository


def run_index_job(*, repo_id: str, job_id: str, url: str, session: Session,
                   graph_repo: GraphRepository, settings: Settings) -> None:
    repos = RepoRepository(session)
    jobs = IndexJobRepository(session)

    repo = repos.get(repo_id)
    job = jobs.get(job_id)
    if repo is None or job is None:
        # Row vanished between enqueue and run (e.g. deleted mid-flight).
        return

    repos.set_status(repo, RepoStatus.INDEXING)
    jobs.mark_running(job)

    try:
        clone_dir = _clone(url, settings.clone_cache_dir / repo_id)
        graph = build_structural_graph(clone_dir)
        cochange = build_cochange_index(
            clone_dir,
            max_commits=settings.max_commits_to_index,
            max_files_per_commit=settings.max_files_per_commit,
        )
        summary = graph_repo.save_snapshot(repo_id, graph, cochange)
    except Exception as exc:
        jobs.mark_failed(job, error_message=_describe_failure(exc))
        repos.set_status(repo, RepoStatus.FAILED)
        return

    jobs.mark_succeeded(job, commits_processed=summary.commit_count)
    repos.record_graph_summary(
        repo,
        node_count=summary.node_count,
        edge_count=summary.edge_count,
        commit_count=summary.commit_count,
        indexed_at=datetime.now(timezone.utc),
    )


def _describe_failure(exc: Exception) -> str:
    """`str(CalledProcessError)` alone omits stderr -- the actual reason git
    failed -- which makes a failed job undiagnosable. Include it when
    present, so IndexJob.error_message is genuinely actionable."""
    stderr = getattr(exc, "stderr", None)
    if stderr:
        return f"{exc}: {stderr.strip()}"
    return str(exc)


def _clone(url: str, dest: Path) -> Path:
    """Clone `url` (a remote git URL or a local path) into `dest`, replacing
    any prior clone. Re-cloning fresh each run is simple and correct for
    Increment 1; incremental fetch is an optimization for later.

    `stdin=DEVNULL`: git never reads stdin here, and explicitly closing it
    avoids inheriting the parent's stdin handle -- on Windows that handle
    can be left invalid after other work in-process (e.g. a FastAPI
    TestClient's async lifecycle), which otherwise crashes Popen with
    'WinError 6: the handle is invalid'.
    """
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--quiet", url, str(dest)],
        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return dest

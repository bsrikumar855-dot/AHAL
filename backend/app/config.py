"""Runtime configuration.

Every tunable lives here, env-overridable via the `AHAL_` prefix, so nothing
downstream hardcodes a path, a limit, or a connection string. Defaults are
the lightweight local stack (SQLite, on-disk graph store) documented in
docs/architecture/decisions/0001-lightweight-local-infra.md; swapping to
Postgres/Neo4j later is a matter of overriding `database_url` /
`graph_store_dir`, not changing code.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DATA_DIR = REPO_ROOT / "backend" / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AHAL_", env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DATA_DIR / 'ahal_backend.db'}"
    graph_store_dir: Path = BACKEND_DATA_DIR / "graphs"
    clone_cache_dir: Path = BACKEND_DATA_DIR / "clones"

    # Mirrors ahal.extract.build_cochange_index's own defaults (Section 3.2,
    # 7): bound how much history and how large a commit we'll index, so one
    # pathological repo can't make indexing unbounded.
    max_commits_to_index: int = 2000
    max_files_per_commit: int = 50

    # Size of the in-process thread pool backing InProcessJobQueue. Indexing
    # is blocking (subprocess git + ast.parse), so this bounds how many
    # indexing jobs can run concurrently before later ones queue.
    index_worker_threads: int = 2


settings = Settings()

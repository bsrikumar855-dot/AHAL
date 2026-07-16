# ADR 0001: Lightweight local infra for Increment 1

## Status

Accepted — Increment 1 (backend skeleton). Superseded incrementally as each
piece of real infra becomes available (tracked in [`../../roadmap.md`](../../roadmap.md)).

## Context

The required architecture (per the engineering brief this increment
implements) calls for Postgres, Redis, and Neo4j. Docker isn't available in
the current development environment, and none of the three can run
natively here without it. The choice was either to block Increment 1 on
installing Docker, or to build the backend skeleton against lightweight
local equivalents sitting behind the same interfaces the real infra would
implement.

The user explicitly chose to defer the Docker decision ("skip docker part
now we'll continue this at end") rather than block on it.

## Decision

Increment 1 uses:

| Required (brief) | Increment 1 stand-in | Interface it sits behind |
|---|---|---|
| Postgres | SQLite (`backend/data/ahal_backend.db`) | SQLAlchemy session factory (`db/base.py`) |
| Redis + Celery | In-process `ThreadPoolExecutor` | `JobQueue` (`jobs/job_queue.py`) |
| Neo4j | One JSON file per repo (`backend/data/graphs/`) | `GraphRepository` (`graph/graph_repository.py`) |

Every stand-in is a complete implementation of the interface its real
counterpart will also implement — nothing in `services/` or `api/` imports
SQLite, `ThreadPoolExecutor`, or JSON-on-disk directly.

## Consequences

- **Positive:** Increment 1 runs and is fully testable with zero extra
  installs (`pip install -r backend/requirements.txt`, no Docker, no
  external services). The whole vertical slice — connect a repo, index it,
  query status — is provably working today.
- **Positive:** swapping any one piece later is additive: implement
  `Neo4jGraphRepository`/`CeleryJobQueue`, point `AHAL_DATABASE_URL` at
  Postgres, wire the new implementation into `api/v1/deps.py`. No changes
  to `services/`, `api/v1/repos.py`, or `ahal/`.
- **Negative:** SQLite doesn't preserve `tzinfo` on `DateTime` columns the
  way Postgres would (see `backend/tests/test_repo_repository.py`'s
  timestamp comparison) — a known, narrow limitation of this stand-in, not
  a design choice to carry forward.
- **Negative:** the in-process job queue does not survive a process
  restart (an in-flight indexing job is simply lost) and doesn't scale
  beyond one backend process. Acceptable for a single-developer increment;
  not acceptable once there's more than one backend instance or a
  customer-facing SLA.
- **Negative:** one JSON file per repo has no query capability beyond
  "load the whole snapshot" — fine for Increment 1 (which only reports
  node/edge/commit counts), insufficient once Increment 2 needs to query
  the graph directly from the API (e.g. "what does X depend on") without
  reconstructing it in Python first.

## Revisit when

Docker (or equivalent hosted Postgres/Redis/Neo4j) becomes available —
tracked as an open item in `../../roadmap.md`, not implicitly assumed to
happen "eventually."

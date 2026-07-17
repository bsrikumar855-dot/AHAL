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

| Required (brief) | Deployment / Real implementation | SQLite / Local stand-in | Interface it sits behind |
|---|---|---|---|
| Postgres (DB Metadata) | PostgreSQL (ORM models, connection dynamically configured via `AHAL_DATABASE_URL`) | SQLite (`backend/data/ahal_backend.db`) | SQLAlchemy session factory (`db/base.py`) |
| Postgres (Graph Storage) | PostgreSQL (`postgres_graph_repository.py` storing json-serialized payloads in `graph_snapshots` table) | One JSON file per repo (`backend/data/graphs/`) | `GraphRepository` (`graph/graph_repository.py`) |
| Redis + Celery | In-process `ThreadPoolExecutor` | In-process `ThreadPoolExecutor` | `JobQueue` (`jobs/job_queue.py`) |
| Neo4j (Graph Querying) | *Deferred* (Uses Python in-memory NetworkX graph processing for prediction/verification) | *Deferred* (Uses Python in-memory NetworkX graph processing for prediction/verification) | `GraphRepository` / `Predictor` |

Every implementation of `GraphRepository` sits behind the same interface—nothing in `services/` or `api/` imports specific repositories directly.

## Consequences

- **Positive:** Swapping SQLite for Postgres and JSON-files for database snapshot storage was achieved without changing the service orchestrator layer or the `ahal` engine boundary, proving the interface decoupling is sound.
- **Positive:** The system can be configured entirely via `AHAL_DATABASE_URL` to run locally with SQLite or deployed fully on Postgres (using the same ORM definitions).
- **Negative:** The in-process job queue does not survive a process restart (an in-flight indexing job is simply lost) and doesn't scale beyond one backend process. This remains an acceptable limitation for local running/development, flagged for future Celery transition.
- **Negative:** Full Neo4j graph queries are still deferred; graph snapshots are loaded in full from the database to instantiate memory graphs in Python.

## Revisit when

Docker full-stack environment or live cloud infrastructure becomes available—this ADR has been updated to reflect the transition of Postgres to real deployment status, leaving Redis/Celery/Neo4j as next-phase items.


# AHAL AI Backend — Increment 1

FastAPI service around the existing, tested `ahal/` engine. This increment
proves the productization path — connect a repository, index it, query its
status — end to end. It does **not** yet predict anything; see
[`../docs/roadmap.md`](../docs/roadmap.md) for what's built vs. planned.

## What's here

| Layer | Path | Role |
|---|---|---|
| API | `app/api/v1/repos.py` | HTTP concerns only: request/response shaping, status codes. |
| Services | `app/services/` | Orchestration: `repo_service` (connect a repo), `indexing_service` (run one index job). |
| Repositories | `app/repositories/` | Data access (Repository pattern) over `Repo`/`IndexJob` rows. |
| Graph | `app/graph/` | `GraphRepository` interface + its current NetworkX-on-disk implementation. |
| Jobs | `app/jobs/` | `JobQueue` interface + its current in-process (`ThreadPoolExecutor`) implementation. |
| DB | `app/db/` | SQLAlchemy models + session-factory construction. |

## Run it

From the **repo root** (not `backend/`) — `ahal` and `backend` are both
top-level packages, and `backend/app/config.py` resolves data paths relative
to the repo root:

```bash
pip install -r backend/requirements.txt networkx --break-system-packages

# start the API (SQLite + on-disk graph store by default, no other infra needed)
uvicorn backend.app.main:app --reload

# run the backend's own tests
pytest backend/tests -v

# run everything (ahal engine + backend)
pytest ahal/tests backend/tests -v
```

Then, e.g.:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/repos -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/psf/requests.git"}'
# -> {"repo": {"id": "...", "status": "pending", ...}, "job": {"id": "...", "status": "pending", ...}}

curl http://127.0.0.1:8000/api/v1/repos/<repo_id>
# poll until "status": "ready" -- node_count/edge_count/commit_count populate on success
```

## Configuration

All settings are env-overridable with an `AHAL_` prefix (see `app/config.py`
for the full list and defaults) — e.g. `AHAL_MAX_COMMITS_TO_INDEX=5000`.
Nothing is hardcoded in business logic.

| Setting | Default | Purpose |
|---|---|---|
| `AHAL_DATABASE_URL` | `sqlite:///backend/data/ahal_backend.db` | Repo/IndexJob metadata storage. |
| `AHAL_GRAPH_STORE_DIR` | `backend/data/graphs` | Where indexed graphs are persisted (one JSON file per repo id). |
| `AHAL_CLONE_CACHE_DIR` | `backend/data/clones` | Where repos are cloned for indexing. |
| `AHAL_MAX_COMMITS_TO_INDEX` | `2000` | Mirrors `ahal.extract`'s own default. |
| `AHAL_INDEX_WORKER_THREADS` | `2` | Size of the in-process indexing thread pool. |

## Honest status (per the whitepaper's own discipline)

- **SQLite, not Postgres; an in-process thread pool, not Celery+Redis; a
  JSON file per repo, not Neo4j.** This is a deliberate Increment 1 choice
  (Docker isn't available in the current dev environment), not a permanent
  architecture decision — see
  [`../docs/architecture/decisions/0001-lightweight-local-infra.md`](../docs/architecture/decisions/0001-lightweight-local-infra.md).
  Every one of these sits behind an interface (`GraphRepository`,
  `JobQueue`) specifically so the swap is a config/implementation change,
  not a rewrite of `services/` or `api/`.
- **"Connect a repository" clones a git URL directly** — no GitHub
  OAuth/App integration yet. That's required once PR-triggered indexing or
  prediction exists; nothing in Increment 1 needs it yet.
- **No auth, RBAC, rate-limiting, or audit logs.** There's no multi-tenant
  surface or webhook to protect yet; building these now would be unused
  code. Required before any public/multi-tenant deployment — tracked in
  `../docs/roadmap.md`.
- **No prediction endpoint.** Increment 1 indexes; it doesn't yet wrap
  `ahal.predictor`/`ahal.verifier` behind an API. That's Increment 2.

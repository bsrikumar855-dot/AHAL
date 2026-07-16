# Architecture Overview

AHAL AI's source of truth is the whitepaper (`AHALfinal_Whitepaper.pdf`).
This document maps its architecture (§3) onto what actually exists in this
repository today versus what's planned, so the two never silently drift
apart (§5.6, Specification-implementation drift, is the failure mode this
document exists to prevent).

## Whitepaper layers vs. this repo

| Whitepaper layer (§3) | Status | Where |
|---|---|---|
| Prediction Engine (§3.2) — structural + co-change graph, verification-before-surfacing | **Built** | [`ahal/`](../../ahal/README.md): `verifier.py`, `ground_truth.py`, `predictor.py`, `extract.py` |
| Backtester + calibration (§6, §5.3) | **Built** | `ahal/backtest.py`, `ahal/calibration.py` |
| Productized access: connect a repo, index it, query status | **Built (Increment 1)** | [`backend/`](../../backend/README.md) |
| Prediction API (wraps `ahal.predictor` + `ahal.verifier` behind HTTP) | Not built | Increment 2 |
| Web UI | Not built | Increment 3 |
| Outcome Store (§3.5) | Not built | Increment 4+ |
| Engineering Flight Recorder (§3.7) | Not built | After Outcome Store exists — it's a query layer over it, not new inputs |
| Diagnosis Engine (§3.3, Stage 2) | Not built — gated on Stage 1 accuracy per §4 | — |
| Action Layer (§3.4, Stages 3–4) | Not built — gated on Stage 2/3 accuracy per §4 | — |

## Layering within `backend/` (Increment 1)

```
API (api/v1/)         <- HTTP concerns only: request/response shaping, status codes
   |
Services (services/)  <- orchestration: repo_service, indexing_service
   |
Repositories (repositories/, graph/, jobs/)  <- persistence + infra, behind interfaces
   |
ahal/                  <- pure computation: graphs, verification, extraction (untouched)
```

Each seam exists so a layer can be swapped without the layers around it
noticing:

- `GraphRepository` (`graph/graph_repository.py`): NetworkX-on-disk today,
  Neo4j in Increment 2.
- `JobQueue` (`jobs/job_queue.py`): in-process `ThreadPoolExecutor` today,
  Celery+Redis once available.
- `db/base.py`'s session factory: SQLite today, Postgres via
  `AHAL_DATABASE_URL` later — the repositories layer doesn't know which.

See [`decisions/0001-lightweight-local-infra.md`](decisions/0001-lightweight-local-infra.md)
for why these three specifically are stand-ins right now, and
[`../roadmap.md`](../roadmap.md) for when each gets replaced.

## The one guarantee that must never move

`ahal/verifier.py`'s verification-before-surfacing (§3.2, §3.8) is the
system's central, provable guarantee: a prediction surfaces only if its
basis resolves to a real graph edge or a real co-change count. Every layer
built around it — indexing, persistence, the eventual prediction API — sits
strictly downstream and must never become a second path for an unverified
prediction to reach a user. `ahal/tests/test_verifier.py` is the compliance
check for this; it has not been modified by any increment and should never
need to be to add a feature elsewhere in the stack.

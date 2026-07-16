# API: Repos (Increment 1)

Base path: `/api/v1/repos`. All bodies are JSON.

## `POST /api/v1/repos`

Connect a repository and start indexing it.

**Request**
```json
{ "url": "https://github.com/psf/requests.git" }
```
`url` may be a remote git URL or a local filesystem path (the latter is
mainly useful for tests and local development). Increment 1 clones
directly — see
[`../architecture/decisions/0001-lightweight-local-infra.md`](../architecture/decisions/0001-lightweight-local-infra.md)
and `../roadmap.md` for why there's no GitHub OAuth/App flow yet.

**Response — `201 Created`**
```json
{
  "repo": {
    "id": "b3f2...", "url": "...", "name": "psf/requests",
    "status": "pending", "created_at": "...", "updated_at": "...",
    "last_indexed_at": null, "node_count": 0, "edge_count": 0, "commit_count": 0
  },
  "job": {
    "id": "9a1c...", "repo_id": "b3f2...", "status": "pending",
    "started_at": null, "finished_at": null, "error_message": null,
    "commits_processed": 0
  }
}
```
Indexing runs in the background; poll `GET /repos/{id}` or
`GET /repos/{id}/jobs/{job_id}` for progress.

## `GET /api/v1/repos`

List all connected repos, most-recently-connected first.

**Response — `200 OK`** — a JSON array of the same `repo` object shape shown above.

## `GET /api/v1/repos/{repo_id}`

Repo detail, including its graph summary once indexing succeeds.

**Response — `200 OK`** — the `repo` object shape above. `status` is one of
`pending | indexing | ready | failed`. `node_count`/`edge_count`/`commit_count`
are populated once `status == "ready"`.

**Response — `404 Not Found`** if `repo_id` doesn't exist:
```json
{ "detail": "repo not found: <repo_id>" }
```

## `GET /api/v1/repos/{repo_id}/jobs/{job_id}`

Status of one indexing run.

**Response — `200 OK`**
```json
{
  "id": "9a1c...", "repo_id": "b3f2...", "status": "succeeded",
  "started_at": "...", "finished_at": "...", "error_message": null,
  "commits_processed": 214
}
```
`status` is one of `pending | running | succeeded | failed`. If `failed`,
`error_message` explains why (e.g. a clone failure).

**Response — `404 Not Found`** if `job_id` doesn't exist, or belongs to a
different repo than `repo_id`.

## Not yet available

`POST /predict` (blast-radius prediction against an indexed repo) is
Increment 2 — see [`../roadmap.md`](../roadmap.md). There is currently no
way to query the indexed graph directly through the API; only its summary
counts.

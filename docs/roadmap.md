# Roadmap

Two axes matter here and shouldn't be conflated: the whitepaper's **staged
trust model** (§4 — what access/authority the system has been empirically
granted) and this repo's **build increments** (how the engineering work is
sequenced). Everything built so far is entirely within whitepaper **Stage
1** (read-only: source, VCS, CI — no telemetry, no write access). Stages
2–4 are not started; per §4 they're gated on empirically validated
performance of the prior stage, not on elapsed engineering time.

## Build increments

### Increment 1 — Backend skeleton (done)

Connect a repo (git URL), index it with the existing `ahal` engine
(structural graph + co-change index), persist it, query status. No
prediction, no UI. See
[`architecture/decisions/0001-lightweight-local-infra.md`](architecture/decisions/0001-lightweight-local-infra.md)
for the SQLite/in-process-queue/JSON-graph stand-ins used in place of
Postgres/Redis+Celery/Neo4j (Docker wasn't available; revisit when it is).

### Increment 2 — Prediction API (next)

Wrap `ahal.predictor.Predictor` + `ahal.verifier.Verifier` behind
`POST /predict` for an indexed repo, given a set of changed files. This is
where the whitepaper's Prediction Agent / Evidence Agent split (propose vs.
verify) actually earns its own service boundary — Increment 1 doesn't need
it because indexing has no propose/verify split. Likely also where
`Neo4jGraphRepository` replaces the on-disk stand-in, since a prediction
needs to query the graph directly rather than reconstruct it in Python each
time.

### Increment 3 — Web UI

Next.js frontend: connect-repo flow, repo/job status, prediction results
with evidence (per §3.2's "stated basis for that score" requirement —
this is a UI *requirement*, not a nice-to-have, since an unexplained
confidence number is exactly what §3.2/§5.4 warn against surfacing).

### Increment 4 — Backtesting as a product surface

Wrap `ahal.backtest.run_backtest` (already includes per-repo calibration,
§5.3/§6) behind an API + UI so "backtest this repo's own history" — the
whitepaper's literal Stage 1 gating criterion (§3.9's table: *"Backtested
prediction accuracy on customer's own merge history exceeds an agreed
threshold"*) — is something a user can run and see, not just a CLI script.

### Later increments (not scoped yet)

Celery+Redis replacing the in-process job queue; Postgres replacing SQLite;
GitHub App + webhooks replacing direct-URL connection (needed once indexing
or prediction should trigger automatically on a PR); auth/RBAC/rate-limiting/
audit logs (needed once there's a multi-tenant surface or a webhook to
protect — building them earlier would be unused code against a
single-user local skeleton).

## Whitepaper stages (§4) — not started

| Stage | Capability | Gate to advance (§4) |
|---|---|---|
| 2 — Diagnosis | Production-linked diagnosis (read-only telemetry/alerting) | Demonstrated reduction in time-to-causal-identification over a trial period |
| 3 — Action | Reversible action (feature flags only) | A defined run of human-approved suggested actions with zero incorrect autonomous recommendations |
| 4 — Deployment remediation | Revert-to-known-good only | Sustained accuracy and safe operation at Stage 3 over an agreed observation period |

None of these have code, even as stubs, in this repo yet. Per the
engineering brief's own rule ("if later-stage code is required, create
interfaces only") — nothing in Increments 1–4 above currently *requires*
a Diagnosis Engine or Action Layer interface to exist, so none has been
added. One gets added the increment something concretely depends on it,
not preemptively.

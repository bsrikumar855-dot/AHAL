# AHAL AI — Stage 1 prototype

Change-impact prediction with **verification-before-surfacing**, plus a
Section 6 backtester. This is the whitepaper's Stage 1 MVP: read-only, no
telemetry, no write access. It proves value by backtesting against a repo's
own git history.

## What's here

| Module | Whitepaper section | Role |
|---|---|---|
| `ahal/verifier.py` | 3.2, 3.8 | **The central guarantee.** A prediction surfaces iff its basis resolves to real graph/history data. Deterministic, no model calls. |
| `ahal/ground_truth.py` | 3.2 | Structural dependency graph + co-change frequency index — the facts the verifier queries. |
| `ahal/types.py` | 3.2 | Prediction / Basis / Verdict types. A basis is a *checkable claim*, not a vibe. |
| `ahal/extract.py` | 3.2, 7 | Builds ground truth from a real repo (Python imports + `git log`). |
| `ahal/predictor.py` | 3.2, 3.9 | No-generative predictor: proposes candidate bases, runs each through the verifier. |
| `ahal/backtest.py` | 6 | Chronological replay, no look-ahead. Reports precision, recall, **calibration**. |
| `tests/test_verifier.py` | 3.2, 3.8, 5.4, 5.6 | 16 tests proving the guarantee, incl. adversarial cases. |

## The guarantee (why it's provable)

The verifier contains no model calls and no randomness. For a fixed
(prediction, ground truth) it always returns the same verdict. A prediction
is **surfaced** only if:

- a **structural** basis resolves to a real dependency path within the claimed
  hops, or
- a **co-change** basis resolves to a real co-change count ≥ the claimed count.

Anything else is **dropped** — never forwarded to a second model. This is why
an "LLM-judges-LLM" critic does *not* satisfy the spec (§3.8): it shares the
ungrounded failure mode. The test `test_score_never_influences_verdict`
proves a 0.99-confidence false claim is still dropped.

## Run it

```bash
pip install networkx pytest --break-system-packages

# prove the verification guarantee
python -m pytest tests/ -v

# backtest against any git repo (produces the Stage 1 deliverable)
python run_backtest.py /path/to/some/repo --commits 300
```

## Honest status (per the whitepaper's own discipline)

- These are **proposed-protocol** outputs, not validated results.
- Raw confidence scores are **not yet per-repo calibrated** — the first
  backtest on `psf/requests` showed clear miscalibration (10% actual hit rate
  in the 40–50% band). Fixing this via per-repo calibration is the immediate
  next task and is exactly what §5.3/§6 require before any customer-facing
  accuracy claim.
- Structural extraction is Python-imports-only. Infra/config dependencies are
  an open problem (§7), not silently faked.

## Not built yet (by design — gated stages)

Stage 2 (diagnosis), Stage 3 (feature-flag action), Stage 4 (deploy revert),
and the self-limiting Action Layer. Each is gated on empirical performance of
the prior stage. Stage 1 ships and proves first.

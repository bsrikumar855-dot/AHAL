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
| `ahal/backtest.py` | 6 | Chronological replay, no look-ahead. Reports precision, recall, **calibration**, split fit/eval. |
| `ahal/calibration.py` | 5.3, 6 | `Calibrator`: isotonic regression from raw score → per-repo empirical hit rate. Monotonic by construction — never inverts the raw score's ranking. sklearn if available, dependency-free PAVA fallback otherwise. |
| `ahal/tests/test_verifier.py` | 3.2, 3.8, 5.4, 5.6 | 16 tests proving the verification guarantee, incl. adversarial cases. |
| `ahal/tests/test_calibration.py` | 5.3, 6 | 7 tests proving calibration is monotonic, measurably reduces calibration error on a known-miscalibrated synthetic repo, and fails closed on degenerate data. |

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
# optional: pip install scikit-learn --break-system-packages
# (calibration.py works without it via a dependency-free PAVA fallback)

# prove the verification guarantee + calibration guarantees
python -m pytest ahal/tests -v

# backtest against any git repo (produces the Stage 1 deliverable,
# including the calibrated confidence table)
python run_backtest.py /path/to/some/repo --commits 300
```

## Calibration: per-repo, fit/eval split (§5.3, §6)

Raw predictor scores are a ranking signal, not a probability: the first
backtest on `psf/requests` showed clear miscalibration (10% actual hit rate
in the 40–50% band, vs. ~58% actual in the 70–80% band). `ahal/backtest.py`
now fits a `Calibrator` (`ahal/calibration.py`, isotonic regression) per
repo, directly from that repo's own backtest outcomes, and the report shows
raw vs. calibrated confidence side by side — fulfilling §5.3/§6's
requirement that confidence scores be calibrated per-repository via
backtesting before being treated as meaningful.

To avoid grading the calibrator on the data it was trained on (optimistic/
leaky), the chronologically-ordered replayed commits are split 70/30: the
calibrator is **fit** only on the earliest 70% of commits' outcomes, and
**both** the raw and calibrated calibration tables in the report are
computed only on the held-out, most-recent 30%. The report states this
split explicitly on every run.

## Honest status (per the whitepaper's own discipline)

- These are **proposed-protocol** outputs, not validated results.
- Raw confidence scores are now **per-repo calibrated** via backtesting
  (§5.3/§6) — see "Calibration" above. Calibration quality still depends on
  having enough held-out eval commits per confidence band; sparse bands fall
  back to the identity map rather than overfitting a handful of points.
- Structural extraction is Python-imports-only. Infra/config dependencies are
  an open problem (§7), not silently faked.

## Not built yet (by design — gated stages)

Stage 2 (diagnosis), Stage 3 (feature-flag action), Stage 4 (deploy revert),
and the self-limiting Action Layer. Each is gated on empirical performance of
the prior stage. Stage 1 ships and proves first.

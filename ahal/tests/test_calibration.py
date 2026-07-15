"""Proof-by-test for per-repo score calibration (Whitepaper Sections 5.3, 6).

Three properties matter for `Calibrator`, matching the guarantees claimed in
`ahal/calibration.py`:

1. `calibrate` never inverts the ranking the raw score already gets right
   (monotonic non-decreasing), tested as a property across random data.
2. On a repo where raw scores are a known amount miscalibrated, calibration
   measurably closes the gap to the true empirical hit rate.
3. Degenerate inputs (empty / single-point / single-raw-score datasets) fail
   closed to the identity map instead of crashing or producing nonsense.
"""
from __future__ import annotations

import random

from ahal.calibration import Calibrator


# ---------------------------------------------------------------------------
# 1. Monotonicity: calibration must never invert the raw-score ranking.
# ---------------------------------------------------------------------------
def test_calibrate_is_monotonic_non_decreasing():
    rng = random.Random(1234)
    # Noisy, non-monotonic-looking training data on purpose: isotonic
    # regression must still produce a monotonic *output* map.
    pairs = [(rng.random(), rng.random() < rng.random()) for _ in range(500)]
    cal = Calibrator().fit(pairs)

    probes = sorted(rng.random() for _ in range(300))
    calibrated = [cal.calibrate(x) for x in probes]
    for a, b in zip(calibrated, calibrated[1:]):
        assert a <= b + 1e-9


def test_calibrate_is_monotonic_across_many_random_fits():
    # Same property, but re-derived across several independently-seeded
    # fits so the guarantee isn't an artifact of one particular dataset.
    for seed in range(10):
        rng = random.Random(seed)
        pairs = [(rng.random(), rng.random() < 0.5) for _ in range(200)]
        cal = Calibrator().fit(pairs)
        probes = sorted(rng.random() for _ in range(50))
        calibrated = [cal.calibrate(x) for x in probes]
        for a, b in zip(calibrated, calibrated[1:]):
            assert a <= b + 1e-9


# ---------------------------------------------------------------------------
# 2. Calibration measurably improves on a known, synthetically miscalibrated
#    repo: raw score claims 2x the true hit probability.
# ---------------------------------------------------------------------------
def _mean_abs_calibration_error(samples, predicted_fn, n_buckets=10):
    """Bucket samples by raw score into `n_buckets` equal-width bands; for
    each non-empty bucket compare the mean predicted confidence against the
    actual empirical hit rate. Average the per-bucket absolute error."""
    buckets: dict[int, list[tuple[float, bool]]] = {}
    for raw, hit in samples:
        b = min(int(raw * n_buckets), n_buckets - 1)
        buckets.setdefault(b, []).append((raw, hit))

    errors = []
    for members in buckets.values():
        actual_rate = sum(1 for _, hit in members if hit) / len(members)
        predicted = sum(predicted_fn(raw) for raw, _ in members) / len(members)
        errors.append(abs(predicted - actual_rate))
    return sum(errors) / len(errors)


def test_calibration_reduces_error_on_known_miscalibration():
    rng = random.Random(42)
    # Raw score is uniformly 2x too confident: it claims probability
    # `raw`, but the true hit probability is only `raw / 2`.
    samples = []
    for _ in range(4000):
        raw = rng.random()
        true_prob = raw / 2.0
        hit = rng.random() < true_prob
        samples.append((raw, hit))

    cal = Calibrator().fit(samples)

    raw_error = _mean_abs_calibration_error(samples, predicted_fn=lambda r: r)
    calibrated_error = _mean_abs_calibration_error(
        samples, predicted_fn=cal.calibrate
    )

    assert calibrated_error < raw_error
    # Not just marginally better -- the raw score is off by a known, large,
    # constant factor, so calibration should close most of the gap.
    assert calibrated_error < raw_error * 0.5


# ---------------------------------------------------------------------------
# 3. Degenerate inputs fail closed to the identity map.
# ---------------------------------------------------------------------------
def test_empty_dataset_fails_closed_to_identity():
    cal = Calibrator().fit([])
    assert cal.is_identity
    for x in (0.0, 0.13, 0.5, 0.87, 1.0):
        assert cal.calibrate(x) == x


def test_single_point_dataset_fails_closed_to_identity():
    cal = Calibrator().fit([(0.73, True)])
    assert cal.is_identity
    for x in (0.0, 0.4, 1.0):
        assert cal.calibrate(x) == x


def test_single_distinct_raw_score_fails_closed_to_identity():
    # Multiple observations, but all at the same raw score: no basis for a
    # monotonic *mapping*, so this must not crash or degenerate into a
    # constant-output calibrator either.
    cal = Calibrator().fit([(0.5, True), (0.5, False), (0.5, True)])
    assert cal.is_identity
    assert cal.calibrate(0.2) == 0.2
    assert cal.calibrate(0.9) == 0.9


def test_calibrate_never_raises_and_stays_in_unit_interval():
    rng = random.Random(7)
    pairs = [(rng.random(), rng.random() < 0.3) for _ in range(50)]
    cal = Calibrator().fit(pairs)
    for x in (0.0, 1.0, 0.5, -0.0):
        y = cal.calibrate(x)
        assert 0.0 <= y <= 1.0

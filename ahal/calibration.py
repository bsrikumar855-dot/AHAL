"""Per-repo score calibration (Whitepaper Sections 5.3, 6).

A prediction's raw score (from `predictor.py`) is a *ranking* signal, not a
calibrated probability -- Section 5.3 requires that confidence numbers be
made honest via backtesting before they are treated as a probability a user
can act on. The first backtest against psf/requests showed this gap directly:
the 40-50% raw-confidence band came true ~10% of the time, while the 70-80%
band came true ~58%. Same model, wildly different reliability by band.

`Calibrator` fixes this with isotonic regression: it learns a monotonic
non-decreasing map from raw score -> empirical hit rate, fit on
(raw_score, was_correct) pairs from a backtest. Monotonic is not a nice-to-
have here -- it is the constraint that keeps calibration from ever
inverting the ranking the raw score already gets right (Section 6). A
calibrator that let a lower raw score end up with a higher calibrated
probability than a higher one would undo the one thing the predictor is
demonstrably good at.

Like verifier.py, this module is a pure, deterministic transform: no model
calls, no randomness, same input always produces the same output. It also
sits strictly downstream of the verifier -- it only ever rescales the score
of a prediction that has ALREADY been surfaced. It is not a second gate and
must never be used to let an unverified prediction through.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from typing import Sequence

try:
    from sklearn.isotonic import IsotonicRegression
    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in sklearn-less environments
    _SKLEARN_AVAILABLE = False


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


class _PAVAIsotonic:
    """Dependency-free isotonic regression via pool-adjacent-violators.

    Used only when sklearn is unavailable. Produces the same shape of fit as
    sklearn.isotonic.IsotonicRegression(out_of_bounds="clip"): a sorted set
    of unique x thresholds with monotonic non-decreasing y values, queried
    by linear interpolation between neighboring thresholds and clipped at
    the ends.
    """

    def __init__(self) -> None:
        self.x_thresholds: list[float] = []
        self.y_thresholds: list[float] = []

    def fit(self, xs: Sequence[float], ys: Sequence[float]) -> "_PAVAIsotonic":
        # Duplicate raw scores must map to one y before pooling, or PAVA's
        # "adjacent" notion is ambiguous.
        sums: dict[float, float] = defaultdict(float)
        counts: dict[float, int] = defaultdict(int)
        for x, y in zip(xs, ys):
            sums[x] += y
            counts[x] += 1
        uniq_x = sorted(sums)
        means = [sums[x] / counts[x] for x in uniq_x]
        weights = [float(counts[x]) for x in uniq_x]

        # Stack of pooled blocks: [mean_value, total_weight, first_idx, last_idx].
        # Merge back-to-front whenever a block's mean would violate
        # non-decreasing order relative to its predecessor.
        blocks: list[list[float]] = []
        for i, (v, w) in enumerate(zip(means, weights)):
            blocks.append([v, w, i, i])
            while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
                v2, w2, _s2, e2 = blocks.pop()
                v1, w1, s1, _e1 = blocks.pop()
                merged_v = (v1 * w1 + v2 * w2) / (w1 + w2)
                blocks.append([merged_v, w1 + w2, s1, e2])

        fitted = [0.0] * len(uniq_x)
        for v, _w, start, end in blocks:
            for idx in range(start, end + 1):
                fitted[idx] = v

        self.x_thresholds = uniq_x
        self.y_thresholds = fitted
        return self

    def predict_one(self, x: float) -> float:
        xs, ys = self.x_thresholds, self.y_thresholds
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = bisect_right(xs, x) - 1
        i = max(0, min(i, len(xs) - 2))
        x0, x1 = xs[i], xs[i + 1]
        y0, y1 = ys[i], ys[i + 1]
        if x1 == x0:
            return y0
        t = (x - x0) / (x1 - x0)
        return y0 + t * (y1 - y0)


class Calibrator:
    """Maps raw prediction scores to per-repo calibrated probabilities.

    Fit once from backtest outcomes (`fit`), then used at prediction time via
    `calibrate`. Isotonic regression guarantees `calibrate` is monotonic
    non-decreasing in the raw score -- see the module docstring for why that
    guarantee is non-negotiable (Section 6).
    """

    def __init__(self) -> None:
        self._identity = True
        self._n = 0
        self._model: IsotonicRegression | _PAVAIsotonic | None = None

    @property
    def is_identity(self) -> bool:
        """True if `fit` had too little data and fell back to the identity map."""
        return self._identity

    @property
    def n_fit_points(self) -> int:
        return self._n

    def fit(self, pairs: Sequence[tuple[float, bool]]) -> "Calibrator":
        """Fit on (raw_score, was_correct) pairs from a backtest.

        Fails closed: an empty dataset, or one with fewer than two distinct
        raw scores, cannot support a monotonic fit, so `calibrate` falls
        back to the identity map (returns the raw score unchanged) rather
        than raising or producing a degenerate single-value calibrator.
        """
        self._n = len(pairs)
        xs = [float(p[0]) for p in pairs]
        ys = [1.0 if p[1] else 0.0 for p in pairs]

        if len(pairs) < 2 or len(set(xs)) < 2:
            self._identity = True
            self._model = None
            return self

        self._identity = False
        if _SKLEARN_AVAILABLE:
            model = IsotonicRegression(
                y_min=0.0, y_max=1.0, out_of_bounds="clip", increasing=True
            )
            model.fit(xs, ys)
            self._model = model
        else:
            self._model = _PAVAIsotonic().fit(xs, ys)
        return self

    def calibrate(self, raw_score: float) -> float:
        """Map a raw score to a calibrated probability in [0, 1].

        Monotonic non-decreasing in `raw_score` by construction (isotonic
        regression), so calibration can only rescale confidence, never
        reorder which prediction looks more likely than another.
        """
        if self._identity or self._model is None:
            return _clamp01(raw_score)
        if _SKLEARN_AVAILABLE and isinstance(self._model, IsotonicRegression):
            return _clamp01(float(self._model.predict([raw_score])[0]))
        return _clamp01(self._model.predict_one(raw_score))  # type: ignore[union-attr]

    def calibration_curve(self) -> list[tuple[float, float]]:
        """Return the fitted (raw_score, calibrated_probability) knot points.

        Used for reporting only -- e.g. rendering a calibration table. The
        identity fallback reports its two defining endpoints.
        """
        if self._identity or self._model is None:
            return [(0.0, 0.0), (1.0, 1.0)]
        if _SKLEARN_AVAILABLE and isinstance(self._model, IsotonicRegression):
            return list(zip(
                (float(x) for x in self._model.X_thresholds_),
                (float(y) for y in self._model.y_thresholds_),
            ))
        return list(zip(self._model.x_thresholds, self._model.y_thresholds))  # type: ignore[union-attr]

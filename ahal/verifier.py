"""Verification-before-surfacing (Whitepaper Sections 3.2, 3.8).

THE CENTRAL GUARANTEE
---------------------
A candidate prediction is surfaced to the user IF AND ONLY IF its basis
resolves to real ground-truth data:

  - a STRUCTURAL basis is surfaced iff the claimed dependency path actually
    exists in the structural graph within the claimed hop count;
  - a CO_CHANGE basis is surfaced iff the components actually co-changed at
    least the claimed number of times in version-control history.

Any basis that does not resolve is DROPPED. It is never forwarded to a second
model for review. This function contains no model calls and no randomness: for
a fixed (prediction, ground truth) it always returns the same verdict. That
determinism is what makes the guarantee provable rather than merely likely.

This module is intentionally dependency-light and side-effect-free.
"""
from __future__ import annotations

from .ground_truth import CoChangeIndex, StructuralGraph
from .types import (
    Basis,
    BasisKind,
    Prediction,
    VerificationResult,
    Verdict,
)


class Verifier:
    """Grounds a prediction's basis against deterministic ground truth."""

    def __init__(self, graph: StructuralGraph, cochange: CoChangeIndex) -> None:
        self._graph = graph
        self._cochange = cochange

    def verify(self, prediction: Prediction) -> VerificationResult:
        """Return SURFACED or DROPPED. Total function: never raises on a
        well-typed Prediction, never returns anything but a verdict."""
        basis = prediction.basis

        if basis.kind is BasisKind.CO_CHANGE:
            return self._verify_cochange(prediction)
        if basis.kind is BasisKind.STRUCTURAL:
            return self._verify_structural(prediction)

        # Unknown basis kind: fail closed (drop). Consistent with Section 3.9's
        # "fail toward suppressing the prediction" degradation rule.
        return VerificationResult(
            prediction=prediction,
            verdict=Verdict.DROPPED,
            reason=f"unknown basis kind: {basis.kind!r}",
        )

    # -- CO_CHANGE ---------------------------------------------------------
    def _verify_cochange(self, prediction: Prediction) -> VerificationResult:
        b = prediction.basis
        claimed = b.claimed_cochange_count
        if claimed is None or claimed < 1:
            return VerificationResult(
                prediction, Verdict.DROPPED,
                reason="co_change basis missing a positive claimed count",
            )
        actual = self._cochange.cochange_count(b.source, b.target)
        if actual >= claimed:
            return VerificationResult(
                prediction, Verdict.SURFACED,
                reason=(f"co-change confirmed: {b.source} & {b.target} "
                        f"changed together {actual} times (\u2265{claimed})"),
                resolved_value=actual,
            )
        return VerificationResult(
            prediction, Verdict.DROPPED,
            reason=(f"co-change claim not met: found {actual}, "
                    f"claimed \u2265{claimed}"),
            resolved_value=actual,
        )

    # -- STRUCTURAL --------------------------------------------------------
    def _verify_structural(self, prediction: Prediction) -> VerificationResult:
        b = prediction.basis
        max_hops = b.claimed_max_path_len
        if max_hops is None or max_hops < 1:
            return VerificationResult(
                prediction, Verdict.DROPPED,
                reason="structural basis missing a positive claimed path length",
            )
        if self._graph.reaches(b.source, b.target, max_hops):
            hops = self._graph.shortest_hops(b.source, b.target)
            return VerificationResult(
                prediction, Verdict.SURFACED,
                reason=(f"structural path confirmed: {b.source} -> {b.target} "
                        f"in {hops} hop(s) (\u2264{max_hops})"),
                resolved_value=hops,
            )
        return VerificationResult(
            prediction, Verdict.DROPPED,
            reason=(f"no structural path {b.source} -> {b.target} "
                    f"within {max_hops} hop(s)"),
        )

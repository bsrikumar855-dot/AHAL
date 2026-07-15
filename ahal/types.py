"""Core data types for AHAL Stage 1.

Deliberately small and explicit. The whole trust argument in the whitepaper
(Sections 3.2, 3.8) rests on a *basis* that is either grounded in real data or
dropped. So a prediction is not just a component + score; it is a claim whose
basis must resolve to a concrete, checkable fact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BasisKind(str, Enum):
    """The kind of ground-truth fact a prediction's basis claims to rest on.

    STRUCTURAL: "changed component structurally reaches target component"
        -> must resolve to a real edge/path in the structural dependency graph.
    CO_CHANGE:  "target changed together with a changed component historically"
        -> must resolve to a real, countable co-change frequency in VCS history.
    """
    STRUCTURAL = "structural"
    CO_CHANGE = "co_change"


@dataclass(frozen=True)
class Basis:
    """A concrete, checkable claim about why a component is predicted affected.

    This is the object the verifier grounds. If it does not resolve to real
    graph/history data, the prediction it belongs to is dropped (never passed
    to a second model for review -- see Section 3.2 / 3.8).
    """
    kind: BasisKind
    source: str          # a changed component named in the diff
    target: str          # the predicted-affected component
    # For CO_CHANGE: the minimum co-change count the basis claims exists.
    claimed_cochange_count: Optional[int] = None
    # For STRUCTURAL: the max path length the basis claims connects them.
    claimed_max_path_len: Optional[int] = None

    def describe(self) -> str:
        if self.kind is BasisKind.CO_CHANGE:
            n = self.claimed_cochange_count
            return (f"{self.target} co-changed with {self.source} "
                    f"in \u2265{n} prior commits")
        return (f"{self.target} structurally reachable from {self.source} "
                f"within {self.claimed_max_path_len} hop(s)")


@dataclass(frozen=True)
class Prediction:
    """A candidate prediction: a component, a score, and a *basis* to verify."""
    target: str
    score: float
    basis: Basis

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0,1], got {self.score}")


class Verdict(str, Enum):
    SURFACED = "surfaced"        # basis resolved to real data -> shown to user
    DROPPED = "dropped"          # basis did not resolve -> suppressed


@dataclass(frozen=True)
class VerificationResult:
    prediction: Prediction
    verdict: Verdict
    reason: str
    # The actual ground-truth value found, for auditability.
    resolved_value: Optional[int] = None

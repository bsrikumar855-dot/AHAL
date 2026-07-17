"""Interface for persisting a repo's structural + co-change graph.

This is the seam a future `Neo4jGraphRepository` implements (Increment 2,
see docs/architecture/decisions/0001-lightweight-local-infra.md). Everything
above this interface (services/indexing_service.py) is written against
`GraphRepository` only, never against a concrete backing store.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ahal.calibration import Calibrator
from ahal.ground_truth import CoChangeIndex, StructuralGraph


@dataclass(frozen=True)
class GraphSummary:
    node_count: int
    edge_count: int
    commit_count: int


class GraphRepository(Protocol):
    def save_snapshot(self, repo_id: str, graph: StructuralGraph,
                       cochange: CoChangeIndex) -> GraphSummary:
        """Persist a repo's graph + co-change index; return its summary."""
        ...

    def load_snapshot(self, repo_id: str) -> tuple[StructuralGraph, CoChangeIndex] | None:
        """Load a previously saved snapshot, or None if the repo hasn't
        been indexed (or the snapshot was never persisted)."""
        ...

    def summary(self, repo_id: str) -> GraphSummary | None:
        """Node/edge/commit counts for a saved snapshot, without requiring
        the caller to reconstruct the full graph."""
        ...

    def save_calibrator(self, repo_id: str, fit_pairs: list[tuple[float, bool]]) -> None:
        """Persist calibration fit pairs for a repo."""
        ...

    def load_calibrator(self, repo_id: str) -> Calibrator | None:
        """Load and reconstruct a Calibrator for a repo, if fit."""
        ...


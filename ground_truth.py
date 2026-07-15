"""Ground-truth data structures the verifier queries.

These are deterministic. No model calls, no learning. They represent the
"real edge in the structural graph" and "real, countable co-change frequency"
that the whitepaper (Section 3.2) requires a basis to resolve to.

Keeping them dead simple and pure is what makes the verifier provably correct:
the verifier's guarantee is only as strong as the ground truth being genuinely
ground truth (queried facts, not inferences).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

import networkx as nx


class StructuralGraph:
    """Directed graph of real code dependencies (A imports/calls B => A -> B).

    Built from static parsing. Edges are facts. `reaches` answers: is there a
    dependency path from `source` to `target` within `max_hops`? This is the
    deterministic query behind a STRUCTURAL basis.
    """

    def __init__(self) -> None:
        self._g = nx.DiGraph()

    def add_dependency(self, source: str, target: str) -> None:
        """Record that `source` structurally depends on `target`."""
        self._g.add_edge(source, target)

    def has_node(self, node: str) -> bool:
        return self._g.has_node(node)

    def reaches(self, source: str, target: str, max_hops: int) -> bool:
        """True iff a directed path source->...->target exists with length
        <= max_hops. Pure graph query; no heuristics."""
        if max_hops < 1:
            return False
        if not (self._g.has_node(source) and self._g.has_node(target)):
            return False
        if source == target:
            return False
        try:
            dist = nx.shortest_path_length(self._g, source, target)
        except nx.NetworkXNoPath:
            return False
        return dist <= max_hops

    def shortest_hops(self, source: str, target: str) -> int | None:
        try:
            return nx.shortest_path_length(self._g, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None


class CoChangeIndex:
    """Counts how often two components appeared in the same commit.

    This is a plain frequency table over version-control history. The query
    behind a CO_CHANGE basis: how many commits changed both A and B?
    """

    def __init__(self) -> None:
        self._pair_counts: dict[frozenset[str], int] = defaultdict(int)
        self._commit_count = 0

    def record_commit(self, changed: Iterable[str]) -> None:
        """Ingest one commit's set of changed components."""
        files = sorted(set(changed))
        self._commit_count += 1
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                self._pair_counts[frozenset((files[i], files[j]))] += 1

    def cochange_count(self, a: str, b: str) -> int:
        """Number of commits in which both a and b changed. Pure lookup."""
        if a == b:
            return 0
        return self._pair_counts[frozenset((a, b))]

    @property
    def total_commits(self) -> int:
        return self._commit_count

"""On-disk GraphRepository: one JSON file per repo id.

Stopgap for Neo4j. `ahal`'s StructuralGraph/CoChangeIndex already work and
are tested (ahal/tests/test_ground_truth.py); this only needs to survive a
process restart, using the public serialization contract added to
ahal/ground_truth.py (to_edges/from_edges, to_pairs/from_pairs) rather than
reaching into private attributes the way ahal/predictor.py does internally.
"""
from __future__ import annotations

import json
from pathlib import Path

from ahal.ground_truth import CoChangeIndex, StructuralGraph

from backend.app.graph.graph_repository import GraphSummary


class NetworkXGraphRepository:
    def __init__(self, store_dir: Path) -> None:
        self._store_dir = store_dir
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, repo_id: str, graph: StructuralGraph,
                       cochange: CoChangeIndex) -> GraphSummary:
        edges = graph.to_edges()
        payload = {
            "edges": edges,
            "cochange_pairs": cochange.to_pairs(),
            "commit_count": cochange.total_commits,
        }
        self._path_for(repo_id).write_text(json.dumps(payload), encoding="utf-8")
        return self._summarize(edges, cochange.total_commits)

    def load_snapshot(self, repo_id: str) -> tuple[StructuralGraph, CoChangeIndex] | None:
        path = self._path_for(repo_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        graph = StructuralGraph.from_edges(tuple(edge) for edge in payload["edges"])
        cochange = CoChangeIndex.from_pairs(
            (tuple(pair) for pair in payload["cochange_pairs"]),
            commit_count=payload["commit_count"],
        )
        return graph, cochange

    def summary(self, repo_id: str) -> GraphSummary | None:
        snapshot = self.load_snapshot(repo_id)
        if snapshot is None:
            return None
        graph, cochange = snapshot
        return self._summarize(graph.to_edges(), cochange.total_commits)

    def _summarize(self, edges: list[tuple[str, str]], commit_count: int) -> GraphSummary:
        nodes = {node for edge in edges for node in edge}
        return GraphSummary(
            node_count=len(nodes), edge_count=len(edges), commit_count=commit_count)

    def _path_for(self, repo_id: str) -> Path:
        return self._store_dir / f"{repo_id}.json"

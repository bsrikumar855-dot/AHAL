"""Postgres-backed GraphRepository.

Saves structural graphs, co-change indices, and calibrators inside PostgreSQL
instead of local JSON files.
"""
from __future__ import annotations

import json
from sqlalchemy.orm import Session

from ahal.calibration import Calibrator
from ahal.ground_truth import CoChangeIndex, StructuralGraph

from backend.app.db.models import GraphSnapshot
from backend.app.graph.graph_repository import GraphSummary


class PostgresGraphRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_snapshot(self, repo_id: str, graph: StructuralGraph,
                       cochange: CoChangeIndex) -> GraphSummary:
        edges = graph.to_edges()
        snapshot = self._session.get(GraphSnapshot, repo_id)
        if snapshot is None:
            snapshot = GraphSnapshot(
                repo_id=repo_id,
                edges=json.dumps(edges),
                cochange_pairs=json.dumps(cochange.to_pairs()),
                commit_count=cochange.total_commits,
            )
            self._session.add(snapshot)
        else:
            snapshot.edges = json.dumps(edges)
            snapshot.cochange_pairs = json.dumps(cochange.to_pairs())
            snapshot.commit_count = cochange.total_commits
        self._session.commit()
        return self._summarize(edges, cochange.total_commits)

    def load_snapshot(self, repo_id: str) -> tuple[StructuralGraph, CoChangeIndex] | None:
        snapshot = self._session.get(GraphSnapshot, repo_id)
        if snapshot is None:
            return None
        edges = json.loads(snapshot.edges)
        cochange_pairs = json.loads(snapshot.cochange_pairs)
        commit_count = snapshot.commit_count

        graph = StructuralGraph.from_edges(tuple(edge) for edge in edges)
        cochange = CoChangeIndex.from_pairs(
            (tuple(pair) for pair in cochange_pairs),
            commit_count=commit_count,
        )
        return graph, cochange

    def summary(self, repo_id: str) -> GraphSummary | None:
        snapshot = self._session.get(GraphSnapshot, repo_id)
        if snapshot is None:
            return None
        edges = json.loads(snapshot.edges)
        return self._summarize(edges, snapshot.commit_count)

    def save_calibrator(self, repo_id: str, fit_pairs: list[tuple[float, bool]]) -> None:
        snapshot = self._session.get(GraphSnapshot, repo_id)
        if snapshot is not None:
            snapshot.calibration_fit_pairs = json.dumps(fit_pairs)
            self._session.commit()

    def load_calibrator(self, repo_id: str) -> Calibrator | None:
        snapshot = self._session.get(GraphSnapshot, repo_id)
        if snapshot is None or snapshot.calibration_fit_pairs is None:
            return None
        fit_pairs = json.loads(snapshot.calibration_fit_pairs)
        pairs = [(float(p[0]), bool(p[1])) for p in fit_pairs]
        return Calibrator().fit(pairs)

    def _summarize(self, edges: list[tuple[str, str]], commit_count: int) -> GraphSummary:
        nodes = {node for edge in edges for node in edge}
        return GraphSummary(
            node_count=len(nodes), edge_count=len(edges), commit_count=commit_count)

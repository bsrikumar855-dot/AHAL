"""Round-trip tests for StructuralGraph/CoChangeIndex serialization.

These methods exist so a persistence layer (e.g. a backend's GraphRepository)
has a public, stable snapshot format instead of reaching into `_g` /
`_pair_counts` directly. They are additive: no existing query method's
behavior changes.
"""
from __future__ import annotations

from ahal.ground_truth import CoChangeIndex, StructuralGraph


def test_structural_graph_edge_round_trip():
    g = StructuralGraph()
    g.add_dependency("A", "B")
    g.add_dependency("B", "C")

    restored = StructuralGraph.from_edges(g.to_edges())

    assert restored.reaches("A", "B", 1)
    assert restored.reaches("A", "C", 2)
    assert not restored.reaches("C", "A", 5)


def test_structural_graph_to_edges_matches_added_dependencies():
    g = StructuralGraph()
    g.add_dependency("A", "B")
    g.add_dependency("A", "C")

    assert set(g.to_edges()) == {("A", "B"), ("A", "C")}


def test_empty_structural_graph_round_trips():
    restored = StructuralGraph.from_edges([])
    assert restored.to_edges() == []
    assert not restored.has_node("anything")


def test_cochange_index_pair_round_trip():
    idx = CoChangeIndex()
    for _ in range(6):
        idx.record_commit(["A", "B"])
    for _ in range(2):
        idx.record_commit(["B", "C"])

    restored = CoChangeIndex.from_pairs(idx.to_pairs(), commit_count=idx.total_commits)

    assert restored.cochange_count("A", "B") == 6
    assert restored.cochange_count("B", "C") == 2
    assert restored.cochange_count("A", "C") == 0
    assert restored.total_commits == idx.total_commits


def test_cochange_index_to_pairs_is_order_independent_pair():
    idx = CoChangeIndex()
    idx.record_commit(["X", "Y"])

    pairs = idx.to_pairs()
    assert len(pairs) == 1
    a, b, count = pairs[0]
    assert {a, b} == {"X", "Y"}
    assert count == 1


def test_empty_cochange_index_round_trips():
    restored = CoChangeIndex.from_pairs([])
    assert restored.total_commits == 0
    assert restored.cochange_count("A", "B") == 0

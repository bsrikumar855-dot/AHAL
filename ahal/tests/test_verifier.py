"""Proof-by-test of the central verification guarantee.

Each test maps to a specific claim in the whitepaper. The naming makes the
mapping explicit so the suite doubles as a compliance check against Sections
3.2, 3.8, 5.4, and 5.6.
"""
import itertools

import pytest

from ahal.ground_truth import CoChangeIndex, StructuralGraph
from ahal.types import Basis, BasisKind, Prediction, Verdict
from ahal.verifier import Verifier


# ---------------------------------------------------------------------------
# Fixtures: a small, fully-known world.
#   Structural: A -> B -> C   (A depends on B depends on C); D is isolated.
#   History: (A,B) co-changed 6x; (B,C) 2x; (A,D) 4x but NO structural edge.
# ---------------------------------------------------------------------------
@pytest.fixture
def graph():
    g = StructuralGraph()
    g.add_dependency("A", "B")
    g.add_dependency("B", "C")
    g.add_dependency("D", "D_dep")  # keep D present but unrelated to A/B/C
    return g


@pytest.fixture
def cochange():
    c = CoChangeIndex()
    for _ in range(6):
        c.record_commit(["A", "B"])
    for _ in range(2):
        c.record_commit(["B", "C"])
    for _ in range(4):
        c.record_commit(["A", "D"])  # correlational only, no structure
    return c


@pytest.fixture
def verifier(graph, cochange):
    return Verifier(graph, cochange)


def _co(source, target, n, score=0.9):
    return Prediction(target, score,
                      Basis(BasisKind.CO_CHANGE, source, target,
                            claimed_cochange_count=n))


def _struct(source, target, hops, score=0.9):
    return Prediction(target, score,
                      Basis(BasisKind.STRUCTURAL, source, target,
                            claimed_max_path_len=hops))


# -- Core positive cases: real basis => surfaced (Section 3.2) ---------------
def test_true_cochange_is_surfaced(verifier):
    r = verifier.verify(_co("A", "B", 6))
    assert r.verdict is Verdict.SURFACED
    assert r.resolved_value == 6


def test_true_structural_path_is_surfaced(verifier):
    r = verifier.verify(_struct("A", "B", 1))
    assert r.verdict is Verdict.SURFACED
    assert r.resolved_value == 1


def test_transitive_structural_path_within_hops_is_surfaced(verifier):
    # A -> B -> C is 2 hops; claim allows 2.
    r = verifier.verify(_struct("A", "C", 2))
    assert r.verdict is Verdict.SURFACED
    assert r.resolved_value == 2


# -- THE ADVERSARIAL CASE the paper is built around (Section 5.6) ------------
def test_plausible_but_structurally_false_claim_is_dropped(verifier):
    """A confident, plausible-sounding claim with NO real path must be dropped.
    This is exactly the failure an LLM-judges-LLM critic would miss."""
    r = verifier.verify(_struct("A", "D", hops=3, score=0.99))
    assert r.verdict is Verdict.DROPPED  # no A->D path at any length


def test_stale_cochange_without_structure_can_be_gated(verifier):
    """A,D co-changed 4x historically but share no structural edge.
    The co-change basis alone WILL surface (it is a real count) -- but a
    *structural* basis over the same pair is correctly dropped. This encodes
    the Section 3.2 point: stale correlation is not laundered into a structural
    claim."""
    # Real co-change count -> honest co-change basis surfaces:
    assert verifier.verify(_co("A", "D", 4)).verdict is Verdict.SURFACED
    # But you cannot dress it up as a structural relationship:
    assert verifier.verify(_struct("A", "D", 5)).verdict is Verdict.DROPPED


# -- Core negative cases: inflated / fabricated basis => dropped -------------
def test_inflated_cochange_count_is_dropped(verifier):
    # Claims >=7 but only 6 real.
    r = verifier.verify(_co("A", "B", 7))
    assert r.verdict is Verdict.DROPPED
    assert r.resolved_value == 6


def test_fabricated_cochange_pair_is_dropped(verifier):
    r = verifier.verify(_co("A", "C", 1))  # A,C never co-changed
    assert r.verdict is Verdict.DROPPED
    assert r.resolved_value == 0


def test_path_beyond_claimed_hops_is_dropped(verifier):
    # A->C really is 2 hops, but claim only allows 1.
    r = verifier.verify(_struct("A", "C", 1))
    assert r.verdict is Verdict.DROPPED


def test_wrong_direction_structural_is_dropped(verifier):
    # Edges are directed: C does not reach A.
    r = verifier.verify(_struct("C", "A", 5))
    assert r.verdict is Verdict.DROPPED


def test_unknown_node_is_dropped(verifier):
    r = verifier.verify(_struct("A", "GHOST", 5))
    assert r.verdict is Verdict.DROPPED


# -- Fail-closed / robustness (Section 3.9 graceful degradation) -------------
def test_malformed_cochange_basis_fails_closed(verifier):
    bad = Prediction("B", 0.9, Basis(BasisKind.CO_CHANGE, "A", "B",
                                     claimed_cochange_count=None))
    assert verifier.verify(bad).verdict is Verdict.DROPPED


def test_zero_claim_fails_closed(verifier):
    bad = Prediction("B", 0.9, Basis(BasisKind.CO_CHANGE, "A", "B",
                                     claimed_cochange_count=0))
    assert verifier.verify(bad).verdict is Verdict.DROPPED


def test_self_reference_is_dropped(verifier):
    assert verifier.verify(_struct("A", "A", 3)).verdict is Verdict.DROPPED
    assert verifier.verify(_co("A", "A", 1)).verdict is Verdict.DROPPED


# -- Meta-properties: determinism & no side effects --------------------------
def test_verdict_is_deterministic(verifier):
    p = _struct("A", "C", 2)
    verdicts = {verifier.verify(p).verdict for _ in range(50)}
    assert len(verdicts) == 1  # identical every time


def test_score_never_influences_verdict(verifier):
    """A high score must NEVER rescue a false basis. This is the anti-
    'confident hallucination' property."""
    for score in (0.0, 0.5, 0.99, 1.0):
        false_claim = _struct("A", "D", 3, score=score)
        assert verifier.verify(false_claim).verdict is Verdict.DROPPED
    for score in (0.01, 0.5, 1.0):
        true_claim = _struct("A", "B", 1, score=score)
        assert verifier.verify(true_claim).verdict is Verdict.SURFACED


def test_surfacing_is_monotonic_in_evidence(cochange, graph):
    """If a claim of N co-changes surfaces, any claim of <=N also surfaces;
    if a claim of N is dropped, any claim of >=N is also dropped."""
    v = Verifier(graph, cochange)
    real = cochange.cochange_count("A", "B")  # 6
    for n in range(1, real + 1):
        assert v.verify(_co("A", "B", n)).verdict is Verdict.SURFACED
    for n in range(real + 1, real + 5):
        assert v.verify(_co("A", "B", n)).verdict is Verdict.DROPPED

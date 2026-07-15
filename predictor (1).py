"""Prediction Engine (Whitepaper Section 3.2), no-generative config.

Given a set of changed components (a diff), propose candidate affected
components from BOTH signals -- structural neighbors and historical co-change
partners -- attach a basis to each, and pass every candidate through the
Verifier. Only surfaced predictions are returned.

This is the "strictly more conservative, still-useful configuration" from
Section 3.9: structural + historical analysis only, no generative proposal.
Scores are simple, transparent, and per-repo calibratable (Section 6).
"""
from __future__ import annotations

from dataclasses import dataclass

from .ground_truth import CoChangeIndex, StructuralGraph
from .types import Basis, BasisKind, Prediction, Verdict
from .verifier import Verifier


@dataclass
class PredictorConfig:
    max_hops: int = 2                 # structural propagation depth
    min_cochange: int = 2             # ignore one-off coincidental co-changes
    max_candidates: int = 25          # conservative surfacing (Section 5.4)


class Predictor:
    def __init__(self, graph: StructuralGraph, cochange: CoChangeIndex,
                 config: PredictorConfig | None = None) -> None:
        self._graph = graph
        self._cochange = cochange
        self._verifier = Verifier(graph, cochange)
        self._cfg = config or PredictorConfig()

    def predict(self, changed: list[str]) -> list[Prediction]:
        """Return verified, ranked predictions for a set of changed files."""
        candidates: dict[str, Prediction] = {}

        for src in changed:
            # -- structural neighbours within max_hops
            for tgt in self._structural_neighbours(src):
                if tgt in changed:
                    continue
                hops = self._graph.shortest_hops(src, tgt)
                if hops is None:
                    continue
                score = 1.0 / (1.0 + hops)  # closer = higher
                self._offer(candidates, Prediction(
                    tgt, score,
                    Basis(BasisKind.STRUCTURAL, src, tgt,
                          claimed_max_path_len=hops)))

            # -- historical co-change partners
            for tgt, count in self._cochange_partners(src):
                if tgt in changed:
                    continue
                # normalise against how often src itself changed-ish:
                score = min(0.99, count / (count + 3.0))
                self._offer(candidates, Prediction(
                    tgt, score,
                    Basis(BasisKind.CO_CHANGE, src, tgt,
                          claimed_cochange_count=count)))

        surfaced = []
        for pred in candidates.values():
            if self._verifier.verify(pred).verdict is Verdict.SURFACED:
                surfaced.append(pred)
        surfaced.sort(key=lambda p: p.score, reverse=True)
        return surfaced[: self._cfg.max_candidates]

    def _offer(self, table: dict[str, Prediction], pred: Prediction) -> None:
        """Keep the highest-scoring basis per target component."""
        existing = table.get(pred.target)
        if existing is None or pred.score > existing.score:
            table[pred.target] = pred

    def _structural_neighbours(self, src: str) -> list[str]:
        out = []
        # who depends ON src (reverse) and what src depends on (forward),
        # both are plausible blast radius; we use forward reach here and let
        # the verifier confirm concrete paths.
        for node in self._graph_nodes():
            if node == src:
                continue
            if self._graph.reaches(src, node, self._cfg.max_hops) or \
               self._graph.reaches(node, src, self._cfg.max_hops):
                out.append(node)
        return out

    def _graph_nodes(self):
        # small helper; StructuralGraph wraps a private nx graph
        return list(self._graph._g.nodes())  # noqa: SLF001 (prototype)

    def _cochange_partners(self, src: str) -> list[tuple[str, int]]:
        partners = []
        for pair, count in self._cochange._pair_counts.items():  # noqa: SLF001
            if src in pair and count >= self._cfg.min_cochange:
                other = next(x for x in pair if x != src)
                partners.append((other, count))
        return partners

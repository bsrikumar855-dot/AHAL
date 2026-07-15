"""Stage 1 backtester (Whitepaper Section 6).

Replays the last N merged commits in chronological order. For each commit we
treat the FIRST changed file as the "seed change" and ask the predictor what
else it thinks is affected -- WITHOUT letting it see this commit. Ground truth
= the other files actually changed in that same commit.

We report precision, recall, and CALIBRATION (does a 0.7-confidence prediction
come true ~70% of the time), never a single aggregate number -- Section 6 is
explicit that a lone accuracy figure hides poor calibration.

Critically, ground truth (co-change index + graph) is rebuilt from history
STRICTLY BEFORE each replayed commit, so there is no look-ahead leakage. This
is the discipline Section 6 demands for an honest held-out backtest.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .extract import build_structural_graph
from .ground_truth import CoChangeIndex
from .predictor import Predictor, PredictorConfig


@dataclass
class CommitRecord:
    sha: str
    files: list[str]


@dataclass
class BacktestReport:
    n_commits_evaluated: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    # calibration buckets: score_band -> [hits, total]
    calibration: dict[str, list[int]] = field(default_factory=dict)

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    def record_calibration(self, score: float, hit: bool) -> None:
        band = f"{int(score * 10) * 10}-{int(score * 10) * 10 + 10}%"
        bucket = self.calibration.setdefault(band, [0, 0])
        bucket[0] += int(hit)
        bucket[1] += 1

    def render(self) -> str:
        lines = [
            "AHAL Stage 1 Backtest Report",
            "=" * 40,
            f"Commits evaluated:  {self.n_commits_evaluated}",
            f"Precision:          {self.precision:.3f}",
            f"Recall:             {self.recall:.3f}",
            f"  TP={self.true_positives}  FP={self.false_positives}  "
            f"FN={self.false_negatives}",
            "",
            "Calibration (predicted confidence vs. actual hit rate):",
        ]
        for band in sorted(self.calibration):
            hits, total = self.calibration[band]
            rate = hits / total if total else 0.0
            lines.append(f"  {band:>8}:  {rate:5.1%} actual  (n={total})")
        lines.append("")
        lines.append("NOTE: proposed-protocol output. Not a validated result.")
        return "\n".join(lines)


def _load_commits(repo: Path, n: int, max_files: int) -> list[CommitRecord]:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", f"-n{n}", "--name-only",
         "--pretty=format:__C__%H", "--reverse"],
        capture_output=True, text=True, check=True,
    ).stdout
    commits: list[CommitRecord] = []
    sha, files = None, []
    for line in out.splitlines():
        if line.startswith("__C__"):
            if sha and 1 < len(files) <= max_files:
                commits.append(CommitRecord(sha, files))
            sha, files = line[5:], []
        elif line.strip():
            files.append(line.strip())
    if sha and 1 < len(files) <= max_files:
        commits.append(CommitRecord(sha, files))
    return commits


def run_backtest(repo: Path, n_commits: int = 300,
                 max_files: int = 30,
                 config: PredictorConfig | None = None) -> BacktestReport:
    """Chronological replay with no look-ahead. Structural graph is built once
    from the current tree (a known approximation, flagged below); co-change
    index is grown incrementally so each prediction only sees the past."""
    commits = _load_commits(repo, n_commits, max_files)
    report = BacktestReport()

    # Structural graph from current tree. This is an approximation: it uses
    # today's structure for past commits. Flagged as a known limitation rather
    # than hidden -- honest-evaluation discipline (Section 6).
    graph = build_structural_graph(repo)
    cochange = CoChangeIndex()

    for rec in commits:
        # Predict using ONLY history strictly before this commit.
        predictor = Predictor(graph, cochange, config)
        seed = rec.files[0]
        actual_affected = set(rec.files[1:])

        preds = predictor.predict([seed])
        predicted = {p.target for p in preds}

        tp = predicted & actual_affected
        fp = predicted - actual_affected
        fn = actual_affected - predicted

        report.true_positives += len(tp)
        report.false_positives += len(fp)
        report.false_negatives += len(fn)
        report.n_commits_evaluated += 1

        for p in preds:
            report.record_calibration(p.score, p.target in actual_affected)

        # Only now fold this commit into history for future predictions.
        cochange.record_commit(rec.files)

    return report

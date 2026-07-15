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

CALIBRATION FIT/EVAL SPLIT (Section 5.3, Section 6)
----------------------------------------------------
Raw predictor scores are a ranking signal, not a calibrated probability (see
`calibration.py`). Fitting a `Calibrator` and then reporting its calibration
quality on the SAME (score, hit) pairs it was fit on is optimistic/leaky: an
isotonic fit can trivially match the data it was trained on, so that would
overstate how well calibration will hold up on the next commit. To keep this
honest, the chronologically-ordered commits are split into a FIT portion
(the earliest FIT_FRACTION of commits, whose outcomes train the
`Calibrator`) and a held-out EVAL portion (the most recent commits, whose
outcomes -- and ONLY whose outcomes -- populate both calibration tables in
the report). This mirrors the no-look-ahead discipline used for the graph
and co-change index, applied one level up: the calibrator itself must not
see the data it is graded on.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .calibration import Calibrator
from .extract import build_structural_graph
from .ground_truth import CoChangeIndex
from .predictor import Predictor, PredictorConfig

# Fraction of chronologically-earliest commits used to FIT the calibrator.
# The remaining (most recent) commits are held out for evaluation only.
FIT_FRACTION = 0.7


@dataclass
class CommitRecord:
    sha: str
    files: list[str]


def _band(score: float) -> str:
    """Bucket a [0,1] score into a 10-point confidence band label."""
    lo = min(int(score * 10), 9) * 10
    return f"{lo}-{lo + 10}%"


@dataclass
class BacktestReport:
    n_commits_evaluated: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    # Chronological fit/eval split accounting (see module docstring).
    fit_commit_count: int = 0
    eval_commit_count: int = 0
    fit_fraction: float = FIT_FRACTION
    calibrator_is_identity: bool = False
    calibrator_fit_points: int = 0

    # calibration buckets: score_band -> [hits, total]. Both tables are
    # computed on the held-out eval portion only.
    raw_calibration: dict[str, list[int]] = field(default_factory=dict)
    calibrated_calibration: dict[str, list[int]] = field(default_factory=dict)

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    def record_raw_calibration(self, score: float, hit: bool) -> None:
        """Bucket a held-out (raw_score, was_correct) outcome."""
        bucket = self.raw_calibration.setdefault(_band(score), [0, 0])
        bucket[0] += int(hit)
        bucket[1] += 1

    def record_calibrated_calibration(self, calibrated_score: float, hit: bool) -> None:
        """Bucket a held-out (calibrated_score, was_correct) outcome."""
        bucket = self.calibrated_calibration.setdefault(_band(calibrated_score), [0, 0])
        bucket[0] += int(hit)
        bucket[1] += 1

    @staticmethod
    def _render_calibration_table(buckets: dict[str, list[int]]) -> list[str]:
        lines = []
        for band in sorted(buckets):
            hits, total = buckets[band]
            rate = hits / total if total else 0.0
            lines.append(f"  {band:>8}:  {rate:5.1%} actual  (n={total})")
        if not buckets:
            lines.append("  (no held-out predictions to report)")
        return lines

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
            f"Calibration fit/eval split (Section 5.3/6): first "
            f"{self.fit_fraction:.0%} of commits ({self.fit_commit_count}) fit the "
            f"calibrator, last {1 - self.fit_fraction:.0%} "
            f"({self.eval_commit_count}) are held out. Both tables below are "
            f"computed on the held-out portion only -- the calibrator never sees "
            f"the commits it is graded on.",
            f"Calibrator: "
            f"{'identity fallback (insufficient fit data)' if self.calibrator_is_identity else 'fit isotonic regression'} "
            f"on {self.calibrator_fit_points} fit-portion prediction(s).",
            "",
            "RAW score vs. actual hit rate (held-out, uncalibrated):",
            *self._render_calibration_table(self.raw_calibration),
            "",
            "CALIBRATED probability vs. actual hit rate (held-out):",
            *self._render_calibration_table(self.calibrated_calibration),
            "",
            "NOTE: proposed-protocol output. Not a validated result.",
        ]
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
    index is grown incrementally so each prediction only sees the past.

    The chronological commit sequence is also split FIT_FRACTION/eval for
    calibration (see module docstring): the calibrator is fit only on the
    earliest commits' outcomes and graded only on the most recent commits'
    outcomes, so the reported calibration numbers are a genuine held-out
    estimate, not a fit-and-grade-on-the-same-data measurement.
    """
    commits = _load_commits(repo, n_commits, max_files)
    fit_cutoff = int(len(commits) * FIT_FRACTION)

    report = BacktestReport(
        fit_commit_count=fit_cutoff,
        eval_commit_count=len(commits) - fit_cutoff,
    )

    # Structural graph from current tree. This is an approximation: it uses
    # today's structure for past commits. Flagged as a known limitation rather
    # than hidden -- honest-evaluation discipline (Section 6).
    graph = build_structural_graph(repo)
    cochange = CoChangeIndex()

    fit_pairs: list[tuple[float, bool]] = []
    eval_pairs: list[tuple[float, bool]] = []

    for idx, rec in enumerate(commits):
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

        is_eval_commit = idx >= fit_cutoff
        for p in preds:
            hit = p.target in actual_affected
            if is_eval_commit:
                eval_pairs.append((p.score, hit))
                report.record_raw_calibration(p.score, hit)
            else:
                fit_pairs.append((p.score, hit))

        # Only now fold this commit into history for future predictions.
        cochange.record_commit(rec.files)

    calibrator = Calibrator().fit(fit_pairs)
    report.calibrator_is_identity = calibrator.is_identity
    report.calibrator_fit_points = len(fit_pairs)

    for score, hit in eval_pairs:
        report.record_calibrated_calibration(calibrator.calibrate(score), hit)

    return report

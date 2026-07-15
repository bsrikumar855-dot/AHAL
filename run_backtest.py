#!/usr/bin/env python3
"""AHAL Stage 1 CLI: run a change-impact backtest against any git repo.

Usage:
    python run_backtest.py /path/to/repo [--commits 300] [--hops 2] [--min-cochange 2]

Produces the Stage 1 deliverable described in the whitepaper (Section 4/6):
a backtest report against the repo's own historical merge data.
"""
import argparse
from pathlib import Path

from ahal.backtest import run_backtest
from ahal.predictor import PredictorConfig


def main() -> None:
    ap = argparse.ArgumentParser(description="AHAL Stage 1 backtest")
    ap.add_argument("repo", type=Path, help="path to a git repository")
    ap.add_argument("--commits", type=int, default=300)
    ap.add_argument("--hops", type=int, default=2)
    ap.add_argument("--min-cochange", type=int, default=2)
    args = ap.parse_args()

    if not (args.repo / ".git").exists():
        raise SystemExit(f"{args.repo} is not a git repository")

    report = run_backtest(
        args.repo,
        n_commits=args.commits,
        config=PredictorConfig(max_hops=args.hops,
                               min_cochange=args.min_cochange),
    )
    print(report.render())


if __name__ == "__main__":
    main()

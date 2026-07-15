"""Build ground truth from a real repository.

Two extractors, both deterministic:
  - build_cochange_index: mines `git log` for per-commit changed-file sets.
  - build_structural_graph: parses Python imports into dependency edges.

These are intentionally simple and language-limited (Python imports only) for
the Stage 1 prototype. The whitepaper flags infra/config dependencies as an
open problem (Section 7); we do NOT pretend to solve them here.
"""
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

from .ground_truth import CoChangeIndex, StructuralGraph


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def build_cochange_index(repo: Path, max_commits: int = 2000,
                         max_files_per_commit: int = 50) -> CoChangeIndex:
    """Mine commit history. Each commit contributes its set of changed files.

    Commits touching an implausibly large number of files (bulk reformats,
    vendored drops) are skipped above max_files_per_commit -- these inflate
    co-change counts spuriously (the monorepo commit-batching problem the
    paper names in Section 7).
    """
    idx = CoChangeIndex()
    log = _git(repo, "log", f"-n{max_commits}", "--name-only",
               "--pretty=format:__COMMIT__%n")
    changed: list[str] = []
    for line in log.splitlines():
        if line == "__COMMIT__":
            if 1 < len(changed) <= max_files_per_commit:
                idx.record_commit(changed)
            changed = []
        elif line.strip():
            changed.append(line.strip())
    if 1 < len(changed) <= max_files_per_commit:
        idx.record_commit(changed)
    return idx


def build_structural_graph(repo: Path) -> StructuralGraph:
    """Parse Python files, map imports to intra-repo dependency edges.

    An edge file_a -> file_b means file_a imports a module resolving to file_b
    inside this repo. External imports are ignored (not our components).
    """
    g = StructuralGraph()
    py_files = [p for p in repo.rglob("*.py")
                if ".git" not in p.parts]
    # Map importable module path -> repo-relative file, for resolution.
    module_to_file: dict[str, str] = {}
    for p in py_files:
        rel = p.relative_to(repo)
        mod = ".".join(rel.with_suffix("").parts)
        module_to_file[mod] = str(rel)
        # also register package form for __init__.py
        if p.name == "__init__.py":
            pkg = ".".join(rel.parent.parts)
            if pkg:
                module_to_file[pkg] = str(rel)

    for p in py_files:
        rel = str(p.relative_to(repo))
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                targets = [node.module]
            for t in targets:
                # resolve longest matching module prefix to a repo file
                resolved = _resolve(t, module_to_file)
                if resolved and resolved != rel:
                    g.add_dependency(rel, resolved)
    return g


def _resolve(module: str, module_to_file: dict[str, str]) -> str | None:
    parts = module.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in module_to_file:
            return module_to_file[prefix]
    return None

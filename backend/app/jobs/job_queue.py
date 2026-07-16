"""Interface for scheduling background work.

`enqueue` is the entire surface a future `CeleryJobQueue` needs to implement
once Redis is available (see docs/architecture/decisions/0001-lightweight-
local-infra.md). Callers (services/repo_service.py) depend on this Protocol
only, never on a concrete executor.
"""
from __future__ import annotations

from typing import Callable, Protocol


class JobQueue(Protocol):
    def enqueue(self, job_id: str, fn: Callable[[], None]) -> None:
        """Schedule `fn` to run in the background; must not block the caller."""
        ...

"""WorktreeOps: what the app asks of git worktrees of cam-docs. A coding change keeps its docs in a named worktree
(`<workspace>/.cw/<id>`, lib/app/change.py); `lib/harness/worktrees.py` provides it."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class WorktreeOps(Protocol):
    def attach(self, repo: Path, path: Path, branch: str, base: str = "HEAD") -> None: ...

    def detach(self, repo: Path, path: Path) -> None: ...

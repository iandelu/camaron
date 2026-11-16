"""RepoSync: what the app asks of the project's repos as git checkouts: clone the missing ones and fast-forward the
clean ones (a forge token injected per call, never stored), find the repos already sitting in a folder, and run git
in one of them, failing loudly."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from lib.ports import Log


class RepoSync(Protocol):
    def git(self, repo: Path, *args: str, check=..., env: dict | None = ...) -> str: ...

    def detect_repos(self, workspace: Path | None = ...) -> list[dict]: ...

    def sync_repos(self, log: Log = ...) -> list[str]: ...

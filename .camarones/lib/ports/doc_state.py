"""DocState: what the app asks of the docs' incremental state: which commit of each repo the docs last matched
(.state.json) and how each repo changed since, and where the pages' status is written (.status.json)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DocState(Protocol):
    STATUS_FILE: Path

    def changes(self) -> dict: ...

    def mark_documented(self, names: list[str] | None = ...) -> list[str]: ...

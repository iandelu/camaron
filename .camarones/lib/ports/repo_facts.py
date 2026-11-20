"""RepoFacts: what the app asks of the repos' static facts — stack, build tool, head, weekly activity, outdated
libraries and code-graph size. All local reads; nothing here calls a model or the network."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class RepoFacts(Protocol):
    def build_tool(self, path: Path) -> str | None: ...

    def facts(self, name: str) -> dict: ...

    def outdated(self, name: str) -> int | None: ...

    def graph_nodes(self, name: str) -> int | None: ...

"""DocStore: what the app asks of the project's pages on disk: every canonical page (docs/ and each repo's OpenWiki
under wikis/) with its logical path, a page's file by any path that names it, where a translation and a repo's wiki
live, a path someone typed resolved, and the human review feedback file."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol


class DocStore(Protocol):
    FEEDBACK: Path

    def iter_docs(self) -> Iterator[tuple[str, Path]]: ...

    def find_page(self, path: str, canon: dict | None = ...) -> Path | None: ...

    def translation_file(self, logical: str, lang: str) -> Path: ...

    def wiki_dir(self, repo: str) -> Path: ...

    def resolve(self, p: str) -> Path: ...

    def add_feedback(self, doc_file: str, text: str, by: str) -> None: ...

    def pending_feedback(self) -> list[str]: ...

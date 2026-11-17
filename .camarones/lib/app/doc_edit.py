"""A person's edits to pages from the portal: saving a page's text and creating a page. Each one reads, checks and writes
holding the page's lock (DocStore.page_lock), so it never interleaves with another writer of that page; a save made from
a version that is no longer the file's (an agent session wrote it, another tab saved it) is a PageConflict and writes
nothing. Confirming is the review's (app/doc_review.py); the MCP's draft edits hold the same lock (lib/mcp.py)."""
from __future__ import annotations

import re
from pathlib import Path

from lib.app import services
from lib.core.paths import DOCS, rel_file
from lib.domain.docs import frontmatter
from lib.domain.docs.page_versions import PageConflict, text_sha


def read_text(f: Path) -> str:
    """A page's text as a writer compares it; "" for a page that does not exist yet (a translation not written)."""
    return f.read_text(encoding="utf-8") if f.exists() else ""


def save(f: Path, raw: str, sha: str | None = None) -> None:
    """Write a page's whole text, ending in a newline, with LF on every OS. `sha` is the version the writer loaded
    (`portal_views.read`'s `sha`): when the file is not that version any more, PageConflict carrying the one it has.
    Without `sha` (an older client, a script) there is no check, but the lock is still held."""
    with services.current().docs.page_lock(f):
        if sha is not None and (now := text_sha(read_text(f))) != sha:
            raise PageConflict(rel_file(f), "sha", now)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(raw if raw.endswith("\n") else raw + "\n", encoding="utf-8", newline="\n")


def create(path: str, title: str) -> str:
    """A new page under docs/, owned by a person; its logical path. A path that exists is refused, checked under the
    lock so two people creating it at once cannot both succeed."""
    path = path.strip().lstrip("/").removeprefix("docs/")
    if not re.fullmatch(r"[\w./-]+\.md", path) or ".." in path:
        raise ValueError("path must look like section/page.md")
    f = DOCS / path
    with services.current().docs.page_lock(f):
        if f.exists():
            raise ValueError(f"{path} already exists")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(frontmatter.join_fm({"title": title, "description": "", "type": "guide", "x-owner": "human"},
                                         f"\n# {title}\n\n"), encoding="utf-8", newline="\n")
    return path

"""The project's pages on disk: every canonical page (docs/ and each repo's OpenWiki under wikis/), a page's file by any
path that names it, where a translation and a repo's wiki live, the lock a writer holds for a page's read-check-write,
and the human review feedback file. Behind lib/ports/doc_store.py."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from lib.adapters.stores import workspace
from lib.common import CAM_LAYOUT, DOCS, ROOT, repo_dir
from lib.core.clock import now
from lib.core.locks import FileLock
from lib.core.paths import CACHE
from lib.domain.docs import logical_paths

PAGE_LOCKS = CACHE / "locks" / "pages"
PAGE_LOCK_WAIT = 10.0          # seconds a writer waits for another writer of the same page before giving up (LockBusy)


def iter_docs():
    """(logical_path, file) for every canonical doc: docs/ + each repo's OpenWiki (cam-docs/wikis/<repo>)."""
    if DOCS.is_dir():
        for f in sorted(DOCS.rglob("*.md")):
            rel = f.relative_to(DOCS)
            if rel.parts[0] == "i18n" or any(p.startswith(".") for p in rel.parts):
                continue
            yield rel.as_posix(), f
    for n in workspace.repo_names():
        ow = wiki_dir(n)
        if ow.is_dir():
            for f in sorted(ow.rglob("*.md")):
                rel = f.relative_to(ow)
                if any(p.startswith(".") for p in rel.parts) or rel.name in ("INSTRUCTIONS.md", "log.md"):
                    continue
                yield logical_paths.wiki_path(n, rel.as_posix()), f


def find_page(path: str, canon: dict | None = None) -> Path | None:
    """The file of a page by any path that names it (logical, `docs/…`, or a wiki page's old repos/<repo>/… path)."""
    canon = dict(iter_docs()) if canon is None else canon
    return canon.get(logical_paths.link_target(path, canon))


def translation_file(logical: str, lang: str) -> Path:
    """Where a page's translation is: docs/i18n/<lang>/<logical>. A wiki page translated before 4.81 kept it under
    i18n/<lang>/repos/<repo>/<page>; that file counts unless a docs page has that path (then it is that page's)."""
    tf = DOCS / "i18n" / lang / logical
    if not tf.exists() and logical.startswith("wikis/") and logical.count("/") >= 2:
        _, repo, rel = logical.split("/", 2)
        old = DOCS / "i18n" / lang / "repos" / repo / rel
        if old.is_file() and not (DOCS / "repos" / repo / rel).exists():
            return old
    return tf


def wiki_dir(repo: str) -> Path:
    """A repo's OpenWiki lives in cam-docs/wikis/<repo> (the repo gets an untracked openwiki/ symlink to it)."""
    own = ROOT / "wikis" / repo
    return own if own.is_dir() or CAM_LAYOUT else repo_dir(repo) / "openwiki"


def resolve(p: str) -> Path:
    f = Path(p)
    if f.is_absolute():
        return f
    return (Path.cwd() / f).resolve() if (Path.cwd() / f).exists() else (ROOT / f).resolve()


def page_lock(f: Path) -> FileLock:
    """The lock a writer holds for a page's whole read-check-write: the portal, the MCP and the kit's own writers take it,
    so two of them never interleave on one page. One per file (a translation is its own page), named after the file's
    folder and name, resolved and case-folded, so every path to the same file meets at the same lock. Agent sessions
    writing the file directly do not take it: the portal's version check (`domain.docs.page_versions`) catches them."""
    f = Path(f)
    key = os.path.normcase(str(f.parent.resolve() / f.name))
    slug = re.sub(r"[^a-z0-9]+", "-", f"{f.parent.name}-{f.stem}".lower()).strip("-")[:48]
    PAGE_LOCKS.mkdir(parents=True, exist_ok=True)     # FileLock names a lock by its resolved folder: make it first
    return FileLock(PAGE_LOCKS / f"{slug}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}.lock",
                    wait=PAGE_LOCK_WAIT, info={"page": f.name})


FEEDBACK = DOCS / ".work" / "review-feedback.md"
FEEDBACK_LOCK = CACHE / "locks" / "review-feedback.lock"


def add_feedback(doc_file: str, text: str, by: str) -> None:
    """One line per comment; the portal, the MCP and the CLI can add one at the same moment, so it holds a lock (two
    first writers would each create the file with its header and drop the other's line)."""
    with FileLock(FEEDBACK_LOCK):
        FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
        if not FEEDBACK.exists():
            FEEDBACK.write_text("# Review feedback\n\nHuman review comments. Agents apply them in the `review-fixes` unit and tick them.\n\n",
                                encoding="utf-8", newline="\n")
        with FEEDBACK.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"- [ ] `{doc_file}` — {text.strip()} _( {by}, {now()[:10]} )_\n")


def pending_feedback() -> list[str]:
    if not FEEDBACK.exists():
        return []
    return [l for l in FEEDBACK.read_text(encoding="utf-8").splitlines() if l.startswith("- [ ]")]

"""The project's pages on disk: every canonical page (docs/ and each repo's OpenWiki under wikis/), a page's file by any
path that names it, where a translation and a repo's wiki live, and the human review feedback file. Behind
lib/ports/doc_store.py."""
from __future__ import annotations

from pathlib import Path

from lib.adapters.stores import workspace
from lib.common import CAM_LAYOUT, DOCS, ROOT, repo_dir
from lib.core.clock import now
from lib.domain.docs import logical_paths


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


FEEDBACK = DOCS / ".work" / "review-feedback.md"


def add_feedback(doc_file: str, text: str, by: str) -> None:
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK.exists():
        FEEDBACK.write_text("# Review feedback\n\nHuman review comments. Agents apply them in the `review-fixes` unit and tick them.\n\n",
                            encoding="utf-8")
    with FEEDBACK.open("a", encoding="utf-8") as fh:
        fh.write(f"- [ ] `{doc_file}` — {text.strip()} _( {by}, {now()[:10]} )_\n")


def pending_feedback() -> list[str]:
    if not FEEDBACK.exists():
        return []
    return [l for l in FEEDBACK.read_text(encoding="utf-8").splitlines() if l.startswith("- [ ]")]

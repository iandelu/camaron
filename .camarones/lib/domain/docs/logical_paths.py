"""Logical paths of pages: where a repo's OpenWiki page sits in cam-docs, what a pre-4.81 wiki path names now, and which
page a link names."""
from __future__ import annotations


# A wiki page's logical path is where it sits in cam-docs, wikis/<repo>/<page>: it can never be a docs page's
# (docs/repos/<repo>/index.md vs OpenWiki's own index.md). Kits up to 4.80.1 called it repos/<repo>/<page>; that path
# still names the wiki page wherever no docs page has it (links, read_doc, freshness stamps, translations).
def wiki_path(repo: str, rel: str) -> str:
    return f"wikis/{repo}/{rel}"


def old_wiki_path(path: str) -> str | None:
    """repos/<repo>/<page> → wikis/<repo>/<page>: what a pre-4.81 wiki path is now (None for any other path)."""
    parts = path.split("/", 2)
    return wiki_path(parts[1], parts[2]) if len(parts) == 3 and parts[0] == "repos" and parts[2] else None


def link_target(path: str, known) -> str:
    """The page a resolved link, or a path someone wrote, names. `docs/<page>` is the docs page <page> (how a wiki page
    links one, as its file sits on disk); a wiki page's old repos/<repo>/<page> is wikis/<repo>/<page> when no docs
    page has that path. Anything else, known or not, stays as written. Mirrored by the portal's linkTarget()."""
    if path in known:
        return path
    bare = path.removeprefix("docs/")
    if bare in known:
        return bare
    alias = old_wiki_path(bare)
    return alias if alias and alias in known else path

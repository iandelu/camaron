"""Where the code backs a C4 element: the anchors written in its `code` and legacy `evidence` metadata, and which repo
paths an anchor covers. An anchor is `<repo>:<path>` with an optional `#L3-L9` (lines) or `#Class.method` (symbol)
suffix; a path ending in `/` is a folder, one with `*` or `?` a glob. Brackets alone are literal names (Next.js
`app/orders/[id]/page.tsx`); in a glob they are a character class or, failing that, literal. The element's own `repo`
metadata is a `kind="repo"` anchor with an empty path (`raw` is `<repo>:`). Pure: metadata comes in as data."""
from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

WILDCARDS = ("*", "?")
GLOB_CHARS = (*WILDCARDS, "[")
LINES = re.compile(r"^L\d+(-L?\d+)?$")
SPECIFICITY = {"lines": 3, "symbol": 3, "file": 2, "folder": 1, "glob": 1, "repo": 0}


@dataclass(frozen=True)
class Anchor:
    repo: str
    path: str
    anchor: str
    kind: str
    legacy: bool
    raw: str


def _entries(value: object) -> list[str]:
    items = [value] if isinstance(value, str) else list(value or [])
    return [i.strip() for i in items if isinstance(i, str) and i.strip()]


def _anchor(repo: str, rest: str, legacy: bool, raw: str) -> Anchor | None:
    path, hashed, frag = rest.replace("\\", "/").partition("#")
    path, frag = path.strip(), frag.strip()
    folder = path.endswith("/")
    p = PurePosixPath(path)
    if not repo or "/" in repo or not path.strip("/") or p.is_absolute() or ".." in p.parts:
        return None
    clean = p.as_posix()
    if any(c in clean for c in WILDCARDS):
        kind = "glob"
    elif folder:
        kind = "folder"
    elif hashed and frag:
        kind = "lines" if LINES.match(frag) else "symbol"
    else:
        kind = "file"
    return Anchor(repo, clean, frag if kind in ("lines", "symbol") else "", kind, legacy, raw)


def _split(entry: str) -> tuple[str | None, str]:
    head = entry.partition("#")[0]
    if ":" not in head:
        return None, entry
    repo, _, rest = entry.partition(":")
    return repo.strip(), rest.strip()


def parse_code(value: str | list[str]) -> tuple[list[Anchor], list[str]]:
    """Anchors, and the raw entries that cannot be read (no `repo:`, empty path, absolute path, `..`)."""
    if not isinstance(value, (str, list, tuple)):
        return [], [repr(value)]
    got: list[Anchor] = []
    bad: list[str] = []
    for entry in _entries(value):
        repo, rest = _split(entry)
        a = _anchor(repo, rest, False, entry) if repo is not None else None
        if a:
            got.append(a)
        else:
            bad.append(entry)
    return got, bad


def parse_legacy(text: str, default_repo: str | None) -> tuple[list[Anchor], list[str]]:
    """Comma-separated `evidence`: an entry without `repo:` takes the previous entry's repo, the first `default_repo`."""
    got: list[Anchor] = []
    bad: list[str] = []
    current = default_repo
    for entry in _entries((text or "").split(",")):
        repo, rest = _split(entry)
        a = _anchor(current if repo is None else repo, rest, True, entry) if (repo or current) else None
        if a:
            current = a.repo
            got.append(a)
        else:
            bad.append(entry)
    return got, bad


def _meta(fqn: str, elements: dict) -> dict:
    return (elements.get(fqn) or {}).get("metadata") or {}


def container_repo(fqn: str, elements: dict) -> str | None:
    """The `metadata.repo` of the element or its nearest ancestor that has one."""
    parts = fqn.split(".")
    for n in range(len(parts), 0, -1):
        repo = _meta(".".join(parts[:n]), elements).get("repo")
        if isinstance(repo, str) and repo.strip():
            return repo.strip()
    return None


def of_element(fqn: str, elements: dict) -> tuple[list[Anchor], list[str]]:
    """`code`, legacy `evidence` (first default: the container's repo) and the element's own `repo`."""
    meta = _meta(fqn, elements)
    got, bad = parse_code(meta.get("code") or [])
    evidence = meta.get("evidence")
    if isinstance(evidence, str):
        legacy, more = parse_legacy(evidence, container_repo(fqn, elements))
        got += legacy
        bad += more
    own = meta.get("repo")
    if isinstance(own, str) and own.strip():
        repo = own.strip()
        got.append(Anchor(repo, "", "", "repo", False, f"{repo}:"))
    return got, bad


def covers(a: Anchor, repo: str, path: str) -> bool:
    """Whether the anchor stands for `path` (repo-relative, posix) of `repo`; lines and symbols compare the file."""
    if a.repo != repo:
        return False
    if a.kind == "repo":
        return True
    if a.kind == "glob":
        return fnmatchcase(path, a.path) or "[" in a.path and fnmatchcase(path, a.path.replace("[", "[[]"))
    if a.kind == "folder":
        return path == a.path or path.startswith(a.path + "/")
    return path == a.path


def ref(a: Anchor) -> str:
    """The anchor as a source reference (`repo:path#frag`), without the folder's trailing `/`."""
    return f"{a.repo}:{a.path}" + (f"#{a.anchor}" if a.anchor else "")


def specificity(a: Anchor) -> int:
    return SPECIFICITY[a.kind]

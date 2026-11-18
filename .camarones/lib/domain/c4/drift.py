"""What the code shows between C4 elements (spec §6): each source file of a repo's code graph mapped to the element
whose anchors cover it most specifically, the structural edges between two elements lifted to relations, which of them
the drawn relations cover, the files no element covers, and the element each name of the arch-draft scan stands for.
Pure: the graph, the scan and the anchors come in as data."""
from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import PurePosixPath

from .anchors import Anchor, container_repo, covers, specificity

STRUCTURAL = ("imports", "imports_from", "calls", "references", "extends", "inherits", "dynamic_import")
NOT_SOURCE = re.compile(r"(^|/)(node_modules|vendor|dist|build|target|\.venv|[\w.-]+-build)/")
# a test's long name matches many words of a prompt, and tests are no component: both leave them out
TEST_FILE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|_test\.\w+$|Tests?\.\w+$|\.(test|spec)\.\w+$")
PEOPLE = ("actor", "person")


def _entries(graph: dict, key: str) -> list[dict]:
    """A node-link list, with what is not an object left out."""
    items = graph.get(key)
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _path(node: dict) -> str:
    return str(node.get("source_file") or "").replace("\\", "/")


def _id(value: object) -> str | int | None:
    return value if isinstance(value, (str, int)) else None


def source_files(graph: dict) -> list[str]:
    """The repo's own source files: code nodes, without tests, build output and vendored code."""
    found = set()
    for n in _entries(graph, "nodes"):
        src = _path(n)
        if (n.get("file_type", "code") == "code" and src and not src.endswith("/") and not NOT_SOURCE.search(src)
                and not TEST_FILE.search(src)):
            found.add(src)
    return sorted(found)


def _rank(a: Anchor) -> tuple[int, int]:
    """Lines or a symbol over a file over a folder or glob; between two folders or globs, the deeper one."""
    return specificity(a), len(PurePosixPath(a.path).parts)


def _within(fqn: str, scope: str) -> bool:
    return fqn == scope or fqn.startswith(scope + ".")


def map_files(files: list[str], anchors_by_fqn: dict[str, list[Anchor]], repo: str) -> tuple[dict[str, str],
                                                                                              list[dict]]:
    """file → the element whose anchors cover it most specifically; a tie between elements that are not parent and
    child is an overlap `{"file", "elements"}` (the file goes to the first, by name)."""
    file_of, overlaps = {}, []
    for f in files:
        best: dict[str, tuple[int, int]] = {}
        for fqn, got in anchors_by_fqn.items():
            ranks = [_rank(a) for a in got if covers(a, repo, f)]
            if ranks:
                best[fqn] = max(ranks)
        if not best:
            continue
        top = max(best.values())
        tied = sorted(fqn for fqn, r in best.items() if r == top)
        tied = [fqn for fqn in tied if not any(o != fqn and _within(o, fqn) for o in tied)]
        file_of[f] = tied[0]
        if len(tied) > 1:
            overlaps.append({"file": f, "elements": tied})
    return file_of, overlaps


def derive(graph: dict, file_of: dict[str, str]) -> dict[tuple[str, str], dict]:
    """(A, B) → {count, example "path:Lnn", relations}: the structural edges from a file of A to a file of B. An edge
    between an element and its own parent or child is no relation: C4 never draws one."""
    nodes = {_id(n.get("id")): n for n in _entries(graph, "nodes") if _id(n.get("id")) is not None}
    out: dict[tuple[str, str], dict] = {}
    for link in _entries(graph, "links"):
        rel = link.get("relation")
        if not isinstance(rel, str) or rel not in STRUCTURAL:
            continue
        src, dst = nodes.get(_id(link.get("source"))), nodes.get(_id(link.get("target")))
        if not src or not dst:
            continue
        path = _path(src)
        a, b = file_of.get(path), file_of.get(_path(dst))
        if not a or not b or _within(a, b) or _within(b, a):
            continue
        d = out.setdefault((a, b), {"count": 0, "example": "", "relations": []})
        d["count"] += 1
        if not d["example"]:
            at = str(link.get("source_location") or src.get("source_location") or "")
            d["example"] = f"{path}:{at}" if at else path
        if rel not in d["relations"]:
            d["relations"].append(rel)
    return out


def covered_by(pair: tuple[str, str], drawn: set[tuple[str, str]]) -> bool:
    """A relation drawn between the pair, or between their ancestors, stands for it."""
    a, b = pair
    return any(_within(a, x) and _within(b, y) for x, y in drawn)


def coverage(files: list[str], file_of: dict[str, str]) -> list[dict]:
    """The files no element covers, as {folder, files} by parent folder, largest first."""
    counts: dict[str, int] = {}
    for f in files:
        if f not in file_of:
            folder = PurePosixPath(f).parent.as_posix()
            counts[folder] = counts.get(folder, 0) + 1
    return [{"folder": k, "files": n} for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def repo_boxes(els: dict) -> dict[str, list[str]]:
    """repo → the outermost elements whose `metadata.repo` names it."""
    named: dict[str, list[str]] = {}
    for fqn, el in els.items():
        repo = (el.get("metadata") or {}).get("repo")
        if isinstance(repo, str) and repo.strip():
            named.setdefault(repo.strip(), []).append(fqn)
    return {repo: sorted(f for f in found if not any(o != f and _within(f, o) for o in found))
            for repo, found in named.items()}


def _word(word: str, text: str) -> bool:
    """`word` as whole words of `text` (`Redis` is not in "Redistribution")."""
    return bool(word) and re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None


def matcher(scan: dict, els: dict) -> Callable[[str], str | None]:
    """A name of the arch-draft scan → the element that stands for it, or None when no element or more than one fits.
    A repo: the outermost element whose `metadata.repo` names it, by title when several do (an app and its Cloud
    Functions). A datastore, broker or identity provider: an element whose technology or title holds its label as
    whole words (a datastore's name breaks a tie), never a person, nor an element in or around a repo container."""
    boxes = repo_boxes(els)
    inside = [f for found in boxes.values() for f in found]
    loose = [f for f, el in els.items() if el.get("kind") not in PEOPLE and container_repo(f, els) is None
             and not any(b.startswith(f + ".") for b in inside)]
    repos, dbs = scan.get("repos") or {}, scan.get("dbs") or {}

    def match(name: str) -> str | None:
        if name in repos:
            found = boxes.get((repos[name] or {}).get("repo", name), [])
            if len(found) > 1:
                found = [f for f in found if str(els[f].get("title") or "").strip().lower() == name.lower()]
            return found[0] if len(found) == 1 else None
        db = dbs.get(name) or {}
        label, extra = str(db.get("label") or name).lower(), str(db.get("name") or "").lower()
        scored = {}
        for f in loose:
            tech, title = str(els[f].get("technology") or "").lower(), str(els[f].get("title") or "").lower()
            if _word(label, tech) or _word(label, title):
                scored[f] = 1 + _word(extra, title)
        top = max(scored.values(), default=0)
        best = [f for f, score in scored.items() if score == top]
        return best[0] if len(best) == 1 else None
    return match

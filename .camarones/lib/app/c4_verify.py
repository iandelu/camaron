"""The C4 model against the code: each element's and relation's evidence state, the findings `check` reports, and the
text `camaron arch-verify` prints. Reads only; states are kept by `harness.freshness`."""
from __future__ import annotations

from lib.domain.c4.verdict import STATES
from lib.harness import freshness

WORST_FIRST = ("broken", "suspect", "no-evidence", "unchecked", "fresh")


def report() -> dict:
    states = freshness.c4_states()
    relations = {}
    for key, r in states["relations"].items():
        own = r.get("own") or "no-evidence"
        relations[key] = {**r, "state": own, "backing": []}
    return {"elements": states["elements"], "relations": relations, "repos": {}, "containers": {},
            "error": states["error"]}


def _what(item: dict) -> str:
    if item["state"] == "no-evidence":
        return "nothing in the code backs it: add metadata { code [...] }"
    parts = [f"{a['result']} {a['raw']}" for a in item["anchors"] if a["result"] in ("missing", "changed")]
    return "; ".join(parts) or item["state"]


def _line(item: dict, name: str) -> str:
    where = f"{item['file']}:{item['line']}: " if item.get("file") else ""
    return f"{where}C4 {name}: {item['state']} — {_what(item)}"


def findings(strict: bool) -> tuple[list[str], list[str]]:
    rep = report()
    errors, warns = [], []
    if rep["error"]:
        warns.append(f"C4 model could not be read: {rep['error']}")
    unchecked = 0
    for group in ("elements", "relations"):
        for name, item in rep[group].items():
            for raw in item.get("unreadable") or []:
                warns.append(f"{item.get('file', '')}:{item.get('line', 0)}: C4 {name}: unreadable evidence entry "
                             f"{raw!r}")
            state = item["state"]
            if state == "unchecked":
                unchecked += 1
            elif state == "fresh" or (state == "no-evidence" and item.get("confirmed")):
                continue
            else:
                (errors if strict else warns).append(_line(item, name))
    if unchecked:
        warns.append(f"C4: {unchecked} unchecked element(s) or relation(s): their repo is not cloned here")
    return errors, warns


def text(rep: dict) -> list[str]:
    out = []
    if rep["error"]:
        out.append(f"C4 model could not be read: {rep['error']}")
    for state in WORST_FIRST:
        rows = [(n, i) for g in ("elements", "relations") for n, i in rep[g].items() if i["state"] == state]
        if rows:
            out.append(f"{state} ({len(rows)})")
            out += [f"  {n}" + (f"  — {_what(i)}" if state not in ("fresh", "unchecked") else "") for n, i in rows]
    legacy = [n for n, i in rep["elements"].items() if i.get("legacy_only")]
    if legacy:
        out.append("legacy evidence only: turn into `code` (metadata { code [...] })")
        out += [f"  {n}" for n in legacy]
    return out or ["No C4 model found."]


assert set(WORST_FIRST) == set(STATES)

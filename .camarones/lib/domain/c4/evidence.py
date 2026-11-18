"""What freshness checks for each C4 element and relation (spec §5.2): the lines that stand for it, the anchors it
names, and its report once each anchor has a result. Pure: the model comes in as c4edit's index and each file's
lines."""
from __future__ import annotations

from collections import Counter

from . import anchors, verdict

SECTIONS = ("elements", "relations")


def relation_key(rel: dict, seen: Counter) -> str:
    """`from -> to 'label'`; a repeat, in index order, gets ` [2]`, ` [3]`…"""
    key = f"{rel['from']} -> {rel['to']} '{rel.get('label') or ''}'"
    seen[key] += 1
    return key if seen[key] == 1 else f"{key} [{seen[key]}]"


def stamps(data: dict) -> dict:
    """fresh.json's `c4` key, set on `data`, with what is not a dict (a merge resolved by hand) read as no stamp."""
    c4 = data["c4"] = data["c4"] if isinstance(data.get("c4"), dict) else {}
    for section in SECTIONS:
        entries = c4.get(section) if isinstance(c4.get(section), dict) else {}
        c4[section] = {k: e for k, e in entries.items() if isinstance(e, dict)}
        for e in c4[section].values():
            fps = e.get("anchors") if isinstance(e.get("anchors"), dict) else {}
            e["anchors"] = {raw: fp for raw, fp in fps.items() if fp is None or isinstance(fp, dict) and "h" in fp}
    return c4


def element_item(fqn: str, elements: dict, files: dict[str, list[str]]) -> tuple | None:
    """("elements", fqn, element, its own lines, anchors, unreadable). Its own lines leave out its child elements'
    blocks: confirming or editing a child is no edit of the parent ("its own block")."""
    el = elements.get(fqn)
    if el is None:
        return None
    inner = {i for f, c in elements.items() if f.startswith(fqn + ".") and c["file"] == el["file"]
             and el["start"] < c["start"] <= el["end"] for i in range(c["start"], c["end"] + 1)}
    own = [files[el["file"]][i] for i in range(el["start"], el["end"] + 1) if i not in inner]
    return ("elements", fqn, el, own, *anchors.of_element(fqn, elements))


def items(files: dict[str, list[str]], idx: dict) -> list[tuple]:
    """element_item for every element, then ("relations", key, relation, its lines, anchors, unreadable): its own
    `code`, and legacy `evidence` whose first entry takes the repo of its `from` end's container."""
    els = idx["elements"]
    out, seen = [element_item(fqn, els, files) for fqn in els], Counter()
    for rel in idx["relations"]:
        meta = rel.get("metadata") or {}
        got, bad = anchors.parse_code(meta.get("code") or [])
        if isinstance(meta.get("evidence"), str):
            more, worse = anchors.parse_legacy(meta["evidence"], anchors.container_repo(rel["from"], els))
            got, bad = got + more, bad + worse
        out.append(("relations", relation_key(rel, seen), rel, files[rel["file"]][rel["start"]:rel["end"] + 1],
                    got, bad))
    return out


def report(item: tuple, results: list[str]) -> dict:
    """An element's {state, confirmed, anchors, unreadable, legacy_only, file, line}, or a relation's {from, to, label,
    anchors, own, confirmed, unreadable, file, line}, from one result per anchor."""
    section, _, it, _, got, bad = item
    rows = [{"raw": a.raw, "kind": a.kind, "legacy": a.legacy, "result": r} for a, r in zip(got, results)]
    state = verdict.combine(list(results))
    where = {"anchors": rows, "unreadable": bad, "file": it["file"], "line": it["start"] + 1}
    if section == "elements":
        return {"state": state, "confirmed": bool(it.get("confirmed")), **where,
                "legacy_only": bool(got) and all(a.legacy for a in got)}
    return {"from": it["from"], "to": it["to"], "label": it["label"], "own": state if got else None,
            "confirmed": "confirmed" in (it.get("tags") or []), **where}

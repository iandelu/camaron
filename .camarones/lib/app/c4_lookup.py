"""The C4 model as an agent asks for it: which elements stand behind a file, what the code says about one (its evidence
and state), its relations and the decisions about it (spec §5.2, §7). The prompt hook and the pre-edit stop call only
`covering` and `decisions_about`, which read anchors and pages; `lookup` is the explicit query behind the MCP tool and
may run the drift report. Elements and relations the code does not back are withheld by `verdict.serve`: named with
why, never described."""
from __future__ import annotations

import re

from lib import adr_doc, c4edit
from lib.app import c4_verify, services
from lib.domain.c4 import anchors, verdict
from lib.domain.docs import frontmatter
from lib.harness import freshness

FILE_LIMIT = 5
BACKING_SHOWN = 2
READ_INSTEAD = "Read the code instead."


def _elements() -> dict:
    try:
        return c4edit.index()["elements"]
    except Exception:  # noqa: BLE001 — a model that does not parse has no elements to point at
        return {}


def _code_anchors(fqn: str, elements: dict) -> list[anchors.Anchor]:
    """The anchors that name code, without the repo anchor that stands for a whole repo."""
    return [a for a in anchors.of_element(fqn, elements)[0] if a.kind != "repo"]


def covering(repo: str, rel: str, elements: dict | None = None) -> list[str]:
    """The elements whose anchors cover `rel` of `repo`, most specific anchor first; a repo container (its `repo`
    metadata) covers every file of the repo and sorts last. Callers that want one element take the first."""
    els = _elements() if elements is None else elements
    found = []
    for fqn in els:
        best = max((anchors.specificity(a) for a in anchors.of_element(fqn, els)[0] if anchors.covers(a, repo, rel)),
                   default=None)
        if best is not None:
            found.append((-best, fqn))
    return [fqn for _, fqn in sorted(found)]


def _code_of(source: str) -> tuple[str, str] | None:
    if source.startswith("c4:"):
        return None
    repo, path, _ = freshness.parse(source)
    return (repo, path.split("#", 1)[0]) if repo and path else None


def _scan() -> tuple[list[dict], dict[str, list[str]]]:
    """One pass over the docs: the decision pages, and per element the other pages citing it (`c4:<fqn>`)."""
    decisions, cited = [], {}
    for logical, f in services.current().docs.iter_docs():
        fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8", errors="replace"))
        sources = [str(s).strip() for s in fm.get("x-sources") or []]
        c4 = [s[3:].strip() for s in sources if s.startswith("c4:")]
        if adr_doc.is_decision(logical, fm.get("type")):
            decisions.append({"path": logical, "title": str(fm.get("title") or logical),
                              "status": adr_doc.status_of(body)[0], "c4": c4,
                              "code": [p for p in map(_code_of, sources) if p]})
        else:
            for fqn in c4:
                cited.setdefault(fqn, []).append(logical)
    return decisions, cited


def decision_pages() -> list[dict]:
    return _scan()[0]


def decisions_about(fqn: str, limit: int = 2, elements: dict | None = None, pages: list[dict] | None = None
                    ) -> list[dict]:
    """Decision pages citing the element or an ancestor, then those whose code sources fall under its anchors;
    accepted ones first."""
    els = _elements() if elements is None else elements
    mine = _code_anchors(fqn, els)
    ranked = []
    for p in decision_pages() if pages is None else pages:
        if any(fqn == c or fqn.startswith(c + ".") for c in p["c4"]):
            group = 0
        elif any(anchors.covers(a, repo, path) for a in mine for repo, path in p["code"]):
            group = 1
        else:
            continue
        ranked.append((p["status"] != "accepted", group, p["path"], p))
    ranked.sort(key=lambda r: r[:3])
    return [{k: p[k] for k in ("path", "title", "status")} for *_, p in ranked[:limit]]


def shown(items: list[dict]) -> list[dict]:
    """An element's anchors as an agent reads them; the repo anchor reads `whole repo <name>`."""
    return [{"raw": f"whole repo {a['raw'][:-1]}" if a["raw"].endswith(":") else a["raw"], "result": a["result"]}
            for a in items]


def code_to_read(items: list[dict]) -> list[dict]:
    return [a for a in shown(items) if not a["raw"].startswith("whole repo")]


def withheld(fqn: str, notice: str | None, items: list[dict]) -> str:
    """`withheld: <fqn> — <why>`, with the code to read instead when the element has named code."""
    why = (notice or "").removeprefix("withheld: ")
    code = code_to_read(items)
    if code:
        why = why.replace(READ_INSTEAD, "Read the code instead: " + ", ".join(
            f"{a['raw']} ({a['result']})" for a in code) + ".")
    return f"withheld: {fqn} — {why}"


def _backing(r: dict) -> list[str]:
    return [b.get("example") or f"{b['from']} -> {b['to']}" for b in r.get("backing") or []][:BACKING_SHOWN]


def _relation(r: dict, other: str, policy: str) -> dict:
    served, notice = verdict.serve(r["state"], bool(r.get("confirmed")), policy)
    row = {"other": other, "state": r["state"], "served": served, "notice": notice}
    if served:
        row.update(label=r["label"], backing=_backing(r))
    return row


def _relations(fqn: str, rep: dict, policy: str) -> tuple[list[dict], list[dict]]:
    into, out = [], []
    for r in rep["relations"].values():
        if r["to"] == fqn:
            into.append(_relation(r, r["from"], policy))
        if r["from"] == fqn:
            out.append(_relation(r, r["to"], policy))
    return into, out


def _normal(rel: str) -> str:
    rel = rel.split("#", 1)[0].strip().replace("\\", "/")
    return re.sub(r"^(\./|/)+", "", rel)


def _targets(target: str, els: dict) -> tuple[list[str], str | None]:
    target = target.strip()
    if ":" in target and target not in els:
        repo, _, rel = target.partition(":")
        found = covering(repo.strip(), _normal(rel), els)
        return found[:FILE_LIMIT], (None if found else f"no C4 element is anchored on {target}")
    return ([target], None) if target in els else ([], f"no C4 element {target!r}")


def lookup(target: str) -> dict:
    """{target, elements, error}: a withheld element keeps only `fqn`, `state`, `served`, `notice` and the code to
    read instead (`anchors`)."""
    rep = c4_verify.report()
    els = _elements()
    fqns, error = _targets(str(target or ""), els)
    out = {"target": target, "elements": [], "error": error or rep["error"]}
    if not fqns:
        return out
    (decisions, cited), policy = _scan(), freshness.policy()
    for fqn in fqns:
        st = rep["elements"].get(fqn) or {"state": "no-evidence", "confirmed": False, "anchors": []}
        served, notice = verdict.serve(st["state"], bool(st["confirmed"]), policy)
        item = {"fqn": fqn, "state": st["state"], "served": served, "notice": notice}
        if not served:
            item["anchors"] = shown(st["anchors"])
        else:
            el = els[fqn]
            into, outgoing = _relations(fqn, rep, policy)
            item.update(title=el.get("title", ""), kind=el.get("kind", ""), description=el.get("description", ""),
                        anchors=shown(st["anchors"]), relations_in=into, relations_out=outgoing,
                        decisions=decisions_about(fqn, 5, els, decisions), pages=cited.get(fqn, []))
        out["elements"].append(item)
    return out


def _relation_line(r: dict, arrow: str) -> str:
    if not r["served"]:
        return f"  {arrow} {r['other']} — {r['notice']}"
    return (f"  {arrow} {r['other']} '{r['label']}' ({r['state']})" + (f" · {r['notice']}" if r["notice"] else "")
            + (f" — {'; '.join(r['backing'])}" if r["backing"] else ""))


def render(found: dict) -> str:
    if not found["elements"]:
        return found["error"] or f"Nothing known about {found['target']}."
    lines = [f"C4 error: {found['error']}"] if found["error"] else []
    for e in found["elements"]:
        if not e["served"]:
            lines.append(withheld(e["fqn"], e["notice"], e["anchors"]) + f" ({e['state']})")
            continue
        head = f"{e['fqn']} — {e['title']} ({e['kind']}) · {e['state']}" + (f" · {e['notice']}" if e["notice"] else "")
        lines.append(head + (f"\n  {e['description']}" if e["description"] else ""))
        lines.append("  evidence: " + (", ".join(f"{a['raw']} ({a['result']})" for a in e["anchors"]) or "none"))
        lines += [_relation_line(r, "<-") for r in e["relations_in"]]
        lines += [_relation_line(r, "->") for r in e["relations_out"]]
        lines += [f"  decision: {d['path']} — {d['title']} ({d['status']})" for d in e["decisions"]]
        lines += [f"  page: {p}" for p in e["pages"]]
    return "\n".join(lines)

"""The C4 model against the code: each element's and relation's evidence state, the drift between the model and what
the code shows (graphify's graph per repo with a components file, the arch-draft scan between containers, spec §6),
the findings `check` reports, and the text `camaron arch-verify` prints. Reads only; states are kept by
`harness.freshness`."""
from __future__ import annotations

import json

from lib import c4edit
from lib.app import services
from lib.common import out, repo_dir
from lib.domain.c4 import anchors, drift
from lib.harness import freshness

WORST_FIRST = ("broken", "suspect", "no-evidence", "unchecked", "fresh")
GATED = ("broken", "no-evidence")
GRAPH_HINT = "build it with `camaron graph`"


def _index() -> dict:
    try:
        return c4edit.index()
    except Exception:                       # a model c4edit cannot read: c4_states already says why
        return {"elements": {}, "relations": []}


def _meta_repo(el: dict) -> str | None:
    repo = (el.get("metadata") or {}).get("repo")
    return repo.strip() if isinstance(repo, str) and repo.strip() else None


def _components(els: dict) -> dict[str, list[str]]:
    """Per repo, the elements nested under a container whose `metadata.repo` names it."""
    got: dict[str, set] = {}
    for fqn, el in els.items():
        repo = _meta_repo(el)
        kids = [f for f in els if f.startswith(fqn + ".")]
        if repo and kids:
            got.setdefault(repo, set()).update(kids)
    return {repo: sorted(kids) for repo, kids in got.items()}


def _graph(repo: str) -> tuple[dict | None, str, str]:
    """The repo's code graph, `ok`/`missing`/`stale`, and the commits when stale."""
    try:
        data = json.loads(services.current().code.repo_graph(repo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "missing", ""
    if not isinstance(data, dict):
        return None, "missing", ""
    built = str(data.get("built_at_commit") or "")
    head = out(["git", "-C", str(repo_dir(repo)), "rev-parse", "HEAD"]) if built else ""
    if built and head and not head.startswith(built) and not built.startswith(head):
        return data, "stale", f"built at {built[:7]}, the repo is at {head[:7]}"
    return data, "ok", ""


def _repo_drift(repo: str, fqns: list[str], els: dict, drawn: set) -> tuple[dict, dict]:
    """The repo's line of the report, and its derived relations."""
    data, status, note = _graph(repo)
    row = {"graph": status, "in_code_not_model": [], "overlaps": [], "coverage": []}
    if note:
        row["note"] = note
    if data is None:
        return row, {}
    files = drift.source_files(data)
    by_fqn = {f: [a for a in anchors.of_element(f, els)[0] if a.kind != "repo"] for f in fqns}
    file_of, row["overlaps"] = drift.map_files(files, by_fqn, repo)
    derived = drift.derive(data, file_of)
    row["in_code_not_model"] = [{"from": a, "to": b, "count": d["count"], "example": d["example"]}
                                for (a, b), d in sorted(derived.items()) if not drift.covered_by((a, b), drawn)]
    row["coverage"] = drift.coverage(files, file_of)
    return row, derived


def _matcher(scan: dict, els: dict):
    """A scan name → the element that stands for it: a repo through `metadata.repo` (its title when the repo has
    several, as an app and its Cloud Functions), anything else by technology and title among the elements neither in
    nor around a repo container; None when nothing or more than one fits."""
    by_repo: dict[str, list[str]] = {}
    for fqn, el in els.items():
        if repo := _meta_repo(el):
            by_repo.setdefault(repo, []).append(fqn)
    boxes = [f for found in by_repo.values() for f in found]
    loose = [f for f in els if anchors.container_repo(f, els) is None and not any(b.startswith(f + ".") for b in boxes)]

    def match(name: str) -> str | None:
        if name in scan.get("repos", {}):
            found = by_repo.get(scan["repos"][name].get("repo", name), [])
            if len(found) > 1:
                found = [f for f in found if str(els[f].get("title", "")).strip().lower() == name.lower()]
            return found[0] if len(found) == 1 else None
        db = scan.get("dbs", {}).get(name)
        words = [(db["label"], 2), (db["name"], 1)] if db else [(name, 2)]
        scored = {}
        for f in loose:
            text = f"{els[f].get('technology', '')} {els[f].get('title', '')}".lower()
            scored[f] = sum(w for word, w in words if word and str(word).lower() in text)
        top = max(scored.values(), default=0)
        best = [f for f, s in scored.items() if s == top]
        return best[0] if top and len(best) == 1 else None
    return match


def _containers(els: dict, drawn: set) -> tuple[dict, list[dict]]:
    """The scan's edges as model pairs: those no drawn relation stands for, those an end of which no element stands
    for, and every matched edge (what backs drawn relations)."""
    box = {"in_code_not_model": [], "not_compared": []}
    try:
        scan = services.current().arch_scan.scan()
    except Exception as e:                  # a scan that fails leaves the containers not compared, never check broken
        return {**box, "error": str(e) or type(e).__name__}, []
    match, proofs, matched, seen = _matcher(scan, els), scan.get("edge_evidence") or {}, [], set()
    for a, b, _, label in scan.get("edges") or []:
        if (a, b, label) in seen:
            continue
        seen.add((a, b, label))
        fa, fb = match(a), match(b)
        if not fa or not fb:
            box["not_compared"].append({"from": a, "to": b, "label": label,
                                        "unmatched": [n for n, f in ((a, fa), (b, fb)) if not f]})
            continue
        if fa == fb:
            continue
        edge = {"from": fa, "to": fb, "label": label, "example": proofs.get((a, b, label)) or ""}
        matched.append(edge)
        if not drift.covered_by((fa, fb), drawn) and not any(drift.covered_by(d, {(fa, fb)}) for d in drawn):
            box["in_code_not_model"].append(edge)
    return box, matched


def report() -> dict:
    states = freshness.c4_states()
    els = _index()["elements"] if states["elements"] else {}
    drawn = {(r["from"], r["to"]) for r in states["relations"].values()}
    repos, derived = {}, {}
    for repo, fqns in _components(els).items():
        repos[repo], derived[repo] = _repo_drift(repo, fqns, els, drawn)
    containers, scanned = _containers(els, drawn) if any(_meta_repo(e) for e in els.values()) else ({}, [])
    no_graph = {repo for repo, row in repos.items() if row["graph"] == "missing"}
    absent = {r for r in services.current().workspace.repo_names() if not repo_dir(r).is_dir()}
    relations = {}
    for key, r in states["relations"].items():
        pair = (r["from"], r["to"])
        ends = {anchors.container_repo(end, els) for end in pair}
        backing = [{"by": "graph", "repo": repo, "from": a, "to": b, "count": d["count"], "example": d["example"]}
                   for repo, found in derived.items() for (a, b), d in sorted(found.items())
                   if drift.covered_by((a, b), {pair})]
        backing += [{"by": "scan", **e} for e in scanned
                    if drift.covered_by((e["from"], e["to"]), {pair}) or drift.covered_by(pair, {(e["from"], e["to"])})]
        if r.get("own"):
            state = r["own"]
        elif backing:
            state = "fresh"
        elif ends & absent or (len(ends) == 1 and ends <= no_graph):      # only one repo's graph derives an edge
            state = "unchecked"
        else:
            state = "no-evidence"
        relations[key] = {**r, "state": state, "backing": backing}
    return {"elements": states["elements"], "relations": relations, "repos": repos, "containers": containers,
            "error": states["error"]}


def _what(item: dict) -> str:
    if item["state"] == "no-evidence":
        return "nothing in the code backs it: add metadata { code [...] }"
    parts = [f"{a['result']} {a['raw']}" for a in item["anchors"] if a["result"] in ("missing", "changed")]
    return "; ".join(parts) or item["state"]


def _where(item: dict) -> str:
    return f"{item['file']}:{item['line']}: " if item.get("file") else ""


def _line(item: dict, name: str) -> str:
    return f"{_where(item)}C4 {name}: {item['state']} — {_what(item)}"


def _example(item: dict) -> str:
    return f", e.g. {item['example']}" if item.get("example") else ""


def findings(strict: bool) -> tuple[list[str], list[str]]:
    rep = report()
    errors, warns = [], []
    gated = errors if strict else warns
    if rep["error"]:
        warns.append(f"C4 model could not be read: {rep['error']}")
    unchecked = 0
    for group in ("elements", "relations"):
        for name, item in rep[group].items():
            for raw in item.get("unreadable") or []:
                gated.append(f"{_where(item)}C4 {name}: unreadable evidence entry {raw!r}")
            state = item["state"]
            if state == "unchecked":
                unchecked += 1
            elif state == "fresh" or (state == "no-evidence" and item.get("confirmed")):
                continue
            else:
                (gated if state in GATED else warns).append(_line(item, name))
    if unchecked:
        warns.append(f"C4: {unchecked} unchecked element(s) or relation(s): their repo is not cloned here or has no "
                     f"code graph ({GRAPH_HINT})")
    for repo, row in rep["repos"].items():
        if row["graph"] == "missing":
            warns.append(f"C4: {repo} has no code graph, so the relations of its components are not compared: "
                         f"{GRAPH_HINT}")
        elif row["graph"] == "stale":
            warns.append(f"C4: the code graph of {repo} was {row['note']}: rebuild it with `camaron graph`")
        stale = " (graph built at another commit)" if row["graph"] == "stale" else ""
        for i in row["in_code_not_model"]:
            gated.append(f"C4 drift in {repo}: {i['from']} -> {i['to']} is in the code ({i['count']} edge(s)"
                         f"{_example(i)}) but not in the model{stale}")
    box = rep["containers"]
    if box.get("error"):
        warns.append(f"C4: the code scan failed, so the containers are not compared: {box['error']}")
    for i in box.get("in_code_not_model") or []:
        where = f" ({i['example']})" if i.get("example") else ""
        gated.append(f"C4 drift: {i['from']} -> {i['to']} '{i['label']}' is in the code{where} but not in the model")
    return errors, warns


def _drift_text(rep: dict) -> list[str]:
    lines = []
    for repo, row in rep["repos"].items():
        if row["graph"] == "missing":
            lines.append(f"drift in {repo}: no code graph, not compared ({GRAPH_HINT})")
            continue
        lines.append(f"drift in {repo}" + (f": graph {row['note']}, rebuild it with `camaron graph`"
                                           if row["graph"] == "stale" else ""))
        found = row["in_code_not_model"]
        lines.append(f"  in the code, not in the model ({len(found)})" if found
                     else "  in the code, not in the model: none")
        lines += [f"    {i['from']} -> {i['to']}  {i['count']} edge(s){_example(i)}" for i in found]
        lines += [f"  overlap: {o['file']} is covered by {', '.join(o['elements'])}" for o in row["overlaps"]]
        if row["coverage"]:
            lines.append("  candidate components (code no element covers)")
            lines += [f"    {c['folder']}/  {c['files']} file(s)" for c in row["coverage"]]
    box = rep["containers"]
    if box:
        lines.append("containers" + (f": the code scan failed ({box['error']})" if box.get("error") else ""))
        found = box["in_code_not_model"]
        if not box.get("error"):
            lines.append(f"  in the code, not in the model ({len(found)})" if found
                         else "  in the code, not in the model: none")
        lines += [f"    {i['from']} -> {i['to']} '{i['label']}'{_example(i)}" for i in found]
        if box["not_compared"]:
            lines.append(f"  not compared, no element stands for one end ({len(box['not_compared'])})")
            lines += [f"    {i['from']} -> {i['to']} '{i['label']}'" for i in box["not_compared"]]
    return lines


def text(rep: dict) -> list[str]:
    lines = []
    if rep["error"]:
        lines.append(f"C4 model could not be read: {rep['error']}")
    for state in WORST_FIRST:
        rows = [(n, i) for g in ("elements", "relations") for n, i in rep[g].items() if i["state"] == state]
        if rows:
            lines.append(f"{state} ({len(rows)})")
            lines += [f"  {n}" + (f"  — {_what(i)}" if state not in ("fresh", "unchecked") else "") for n, i in rows]
    legacy = [n for n, i in rep["elements"].items() if i.get("legacy_only")]
    if legacy:
        lines.append("legacy evidence only: turn into `code` (metadata { code [...] })")
        lines += [f"  {n}" for n in legacy]
    lines += _drift_text(rep)
    return lines or ["No C4 model found."]

"""One repo's dashboard and every repo's card for the desktop app: the last health snapshot, the repo's static facts, its
docs, wiki, C4 element, board cards and decisions. Each source is read through a guard, so one that fails leaves only its
own block empty. Reads only, no model and no network."""
from __future__ import annotations

from collections.abc import Callable

from lib import adr, c4edit, health
from lib.app import services
from lib.harness import freshness
from lib.kanban import ops

TREND = 8
ADRS = 5


def _guard(read: Callable, default=None):
    try:
        return read()
    except Exception:  # noqa: BLE001 - a broken source must not take the whole page down
        return default


def _num(v) -> float | None:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _sonar(block, coverage) -> dict | None:
    if not isinstance(block, dict) or ("error" in block and not block.get("used") and not block.get("server")):
        return None
    server = block.get("server") if isinstance(block.get("server"), dict) else None
    report = coverage if isinstance(coverage, dict) else {}
    if server and _num(server.get("coverage")) is not None:
        cov, src, at = server["coverage"], "sonar", server.get("at")
    else:
        cov, src, at = _num(report.get("percent")), report.get("source") if _num(report.get("percent")) is not None else None, report.get("at")
    figures = server or {}
    return {"source": "sonar" if server else "estimated", "gate": figures.get("gate"), "coverage": cov,
            "coverageSource": src if cov is not None else None, "coverageAt": at if cov is not None else None,
            "bugs": figures.get("bugs"), "vulnerabilities": figures.get("vulnerabilities"),
            "debtMinutes": _num(figures.get("debt_minutes")), "link": block.get("link") or "",
            "host": block.get("host") or "", "connect": bool(block.get("connect")),
            "error": block.get("error") if isinstance(block.get("error"), str) else None}


def _trend(name: str) -> list[dict]:
    rows = [{"at": r.get("at"), "coverage": p} for r in health.history()
            if isinstance(r.get("repos"), dict) and (p := _num(r["repos"].get(name))) is not None]
    return rows[-TREND:]


def _vulns(snap_repo: dict, snap: dict) -> dict:
    inv, vulns = snap.get("inventory"), snap_repo.get("vulns")
    return {"vulns": vulns if isinstance(vulns, dict) and "error" not in vulns else {},
            "scanned": bool(isinstance(inv, dict) and inv.get("scanned"))}


def _libs(snap_repo: dict, snap: dict, name: str) -> dict:
    total = snap_repo.get("libraries")
    return {"total": total if isinstance(total, int) and not isinstance(total, bool) else None,
            **_vulns(snap_repo, snap),
            "outdated": _guard(lambda: services.current().repo_facts.outdated(name))}


def _docs(counts: dict | None) -> dict | None:
    if counts is None:
        return None
    row = counts or {}
    fresh, suspect, stale = (row.get(k, 0) for k in ("fresh", "suspect", "stale"))
    return {"total": fresh + suspect + stale, "fresh": fresh, "suspect": suspect, "stale": stale}


def _wiki(row: dict | None) -> dict | None:
    if not row:
        return None
    return {"pages": row.get("pages", 0), "at": row.get("at"), "stale": bool(row.get("stale")),
            "chosen": bool(row.get("chosen")), "unit": row.get("unit")}


def _c4(name: str) -> dict | None:
    idx = c4edit.index()
    els = idx["elements"]
    fqn = next((f for f in sorted(els) if (els[f].get("metadata") or {}).get("repo") == name), None) \
        or next((f for f in sorted(els) if els[f].get("title") == name), None)
    if fqn is None:
        return None
    ends = lambda a, b: sorted(  # noqa: E731
        {r[b] for r in idx["relations"] if r[a] == fqn and r[b] != fqn and r[b] in els},
        key=lambda f: (els[f].get("title") or f, f))
    node = lambda f: {"fqn": f, "title": els[f].get("title") or f}  # noqa: E731
    el = els[fqn]
    return {"fqn": fqn, "title": el.get("title") or fqn, "technology": el.get("technology") or "",
            "in": [node(f) for f in ends("to", "from")], "out": [node(f) for f in ends("from", "to")]}


def _work(name: str) -> dict:
    found = ops.list_items(repo=name)
    cards = found.get("cards", []) if isinstance(found, dict) else found
    cards = [c for c in cards if name in (c.get("repos") or [])]
    columns = [{"status": s, "n": sum(1 for c in cards if c.get("status") == s)} for s in ops.STATUSES]
    return {"columns": columns, "total": len(cards)}


def _adrs(name: str) -> list[dict]:
    rows = [a for a in adr.list_adrs() if name in (a.get("repos") or [])]
    return [{k: a.get(k) for k in ("id", "title", "chip", "status")} for a in rows[:ADRS]]


def _state(snap: dict | None, name: str) -> str | None:
    states = snap.get("repo_state") if snap else None
    return states.get(name) if isinstance(states, dict) else None


def repo(name: str) -> dict | None:
    """The repo's dashboard, or None when `name` is not a repo of the workspace."""
    svc = services.current()
    if name not in svc.workspace.repo_names():
        return None
    snap = _guard(health.load)
    block = (snap.get("repos") or {}).get(name) if snap and isinstance(snap.get("repos"), dict) else None
    block = block if isinstance(block, dict) and "error" not in block else {}
    cloned = bool(_guard(lambda: _dir(name).is_dir(), False))
    facts = (_guard(lambda: svc.repo_facts.facts(name)) or {}) if cloned else {}
    wiki = next((r for r in _guard(svc.wiki.wikis, []) if r.get("repo") == name), None)
    return {"name": name, "cloned": cloned, "state": _state(snap, name), "at": snap.get("at") if snap else None,
            "head": facts.get("head"), "stack": facts.get("stack") or [], "build": facts.get("build"),
            "sonar": _sonar(block.get("sonar"), block.get("coverage")) if cloned and block else None,
            "trend": _guard(lambda: _trend(name), []), "activity": facts.get("activity"),
            "libs": _libs(block, snap or {}, name), "docs": _guard(lambda: _docs(freshness.by_repo().get(name, {}))),
            "wiki": _wiki(wiki), "c4": _guard(lambda: _c4(name)),
            "graph": _guard(lambda: svc.repo_facts.graph_nodes(name)) if cloned else None,
            "work": _guard(lambda: _work(name), {"columns": [{"status": s, "n": 0} for s in ops.STATUSES], "total": 0}),
            "adrs": _guard(lambda: _adrs(name), [])}


def _dir(name: str):
    from lib.common import repo_dir
    return repo_dir(name)


def repos() -> dict:
    """Every workspace repo's card, in workspace order; freshness and the wikis are read once for all."""
    svc = services.current()
    snap = _guard(health.load)
    by = _guard(freshness.by_repo)
    wikis = {r.get("repo"): r for r in _guard(svc.wiki.wikis, [])}
    rows = []
    for name in svc.workspace.repo_names():
        block = (snap.get("repos") or {}).get(name) if snap and isinstance(snap.get("repos"), dict) else None
        block = block if isinstance(block, dict) and "error" not in block else {}
        cloned = bool(_guard(lambda: _dir(name).is_dir(), False))
        sonar = _sonar(block.get("sonar"), block.get("coverage")) if cloned and block else None
        docs = _docs(by.get(name, {})) if by is not None else None
        rows.append({
            "name": name, "cloned": cloned, "state": _state(snap, name),
            "stack": (_guard(lambda: svc.repo_facts.facts(name)) or {}).get("stack", []) if cloned else [],
            "sonar": {k: sonar[k] for k in ("source", "gate", "coverage", "coverageSource")} if sonar else None,
            "libs": _vulns(block, snap or {}),
            "wiki": {k: v for k, v in (_wiki(wikis.get(name)) or {}).items() if k in ("pages", "at", "unit")} or None,
            "docs": {k: docs[k] for k in ("total", "suspect", "stale")} if docs else None})
    return {"at": snap.get("at") if snap else None, "repos": rows}

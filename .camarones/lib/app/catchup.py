"""Catch-up: bring this machine's cam-docs in step with the team's (pull) and rebuild the local views that went stale.
It never pushes and never writes team decisions (workspace.yaml, plan.yaml, the .c4 model)."""
from __future__ import annotations

import datetime as dt

from lib.app import services
from lib.common import CACHE, CTX, load_json, save_json, which
from lib.core.locks import FileLock, LockBusy
from lib.harness import scheduler
from lib.ports import Log

LAST = CACHE / "catch-up.json"
LOCK = CTX.state_root / ".camarones" / ".cache" / "locks" / "catch-up.lock"


def last() -> dict | None:
    return load_json(LAST, None)


def rebuild_c4(log: Log = print) -> str:
    c4 = services.current().viewers.viewers()["c4"]
    if not c4["model"] or "likec4" not in services.current().components.components() or not which("likec4"):
        return "skipped"
    if c4["exists"] and not c4["stale"]:
        return "fresh"
    return "built" if services.current().viewers.build_c4(log=log) else "failed"


def stale_graphs() -> list[str]:
    v = services.current().viewers.viewers()
    if not v["graphify"]:
        return []
    return [n for n, g in v["graphs"].items() if g["stale"] and n != "all"]


def rebuild_graphs(repos: list[str], log: Log = print) -> bool:
    for name in repos:
        services.current().code.graph_repo(name)
    return bool(services.current().viewers.graph(rebuild=False, log=log))


def _pull(log: Log) -> dict:
    if scheduler.busy():
        return {"status": "busy", "commits": 0, "files": [], "regenerated": [], "detail": "run"}
    return services.current().share.pull(log)


def _run(log: Log) -> dict:
    pull = _pull(log)
    c4 = rebuild_c4(log)
    stale = stale_graphs()
    if stale:
        rebuild_graphs(stale, log)
    result = {"status": "done", "pull": pull, "views": {"c4": c4, "graphs": stale},
              "at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    save_json(LAST, result)
    return result


def run(log: Log = print) -> dict:
    at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    if CTX.root != CTX.state_root:
        return {"status": "skipped", "pull": None, "views": {"c4": "skipped", "graphs": []}, "at": at}
    try:
        with FileLock(LOCK, wait=0):
            return _run(log)
    except LockBusy:
        return {"status": "busy", "pull": None, "views": {"c4": "skipped", "graphs": []}, "at": at}

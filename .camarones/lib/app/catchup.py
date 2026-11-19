"""Catch-up: bring this machine's cam-docs in step with the team's (pull), find the team's repos on this machine (a clone
under another folder name is linked, nothing is cloned) and rebuild the local views that went stale.
It never pushes and never writes team decisions (workspace.yaml, plan.yaml, the .c4 model). The explorer is rebuilt
here; the code graphs are slow, so `views["graphs"]` lists the stale repos still to rebuild and the caller runs
`rebuild_graphs` on them (a background job, or inline in the CLI). Nothing here raises past `run`."""
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


FETCH_TIMEOUT = 30                                   # seconds: opening never waits on a host that does not answer


def _pull(log: Log) -> dict:
    if scheduler.busy():
        return {"status": "busy", "commits": 0, "files": [], "regenerated": [], "detail": "run"}
    try:
        return services.current().share.pull(log, timeout=FETCH_TIMEOUT)
    except Exception as e:                                   # noqa: BLE001 — opening must go on, and say why
        log(f"⚠ bringing in the team's work failed: {e}")
        return {"status": "error", "commits": 0, "files": [], "regenerated": [], "detail": str(e), "reason": "unknown",
                "host": ""}


def _repos(log: Log) -> dict:
    from lib.app import repos_here
    try:
        found = repos_here.find(log)
    except Exception as e:                                   # noqa: BLE001 — opening must go on
        log(f"⚠ could not look for the repos: {e}")
        return {s: [] for s in repos_here.STATES}
    return {s: found[s] for s in repos_here.STATES}


def _run(log: Log) -> dict:
    pull = _pull(log)
    repos = _repos(log)
    try:
        c4 = rebuild_c4(log)
    except Exception as e:                                   # noqa: BLE001 — opening must go on
        log(f"⚠ explorer rebuild failed: {e}")
        c4 = "failed"
    try:
        stale = stale_graphs()
    except Exception as e:                                   # noqa: BLE001
        log(f"⚠ could not check the code graphs: {e}")
        stale = []
    result = {"status": "done", "pull": pull, "repos": repos, "views": {"c4": c4, "graphs": stale},
              "at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    save_json(LAST, result)
    return result


def run(log: Log = print) -> dict:
    """Pull, rebuild the explorer if stale, and list the stale graph repos for the caller to rebuild. Status: done ·
    busy (another catch-up holds the lock) · skipped (a unit's worktree)."""
    at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    if CTX.root != CTX.state_root:
        return {"status": "skipped", "pull": None, "views": {"c4": "skipped", "graphs": []}, "at": at}
    try:
        with FileLock(LOCK, wait=0):
            return _run(log)
    except LockBusy:
        return {"status": "busy", "pull": None, "views": {"c4": "skipped", "graphs": []}, "at": at}

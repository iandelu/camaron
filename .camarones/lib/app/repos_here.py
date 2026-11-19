"""Where each of the team's repos is on this machine, found by its remote (remote_key), not its folder name.
A clone kept under another folder name, at the workspace's first level or in a folder this machine names, gets
<workspace>/<name> linked to it, so the kit, the agents and every doc path keep reading <workspace>/<name>. A
<workspace>/<name> holding something else is never touched. The links and the search folders are this machine's, kept
in the git-ignored cache; uninstall removes the links. Nothing is cloned, renamed or moved here."""
from __future__ import annotations

import os
from pathlib import Path

from lib.app import services
from lib.common import CACHE, CAM_DIR, WORKSPACE, load_json, save_json
from lib.core.remotes import remote_key
from lib.ports import Log

FILE = "repos-here.json"
STATES = ("here", "linked", "missing", "taken")


def load(cache: Path | None = None) -> dict:
    data = load_json((cache or CACHE) / FILE, {}) or {}
    return {"search": list(data.get("search") or []), "links": dict(data.get("links") or {}),
            "excluded": list(data.get("excluded") or [])}


def _save(data: dict, cache: Path | None = None) -> None:
    save_json((cache or CACHE) / FILE, data)


def add_search(folder: Path, cache: Path | None = None) -> list[str]:
    """Remember a folder to search for this project's repos, on this machine only."""
    f = Path(folder).expanduser()
    if not f.is_dir():
        raise ValueError("folder")
    data = load(cache)
    if str(f.resolve()) not in data["search"]:
        data["search"].append(str(f.resolve()))
        _save(data, cache)
    return data["search"]


def _origin(d: Path) -> str:
    return services.current().repos.git(d, "remote", "get-url", "origin", check=False)


def _same(a: str, b: str) -> bool:
    return bool(a and b) and remote_key(a) == remote_key(b)


def _clones(folders: list[Path]) -> dict[str, Path]:
    """remote key → the first real clone with that origin, the workspace first; links are never followed."""
    links, out = services.current().links, {}
    for folder in folders:
        try:
            dirs = sorted(d for d in folder.iterdir() if d.is_dir() and not links._is_link(d))
        except OSError:
            continue
        for d in dirs:
            if d.name.startswith(".") or d.name == CAM_DIR or not (d / ".git").exists():
                continue
            if o := _origin(d):
                out.setdefault(remote_key(o), d.resolve())
    return out


def find(log: Log = print) -> dict:
    """Each repo of workspace.yaml as here · linked · missing · taken (`path`: the clone a link points at, or the one
    found but not linkable). Links what it finds; idempotent."""
    links, data = services.current().links, load()
    before = {k: (dict(v) if isinstance(v, dict) else list(v)) for k, v in data.items()}
    rows, clones = [], None

    def add(name: str, url: str, state: str, path: str = "") -> None:
        rows.append({"name": name, "url": url, "state": state, "path": path})

    for r in services.current().workspace.workspace()["repos"]:
        name, url = r["name"], (r.get("url") or "").strip()
        dst = WORKSPACE / name
        if name in data["links"]:
            if links._is_link(dst) and _same(_origin(dst), url):
                add(name, url, "linked", os.path.realpath(dst))
                continue
            if links._is_link(dst):                 # its clone is gone, or is another repo now: search again
                links._unlink(dst)
            del data["links"][name]
        if (dst / ".git").exists():
            o = _origin(dst)
            add(name, url, "here" if not url or not o or _same(o, url) else "taken")
        elif os.path.lexists(dst) or not url:
            add(name, url, "taken" if os.path.lexists(dst) else "missing")
        else:
            clones = _clones([WORKSPACE, *map(Path, data["search"])]) if clones is None else clones
            found = clones.get(remote_key(url))
            if found and links.link(dst, found, log):
                data["links"][name] = str(found)
                _exclude(name, data)
                add(name, url, "linked", str(found))
            else:
                add(name, url, "missing", str(found or ""))
    if data != before:
        _save(data)
    return {"rows": rows, **{s: [r["name"] for r in rows if r["state"] == s] for s in STATES}}


def _exclude_file() -> Path:
    return WORKSPACE / ".git" / "info" / "exclude"


def _exclude(name: str, data: dict) -> None:
    """A workspace under git sees each link as untracked: hidden locally, and only a line the kit added is recorded."""
    f = _exclude_file()
    if (WORKSPACE / ".git").is_dir() and f"/{name}" not in (f.read_text(encoding="utf-8").splitlines() if f.is_file() else []):
        services.current().links.git_exclude(WORKSPACE, f"/{name}")
        data["excluded"].append(name)


def links_made() -> dict[str, str]:
    links = services.current().links
    return {n: t for n, t in load()["links"].items() if links._is_link(WORKSPACE / n)}


def unlink_all(log: Log = print) -> list[str]:
    """Remove the links the kit made (never a clone, never a link of the person's) and the exclude lines it added."""
    links, data = services.current().links, load()
    gone = [n for n in data["links"] if links._is_link(WORKSPACE / n)]
    for n in gone:
        links._unlink(WORKSPACE / n)
    f = _exclude_file()
    if data["excluded"] and f.is_file():
        drop = {f"/{n}" for n in data["excluded"]}
        keep = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln not in drop]
        f.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
    if data["links"] or data["excluded"]:
        _save({**data, "links": {}, "excluded": []})
    if gone:
        log(f"✔ {WORKSPACE.name}/: links to your clones removed ({', '.join(gone)})")
    return gone

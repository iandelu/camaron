"""Optional skill packs and the skills' switches.

A pack is a third-party set of skills the kit knows about (`skills_catalog.yaml`): off until a person adds it.
`add` fetches the pack's repo at its pinned commit and copies its skills into the team's folder
(`cam-docs/.camarones/skills/`), so they are team-only skills: rendered like any other, approved once per machine by
`camaron trust`, and shared with a pull. `.camarones/skills.lock` remembers what came from where.

Two switches turn a rendered skill off: the project's (`skills: {off: [...]}` in workspace.yaml, read by
`skills.sources()`, so nobody gets it) and this machine's (`skills_off` in the machine prefs), which leaves the team's
files alone and writes `Skill(<name>)` deny rules into the local, git-ignored `.claude/settings.local.json` that Claude
Code reads. The kit adds and removes only the rules it wrote; the person's own rules stay. Codex has no such rule."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

import yaml

from .common import CACHE, PREFS, ROOT, WORKSPACE, is_link, load_json, own_file, rmtree, run, save_json, through_link
from .core import yamlio
from . import skills

CATALOG = Path(__file__).with_name("skills_catalog.yaml")
LOCK_HEADER = "# Written by `camaron skills add|remove`: the optional skill packs vendored in .camarones/skills/.\n"
DENIED = CACHE / "skills-denied.json"            # the deny rules the kit wrote, so it never removes the person's own


def catalog() -> dict:
    data = yamlio.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    return {"icons": dict(data.get("icons") or {}), "packs": dict(data.get("packs") or {})}


def lock_path() -> Path | None:
    t = skills.team_dir()
    return None if t is None else t.parent / "skills.lock"


def load_lock() -> dict:
    p = lock_path()
    if p is None or not p.is_file() or through_link(ROOT, p):
        return {}
    data = yamlio.safe_load(p.read_text(encoding="utf-8")) or {}
    return dict(data.get("packs") or {}) if isinstance(data, dict) else {}


def save_lock(entries: dict) -> None:
    p = lock_path()
    if p is None or not own_file(ROOT, p):
        raise ValueError(".camarones/skills.lock goes through a link: it is never written through it")
    if not entries:
        p.unlink(missing_ok=True)
        return
    p.write_text(LOCK_HEADER + yaml.safe_dump({"packs": dict(sorted(entries.items()))}, sort_keys=False,
                                              allow_unicode=True), encoding="utf-8", newline="\n")


def pack_of(name: str) -> str | None:
    """The pack a skill came with: the one that added it here, else the catalog's."""
    for pack, entry in load_lock().items():
        if name in (entry.get("skills") or {}):
            return pack
    return next((pack for pack, p in catalog()["packs"].items() if name in (p.get("skills") or [])), None)


def icon(name: str) -> str:
    cat = catalog()
    pack = pack_of(name)
    return cat["icons"].get(name) or (cat["packs"].get(pack, {}).get("icon", "") if pack else "")


def available() -> list[dict]:
    """The catalog's packs this project has not added, for the panel and `skills list`."""
    added = load_lock()
    return [{"name": n, "title": p.get("title", n), "icon": p.get("icon", ""), "summary": p.get("summary") or {},
             "license": p.get("license", ""), "runs_code": bool(p.get("runs_code")), "source": p.get("source", ""),
             "skills": list(p.get("skills") or [])}
            for n, p in sorted(catalog()["packs"].items()) if n not in added]


# ---------- adding and removing a pack ----------

def _fingerprint(folder: Path) -> str:
    """The skill folder's files as the renderer reads them (dot-files left out), so an edit shows and a re-add does not."""
    h = hashlib.sha256()
    for f in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = f.relative_to(folder)
        if any(part.startswith(".") for part in rel.parts):
            continue
        h.update(rel.as_posix().encode("utf-8") + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def fetch(source: str, commit: str, into: Path) -> Path:
    """The pack's repo checked out at `commit` in `into`: a shallow fetch of that commit, or a clone when the remote
    does not serve a commit by its id. ValueError when neither has it."""
    repo = into / "repo"
    repo.mkdir(parents=True)
    q = dict(cwd=repo, check=False, quiet=True)
    run(["git", "init", "-q"], **q)
    if run(["git", "fetch", "-q", "--depth", "1", source, commit], **q).returncode != 0:
        rmtree(repo)
        r = run(["git", "clone", "-q", "--no-checkout", source, str(repo)], cwd=into, check=False, quiet=True)
        if r.returncode != 0:
            raise ValueError(f"cannot fetch {source}: {((r.stderr or '').strip().splitlines() or ['git failed'])[-1]}")
        target = commit
    else:
        target = "FETCH_HEAD"
    if run(["git", "checkout", "-q", "--detach", target], **q).returncode != 0:
        raise ValueError(f"cannot fetch {source} at {commit}: no such commit")
    head = run(["git", "rev-parse", "HEAD"], cwd=repo, check=False, capture=True).stdout.strip()
    if head != commit:
        raise ValueError(f"cannot fetch {source} at {commit}: got {head or 'nothing'}")
    return repo


def _team_dir() -> Path:
    t = skills.team_dir()
    if t is None:
        raise ValueError("skill packs need the cam-docs layout")
    if skills._linked_team_dir() or through_link(ROOT, t):
        raise ValueError(".camarones/skills is a link: skills are never written through it")
    return t


def add(name: str) -> dict:
    """Vendor pack `name` at its pinned commit; nothing is written when any check fails."""
    pack = catalog()["packs"].get(name)
    if not pack:
        raise ValueError(f"no optional skill pack called {name} (see `skills list`)")
    team, lock = _team_dir(), load_lock()
    if name in lock:
        raise ValueError(f"{name} is already added: `skills remove {name}` first to fetch it again")
    names = list(pack.get("skills") or [])
    clash = [n for n in names if (team / n).exists() or n in skills.kit_names()]
    if clash:
        raise ValueError(f"{', '.join(clash)}: a skill with that name is already here, so {name} was not added")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = fetch(str(pack["source"]), str(pack["commit"]), Path(tmp))
        base = repo / str(pack.get("path") or ".")
        missing = [n for n in names if not (base / n / "SKILL.md").is_file()]
        if missing:
            raise ValueError(f"{name} at {pack['commit'][:7]} has no {', '.join(missing)}")
        extra = [repo / f for f in pack.get("files") or []]
        done: dict[str, str] = {}
        try:
            for n in names:
                dest = team / n
                shutil.copytree(base / n, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                for f in extra:
                    if f.is_file():
                        shutil.copyfile(f, dest / f.name)
                done[n] = _fingerprint(dest)
        except OSError:
            for n in done:
                rmtree(team / n)
            raise
    lock[name] = {"source": pack["source"], "commit": pack["commit"], "skills": done}
    save_lock(lock)
    return lock[name]


def remove(name: str) -> dict:
    """Drop pack `name`: its folders still as fetched go, an edited one stays (it is the team's now)."""
    team, lock = _team_dir(), load_lock()
    if name not in lock:
        raise ValueError(f"{name} is not added here")
    out: dict[str, list[str]] = {"removed": [], "kept": []}
    for n, digest in sorted((lock[name].get("skills") or {}).items()):
        d = team / n
        if not d.is_dir() or is_link(d):
            continue
        if _fingerprint(d) == digest:
            rmtree(d)
            out["removed"].append(n)
        else:
            out["kept"].append(n)
    del lock[name]
    save_lock(lock)
    return out


# ---------- this machine's switch (Claude Code) ----------

def machine_off() -> set[str]:
    off = load_json(PREFS, {}).get("skills_off")
    return {n for n in off if isinstance(n, str)} if isinstance(off, list) else set()


def set_machine(name: str, on: bool) -> None:
    prefs = load_json(PREFS, {})
    off = machine_off() - {name} if on else machine_off() | {name}
    prefs["skills_off"] = sorted(off)
    save_json(PREFS, prefs)
    apply_machine()


def _settings_files() -> list[Path]:
    """Where Claude Code reads this machine's own settings for the project: the workspace folder (where the app opens
    agents) and cam-docs. A `.claude` that is a link counts only when it points at cam-docs' own `.claude`; a
    settings.local.json that is itself a link is never written through."""
    home = Path(os.path.realpath(ROOT / ".claude"))
    out: list[Path] = []
    for d in (WORKSPACE / ".claude", ROOT / ".claude"):
        if not d.is_dir():
            continue
        real = Path(os.path.realpath(d))
        if real not in (home, d.absolute()) or real in {f.parent for f in out}:
            continue
        f = real / "settings.local.json"
        if not is_link(f):
            out.append(f)
    return out


def apply_machine() -> None:
    """Bring the kit's `Skill(<name>)` deny rules in each local settings file in line with this machine's switch. A
    rule is the kit's in a file only when the kit added it there: one the person had already stays when the skill
    comes back on."""
    want = sorted(f"Skill({n})" for n in machine_off())
    owned = load_json(DENIED, {})
    owned = owned if isinstance(owned, dict) else {}
    now: dict[str, list[str]] = {}
    for f in _settings_files():
        data = load_json(f, {}) if f.is_file() else {}
        if not isinstance(data, dict):
            continue
        ours = {r for r in owned.get(str(f)) or [] if isinstance(r, str)}
        perms = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}
        deny = perms.get("deny") if isinstance(perms.get("deny"), list) else []
        kept = [r for r in deny if not (r in ours and r not in want)]
        added = [r for r in want if r not in kept]
        now[str(f)] = sorted((ours & set(want)) | set(added))
        if kept + added == deny:
            continue
        perms = {**perms, "deny": kept + added} if kept + added else {k: v for k, v in perms.items() if k != "deny"}
        data = {**data, "permissions": perms} if perms else {k: v for k, v in data.items() if k != "permissions"}
        save_json(f, data)
    save_json(DENIED, {k: v for k, v in now.items() if v})

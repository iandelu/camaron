"""The guardrails across the project (P3): where they go, and installing, checking and drift of all of them. The pieces
are the adapters' (adapters/guard.py: git hooks and Claude Code attribution; adapters/guard_gate.py: the gate), reached
through `services`. `guard: {install: false}` in workspace.yaml leaves a project out of setup and repair; the gate
(`camaron guard gate`) is never switched off."""
from __future__ import annotations

from pathlib import Path

from lib import skills_packs
from lib.app import services
from lib.common import CAM_DIR, CAM_LAYOUT, ROOT, repo_dir
from lib.ports import Log


def enabled() -> bool:
    return (services.current().workspace.workspace().get("guard") or {}).get("install") is not False


def targets(only: list[str] | None = None) -> list[dict]:
    """Where the guardrails go: each repo of the workspace that is a clone, and cam-docs. `settings`: the local Claude
    Code settings that read there: a repo's own, and for cam-docs the workspace folder's too (where agents open)."""
    found = [{"name": n, "path": repo_dir(n), "docs": False, "settings": [repo_dir(n) / ".claude" / "settings.local.json"]}
             for n in services.current().workspace.repo_names() if (repo_dir(n) / ".git").exists()]
    if CAM_LAYOUT and (ROOT / ".git").exists():
        found.append({"name": CAM_DIR, "path": ROOT, "docs": True, "settings": skills_packs._settings_files()})
    return [t for t in found if only is None or t["name"] in only]


def install(log: Log = print, only: list[str] | None = None) -> list[str]:
    """The hook folder, each target's git config and its settings. Idempotent; returns the names that changed."""
    if not enabled():
        return []
    g = services.current().guard
    g.install_hooks()
    changed = []
    for t in targets(only):
        hooks = g.install_repo(t["path"], docs=t["docs"])
        settings = g.install_attribution(t["settings"])
        if hooks or settings:
            changed.append(t["name"])
            log(f"{t['name']}: git hooks on (no AI co-author, no staged secret"
                + (", docs check on push" if t["docs"] else "") + ") and Claude Code attribution off")
    return changed


def uninstall(log: Log = print, only: list[str] | None = None) -> list[str]:
    """Give each target's repo its own hooks back and take the kit's attribution setting out. Returns the names."""
    g = services.current().guard
    gone = []
    for t in targets(only):
        hooks, settings = g.uninstall_repo(t["path"]), g.uninstall_attribution(t["settings"])
        if hooks or settings:
            gone.append(t["name"])
            log(f"{t['name']}: git hooks and Claude Code attribution put back as they were")
    return gone


def status() -> list[dict]:
    """One row per target: `hooks` is why the kit's hooks do not run there (None: they do), `attribution` whether
    every local settings file that reads there has Claude Code's attribution off."""
    g = services.current().guard
    return [{"name": t["name"], "path": str(t["path"]), "docs": t["docs"], "hooks": g.hooks_off(t["path"]),
             "attribution": not g.attribution_on(t["settings"])} for t in targets()]


def drift() -> list[dict]:
    """What `setup` or `repair` would put back, in install_state's shape."""
    if not enabled():
        return []
    out = []
    for row in status():
        if row["hooks"]:
            out.append({"path": row["name"], "state": "off", "what": "git hooks", "why": row["hooks"]})
        if not row["attribution"]:
            out.append({"path": row["name"], "state": "off", "what": "Claude Code attribution"})
    return out


def gate(names: list[str] | None = None, *, base: str | None = None, latest: bool = False, log: Log = print) -> list[dict]:
    """The gate's report for each service repo (cam-docs has no code to gate)."""
    g, ws = services.current().guard_gate, services.current().workspace.workspace()
    return [g.gate(t["name"], t["path"], ws, base=base, latest=latest, log=log) for t in targets(names) if not t["docs"]]

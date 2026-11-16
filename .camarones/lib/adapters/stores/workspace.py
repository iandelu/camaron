"""The project's workspace.yaml (which repos form the project, the interview mode, the repos that get a wiki) and the
block of cam-docs' .gitignore that follows those repos. Behind lib/ports/workspace_store.py."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from lib.core import yamlio
from lib.common import CAM_LAYOUT, ROOT, WORKSPACE, WS_FILE, through_link

GI_START, GI_END = "# >>> camarones repos >>>", "# <<< camarones repos <<<"
WS_HEADER = "# Camarón workspace: which repos form this project. Edit freely, then run sync.\n"


def ws_file() -> Path:
    legacy = ROOT / "workspace.yaml"
    if legacy.exists() and not WS_FILE.exists():      # migrate older layout
        WS_FILE.parent.mkdir(parents=True, exist_ok=True)
        legacy.replace(WS_FILE)
    return WS_FILE


def workspace() -> dict:
    ws = (yamlio.safe_load(ws_file().read_text(encoding="utf-8")) if ws_file().exists() else None) or {}
    ws.setdefault("project", {})
    ws.setdefault("repos", [])
    ws["project"].setdefault("name", WORKSPACE.name)
    ws["project"].setdefault("translations", ["es"])
    return ws


def save_workspace(ws: dict) -> None:
    write_workspace(ws_file(), ws)


def write_workspace(ws_file: Path, ws: dict) -> None:
    ws_file.parent.mkdir(parents=True, exist_ok=True)   # global install: .camarones/ may not exist yet
    ws_file.write_text(WS_HEADER + yaml.safe_dump(ws, sort_keys=False, allow_unicode=True), encoding="utf-8",
                       newline="\n")


def repo_names() -> list[str]:
    return [r["name"] for r in workspace()["repos"]]


def wiki_repos() -> list[str]:
    """Repos that get an OpenWiki (`wiki: true` in workspace.yaml). None chosen → none: a wiki per repo costs a full
    agent run, and libraries or CI repos rarely need one."""
    return [r["name"] for r in workspace()["repos"] if r.get("wiki")]


INTERVIEW_MODES = ("live", "team")


def interview_mode() -> str:
    """`live`: the agent interviews the user in a session. `team`: a questionnaire the team answers offline, then agent
    units consolidate the answers. Projects without the key (every 3.x project so far) keep `live`."""
    mode = workspace()["project"].get("interviews")
    return mode if mode in INTERVIEW_MODES else "live"


def interview_mode_chosen() -> bool:
    """Someone picked the mode (wizard, app, `interview mode`): `live` alone is only the fallback, and an interview
    unit does not start on it."""
    return workspace()["project"].get("interviews") in INTERVIEW_MODES


def set_interview_mode(mode: str) -> None:
    if mode not in INTERVIEW_MODES:
        raise ValueError(f"interview mode must be one of {', '.join(INTERVIEW_MODES)}")
    ws = workspace()
    ws["project"]["interviews"] = mode
    save_workspace(ws)


def set_wiki_repos(names: list[str]) -> None:
    ws = workspace()
    for r in ws["repos"]:
        r["wiki"] = r["name"] in names
    save_workspace(ws)


def write_gitignore() -> None:
    gi = ROOT / ".gitignore"
    if through_link(ROOT, gi):                          # a committed link: never read or written through
        return
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    repos = [] if CAM_LAYOUT else [f"/{n}/" for n in repo_names()]      # cam-docs layout: repos live next to it
    block = "\n".join([GI_START, *repos, "/.camarones/.cache/", "/graph/", "/.claude/settings.local.json",
                       # anchored: unanchored, they also hid docs/repos/<repo>/ and wikis/<repo>/ of a repo named
                       # like the kit; the kit is unzipped or cloned at the project root only (lib/upgrade.py)
                       "/camarones-documenter*/", "/camarones-kit*/", "camarones-documenter*.zip", ".DS_Store", GI_END])
    if GI_START in text:
        text = re.sub(re.escape(GI_START) + r".*?" + re.escape(GI_END), lambda _: block, text, flags=re.S)
    else:
        text = (text.rstrip() + "\n\n" if text.strip() else "") + block + "\n"
    gi.write_text(text, encoding="utf-8")

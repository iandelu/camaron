"""The docs' incremental state: the commit of each repo the docs last matched (docs/.state.json), how each repo changed
since, and where the pages' status is written (docs/.status.json). Behind lib/ports/doc_state.py."""
from __future__ import annotations

import subprocess

from lib.adapters.git import repos
from lib.adapters.stores import workspace
from lib.common import DOCS, load_json, repo_dir, save_json
from lib.core.clock import now

STATE_FILE = DOCS / ".state.json"
STATUS_FILE = DOCS / ".status.json"


def changes() -> dict:
    state, out = load_json(STATE_FILE, {"repos": {}}), {}
    for r in workspace.workspace()["repos"]:
        path = repo_dir(r["name"])
        if not (path / ".git").exists():
            out[r["name"]] = {"status": "missing"}
            continue
        head = repos.git(path, "rev-parse", "HEAD", check=False)
        last = state["repos"].get(r["name"], {}).get("sha")
        if not last:
            out[r["name"]] = {"status": "never-documented", "head": head}
        elif last == head:
            out[r["name"]] = {"status": "up-to-date", "head": head}
        else:
            known = subprocess.run(["git", "-C", str(path), "cat-file", "-e", f"{last}^{{commit}}"],
                                   capture_output=True).returncode == 0
            files = repos.git(path, "diff", "--name-status", f"{last}..{head}").splitlines() if known else []
            out[r["name"]] = {"status": "changed" if known else "history-rewritten", "from": last, "head": head, "files": files}
    for name in sorted(set(state["repos"]) - set(workspace.repo_names())):
        out[name] = {"status": "removed-from-workspace"}
    return out


def mark_documented(names: list[str] | None = None) -> list[str]:
    state = load_json(STATE_FILE, {"repos": {}})
    names = names or workspace.repo_names()
    for n in names:
        state["repos"][n] = {"sha": repos.git(repo_dir(n), "rev-parse", "HEAD"), "at": now()}
    for n in set(state["repos"]) - set(workspace.repo_names()):
        del state["repos"][n]
    save_json(STATE_FILE, state)
    return names

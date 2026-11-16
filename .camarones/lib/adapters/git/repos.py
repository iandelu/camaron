"""The project's repos as git checkouts: clone the missing ones, fast-forward the clean ones (tokens injected per call),
find the repos already sitting in a folder, and run git in one of them. Behind lib/ports/repo_sync.py."""
from __future__ import annotations

import os, re, subprocess
from pathlib import Path

from lib.adapters.stores import workspace
from lib.common import CAM_DIR, WORKSPACE, repo_dir
from lib.ports import Log


def git(repo: Path, *args: str, check=True, env: dict | None = None) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, **(env or {})})
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo.name}: {r.stderr.strip()}")
    return r.stdout.strip()


def detect_repos(workspace: Path | None = None) -> list[dict]:
    """Repos already sitting in the workspace folder (the 'drop the kit next to your repos' case). `workspace`: any
    folder, e.g. one picked before a project exists; default is this project's."""
    found = []
    for d in sorted(p for p in (workspace or WORKSPACE).iterdir() if p.is_dir() and (p / ".git").exists()):
        if d.name.startswith(".") or d.name in ("docs", CAM_DIR) or d.name.lower().startswith("camarones-"):
            continue
        url = git(d, "remote", "get-url", "origin", check=False)
        branch = git(d, "rev-parse", "--abbrev-ref", "HEAD", check=False) or "main"
        found.append({"name": d.name, "url": url or "", "branch": branch, "kind": guess_kind(d)})
    return found


def guess_kind(d: Path) -> str:
    if (d / "pubspec.yaml").exists():
        return "mobileApp"
    if (d / "package.json").exists() and not any((d / f).exists() for f in ("pom.xml", "build.gradle", "build.gradle.kts")):
        pkg = (d / "package.json").read_text(encoding="utf-8", errors="ignore")
        if any(k in pkg for k in ('"react"', '"vue"', '"@angular/core"', '"svelte"', '"next"')):
            return "webapp"
    if any((d / f).exists() for f in ("Chart.yaml", "main.tf", "kustomization.yaml")):
        return "infra"
    return "service"


def sync_repos(log: Log = print) -> list[str]:
    """Clone missing repos, fast-forward clean ones. Tokens (🔑) are injected per call, never stored in the repos."""
    from lib import creds
    failed = []
    for r in workspace.workspace()["repos"]:
        path, branch, url = repo_dir(r["name"]), r.get("branch", "main"), r.get("url", "")
        env = creds.git_env(url)
        if not (path / ".git").exists():
            if not url:
                log(f"⚠ {r['name']}: no url and not present — skipped")
                continue
            log(f"cloning {r['name']} ({branch})…")
            p = subprocess.run(["git", "clone", "--branch", branch, url, str(path)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env={**os.environ, **env})
            if p.returncode != 0:
                failed.append(r["name"])
                hint = " — add a GitLab/GitHub token (🔑)" if re.search(r"auth|denied|403|401|could not read|permission",
                                                                       p.stderr, re.I) else ""
                log(f"⚠ {r['name']}: clone failed{hint}: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ''}")
        elif not url:
            log(f"local  {r['name']} (no remote)")
        elif git(path, "status", "--porcelain", "--untracked-files=no", check=False):
            log(f"skip   {r['name']}: local changes, not pulling")
        else:
            log(f"pulling {r['name']} ({branch})…")
            try:
                git(path, "fetch", "--quiet", "origin", branch, env=env)
                git(path, "checkout", "--quiet", branch)
                git(path, "merge", "--ff-only", "--quiet", f"origin/{branch}")
            except RuntimeError as e:
                # The repo is already cloned locally — a remote that 404s or rejects auth (renamed,
                # made private, deleted, expired token) shouldn't block work on what's already there.
                hint = " — add a GitLab/GitHub token (🔑)" if re.search(r"auth|denied|403|401|could not read", str(e), re.I) else ""
                if re.search(r"not found|repository .* not found", str(e), re.I):
                    hint = " — check the repo still exists at that URL/org, or that you have access"
                log(f"⚠ {r['name']}: remote unreachable, using local copy as-is{hint}: {e}")
    workspace.write_gitignore()
    return failed

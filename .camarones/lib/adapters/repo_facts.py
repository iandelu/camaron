"""Static facts of one repo for the repo dashboard: stack pills, build tool, head, weekly activity, outdated library
count and code-graph size. Read from the checkout, the stored inventory and the graph file; no model, no network."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .. import history, inventory, latest, quickarch, radar
from ..common import CACHE, out, repo_dir
from ..core import fsutil
from . import graphify
from .stores import workspace

BUILD_LABELS = {"maven": "Maven", "gradle": "Gradle", "npm": "npm", "pnpm": "pnpm", "yarn": "Yarn", "uv": "uv",
                "poetry": "Poetry", "pip": "pip", "go": "Go modules"}
CONTAINERS = {"docker": "Docker", "compose": "Docker Compose", "helm": "Helm"}
PIPELINES = {"gitlab-ci": "GitLab CI", "github-actions": "GitHub Actions", "jenkins": "Jenkins",
             "azure-pipelines": "Azure Pipelines"}
EMPTY = {"head": None, "stack": [], "build": None, "activity": None}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def build_tool(path: Path) -> str | None:
    has = lambda *names: any((path / n).exists() for n in names)
    if has("pom.xml"):
        return "maven"
    if has("build.gradle", "build.gradle.kts"):
        return "gradle"
    if has("package.json"):
        return "pnpm" if has("pnpm-lock.yaml") else "yarn" if has("yarn.lock") else "npm"
    if has("pyproject.toml"):
        return "poetry" if has("poetry.lock") else "uv" if has("uv.lock") else "pip"
    if has("requirements.txt"):
        return "pip"
    return "go" if has("go.mod") else None


def _tip(path: Path) -> tuple[str, str] | None:
    """HEAD's full sha and branch in one git call: the cache key, the only process a cache hit costs."""
    lines = out(["git", "-C", str(path), "rev-parse", "HEAD", "--abbrev-ref", "HEAD"]).splitlines()
    return (lines[0], lines[1]) if len(lines) == 2 and all(lines) else None


def _head(path: Path, branch: str) -> dict | None:
    line = out(["git", "-C", str(path), "log", "-1", "--format=%h%x09%at%x09%aN%x09%s"])
    if not line:
        return None
    sha, at, author, subject = (line.split("\t", 3) + ["", "", "", ""])[:4]
    return {"branch": branch, "sha": sha[:7], "at": int(at) if at.isdigit() else 0, "subject": subject, "author": author}


def _data(path: Path) -> list[str]:
    text = ""
    for name in quickarch.MANIFESTS:
        try:
            text += (path / name).read_text(encoding="utf-8", errors="ignore").lower() + "\n"
        except OSError:
            pass
    labels = [label for key, label in quickarch.DEP_DB.items() if label and key in text]
    if any(key in text for key in quickarch.CACHE_DEPS):
        labels.append("Redis")
    return list(dict.fromkeys(labels))


def _override(name: str) -> str:
    row = next((r for r in workspace.workspace()["repos"] if r["name"] == name), {})
    return row.get("stack") or ""


def _stack(name: str, path: Path, build: str | None, override: str) -> list[dict]:
    text = override or quickarch.stack(path, quickarch.repo_blob(path))
    first, *rest = [p.strip() for p in text.split(" · ") if p.strip()] or ["?"]
    pills = [{"role": "language", "label": first}] if first != "?" else []
    pills += [{"role": "framework", "label": p} for p in rest]
    if build:
        pills.append({"role": "build", "label": BUILD_LABELS[build]})
    pills += [{"role": "data", "label": label} for label in _data(path)]
    found = {t["id"] for t in radar.scan_repo(name, path)}
    pills += [{"role": "container", "label": label} for key, label in CONTAINERS.items() if key in found]
    pills += [{"role": "ci", "label": label} for key, label in PIPELINES.items() if key in found]
    return pills


def _week() -> str:
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _lock(name: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(name, threading.Lock())


def facts(name: str) -> dict:
    path = repo_dir(name)
    if not path.is_dir():
        return dict(EMPTY)
    with _lock(name):            # the server is threaded: two requests at once scan the repo once
        return _facts(name, path)


def _facts(name: str, path: Path) -> dict:
    tip = _tip(path)
    if tip is None:
        return dict(EMPTY)
    override = _override(name)
    key = {"head": tip[0], "branch": tip[1], "week": _week(), "stack": override}
    cache = CACHE / "repos" / f"{name}.json"
    stored = fsutil.load_json(cache, {})
    if stored.get("key") == key and "facts" in stored:
        return stored["facts"]
    head = _head(path, tip[1])
    if head is None:
        return dict(EMPTY)
    build = build_tool(path)
    found = {"head": head, "stack": _stack(name, path, build, override), "build": build,
             "activity": history.activity(name)}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"key": key, "facts": found}), encoding="utf-8", newline="\n")
    except OSError:
        pass
    return found


def outdated(name: str) -> int | None:
    data = inventory.load()
    versions = (data.get("latest") or {}).get("versions")
    if versions is None:
        return None
    seen = {(r["ecosystem"], r["name"]): r.get("version") for r in data.get("libraries") or []
            if r.get("repo") == name}
    return sum(1 for (eco, lib), version in seen.items() if latest.newer(version, versions.get(f"{eco}|{lib}")))


def graph_nodes(name: str) -> int | None:
    try:
        return len(json.loads(graphify.repo_graph(name).read_text(encoding="utf-8"))["nodes"])
    except (OSError, ValueError, KeyError, TypeError):
        return None

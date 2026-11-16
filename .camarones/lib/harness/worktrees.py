"""Unit worktrees (R11): a unit that runs in parallel writes its docs in its own git worktree of cam-docs, at
<workspace>/.cw/<n> on branch cam/u/<n>-<unit>. Numbered folders keep paths short and valid on Windows (unit ids
contain ':'). The registry in the state root's cache lets a new process find the worktree of a killed run again."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from ..common import IS_WIN, load_json, rmtree, run, save_json
from .ctx import Ctx
from .locks import FileLock

FOLDER = ".cw"


@dataclass(frozen=True)
class Worktree:
    unit: str
    n: int
    path: Path
    branch: str


def slug(uid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", uid).strip("-.")[:40] or "unit"


def _git(repo: Path, *args: str, cwd: Path | None = None, check: bool = True):
    return run(["git", *args], cwd=cwd or repo, check=check, capture=True)


def _usable(repo: Path, path: Path) -> bool:
    return (path / ".git").exists() and _git(repo, "rev-parse", "--is-inside-work-tree", cwd=path, check=False).returncode == 0


def _branch_exists(repo: Path, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


def attach(repo: Path, path: Path, branch: str, base: str = "HEAD") -> None:
    """A worktree of `repo` at `path` on `branch`: the existing one (with its uncommitted work), its folder rebuilt from
    the branch, or a new branch from `base`. The caller holds whatever lock guards its own registry."""
    if IS_WIN:
        _git(repo, "config", "core.longpaths", "true")
    if _usable(repo, path):
        return
    if path.exists():
        rmtree(path)
    _git(repo, "worktree", "prune")
    path.parent.mkdir(parents=True, exist_ok=True)
    if _branch_exists(repo, branch):
        _git(repo, "worktree", "add", str(path), branch)
    else:
        _git(repo, "worktree", "add", "-b", branch, str(path), base)


def detach(repo: Path, path: Path) -> None:
    """The worktree at `path` goes, uncommitted work included; its branch stays."""
    for attempt in range(5):           # Windows: an editor, the antivirus or a watcher may hold a file a moment
        if _git(repo, "worktree", "remove", "--force", str(path), check=False).returncode == 0 or not path.exists():
            break
        time.sleep(0.2 * (attempt + 1))
    if path.exists():
        rmtree(path)
    _git(repo, "worktree", "prune")


class Worktrees:
    def __init__(self, ctx: Ctx):
        self.repo = ctx.state_root
        self.base = (ctx.workspace / FOLDER).resolve()
        cache = ctx.state_root / ".camarones" / ".cache"
        self.registry, self.lock = cache / "worktrees.json", cache / "locks" / "worktrees.lock"

    def _git(self, *args: str, cwd: Path | None = None, check: bool = True):
        return _git(self.repo, *args, cwd=cwd, check=check)

    def _load(self) -> dict:
        return load_json(self.registry, {})

    def _entry(self, uid: str, e: dict) -> Worktree:
        return Worktree(uid, e["n"], Path(e["path"]), e["branch"])

    def get(self, uid: str) -> Worktree | None:
        e = self._load().get(uid)
        return self._entry(uid, e) if e else None

    def list(self) -> list[Worktree]:
        return [self._entry(uid, e) for uid, e in sorted(self._load().items(), key=lambda kv: kv[1]["n"])]

    def _branch_exists(self, branch: str) -> bool:
        return _branch_exists(self.repo, branch)

    def add(self, uid: str, base: str = "HEAD") -> Worktree:
        """The unit's worktree: the existing one (a killed run's, with its uncommitted work), its folder rebuilt from
        its branch, or a new one from `base`."""
        with FileLock(self.lock):
            reg = self._load()
            if uid in reg:
                w = self._entry(uid, reg[uid])
                attach(self.repo, w.path, w.branch, base)
                return w
            used = {e["n"] for e in reg.values()}
            n = next(i for i in range(1, len(used) + 2) if i not in used and not (self.base / str(i)).exists())
            w = Worktree(uid, n, self.base / str(n), f"cam/u/{n}-{slug(uid)}")
            attach(self.repo, w.path, w.branch, base)
            reg[uid] = {"n": w.n, "path": str(w.path), "branch": w.branch}
            save_json(self.registry, reg)
            return w

    def remove(self, uid: str, delete_branch: bool = True) -> None:
        with FileLock(self.lock):
            reg = self._load()
            e = reg.pop(uid, None)
            if not e:
                return
            w = self._entry(uid, e)
            detach(self.repo, w.path)
            if delete_branch:
                self._git("branch", "-D", w.branch, check=False)
            save_json(self.registry, reg)
            if self.base.is_dir() and not any(self.base.iterdir()):
                self.base.rmdir()                  # no unit left in parallel: no .cw/ left in the workspace

    def prune(self) -> None:
        """Forget worktrees whose folder and branch are both gone (nothing left to resume)."""
        with FileLock(self.lock):
            self._git("worktree", "prune")
            reg = self._load()
            keep = {uid: e for uid, e in reg.items() if Path(e["path"]).exists() or self._branch_exists(e["branch"])}
            if keep != reg:
                save_json(self.registry, keep)

"""The guardrails installed on this machine (P3): git hooks in each repo through local config only, and Claude Code's
commit/PR attribution turned off in the local settings. Nothing is written into a tracked file of a service repo.

The hooks live in one folder per machine, ~/.camarones/githooks/ (lib/githooks/: `dispatch` copied under every git hook
name, the kit's checks in `kit/`, and `kit-cmd`, how to run this kit). A repo points at it with `core.hooksPath` in its
own .git/config; `camaron.chain` remembers the hooks folder it had (husky's `.husky/_`, say) so the dispatcher runs the
repo's own hooks after the kit's (decision D5); `camaron.check` marks cam-docs, whose push runs `camaron check`."""
from __future__ import annotations

import os
from pathlib import Path

from lib.adapters import fs_links
from lib.common import HOME, IS_WIN, KIT, load_json, out, run, save_json, uv
from lib.domain import guard

HOOKS_DIR = HOME / ".camarones" / "githooks"
SOURCE = KIT / "lib" / "githooks"
# githooks(5), the client side: every one the dispatcher must answer, or a repo's own hook of that name would stop running.
# Not these: `post-index-change`, `reference-transaction` (git runs them on every index or ref write, a shell start each time)
# and `fsmonitor-watchman` (it speaks on stdout): a repo's own hook of those three does not run under the kit's path.
HOOK_NAMES = ("applypatch-msg", "pre-applypatch", "post-applypatch", "pre-commit", "pre-merge-commit",
              "prepare-commit-msg", "commit-msg", "post-commit", "pre-rebase", "post-checkout", "post-merge", "pre-push",
              "post-rewrite", "pre-auto-gc", "sendemail-validate", "push-to-checkout", "p4-changelist",
              "p4-prepare-changelist", "p4-post-changelist", "p4-pre-submit")
SETTINGS = Path(".claude") / "settings.local.json"


def _files() -> dict[str, bytes]:
    """folder-relative name → what it holds; LF whatever a checkout did to the source."""
    dispatch = (SOURCE / "dispatch").read_bytes().replace(b"\r\n", b"\n")
    files = {name: dispatch for name in HOOK_NAMES}
    for f in sorted((SOURCE / "kit").iterdir()):
        files[f"kit/{f.name}"] = f.read_bytes().replace(b"\r\n", b"\n")
    try:                                                 # without uv the kit cannot run: no `check` on push, said at push
        files["kit-cmd"] = f'"{Path(uv()).as_posix()}" run --quiet --script "{(KIT / "camarones.py").as_posix()}"\n'.encode()
    except RuntimeError:
        pass
    return files


def _stale(rel: str, data: bytes) -> bool:
    f = HOOKS_DIR / rel
    return not f.is_file() or f.read_bytes() != data or (rel != "kit-cmd" and not IS_WIN and not os.access(f, os.X_OK))


def install_hooks() -> bool:
    """The machine's hook folder as this kit renders it. True when anything had to be written."""
    changed = False
    for rel, data in _files().items():
        if not _stale(rel, data):
            continue
        f = HOOKS_DIR / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        f.chmod(0o755)
        changed = True
    return changed


def _cfg(repo: Path, key: str, local: bool = False) -> str:
    return out(["git", "config", "--local" if local else "--type=path", "--get", key], cwd=repo)


def _set(repo: Path, key: str, value: str | None) -> None:
    run(["git", "config", "--local", key, value] if value is not None else ["git", "config", "--local", "--unset", key],
        cwd=repo, check=False, quiet=True)


def _ours(value: str) -> bool:
    return bool(value) and os.path.normcase(os.path.realpath(value)) == os.path.normcase(os.path.realpath(HOOKS_DIR))


def install_repo(repo: Path, *, docs: bool = False) -> bool:
    """Point `repo` at the kit's hooks, chaining to the hooks it had. `docs`: cam-docs (its push runs the docs check).
    Idempotent: True when git config changed."""
    changed = False
    current = _cfg(repo, "core.hooksPath")
    if not _ours(current):
        _set(repo, "camaron.chain", current or None)                  # none: the repo's own .git/hooks
        _set(repo, "core.hooksPath", HOOKS_DIR.as_posix())
        changed = True
    if (_cfg(repo, "camaron.check", local=True) == "true") != docs:
        _set(repo, "camaron.check", "true" if docs else None)
        changed = True
    return changed


def has_config(repo: Path) -> bool:
    """Whether anything of the kit's is in the repo's git config."""
    return _ours(_cfg(repo, "core.hooksPath")) or any(_cfg(repo, k, local=True) for k in ("camaron.chain", "camaron.check"))


def uninstall_repo(repo: Path) -> bool:
    """Give the repo back its own hooks folder; True when anything of the kit's was in its config."""
    changed = has_config(repo)
    if _ours(_cfg(repo, "core.hooksPath")):
        _set(repo, "core.hooksPath", _cfg(repo, "camaron.chain", local=True) or None)
    for key in ("camaron.chain", "camaron.check"):
        if _cfg(repo, key, local=True):
            _set(repo, key, None)
    return changed


def hooks_off(repo: Path) -> str | None:
    """Why the kit's hooks do not run in `repo` (what `core.hooksPath` says now), or None when they do."""
    if any(_stale(rel, data) for rel, data in _files().items()):
        return "the kit's hook folder is missing or out of date"
    current = _cfg(repo, "core.hooksPath")
    return None if _ours(current) else f"core.hooksPath is {current}" if current else "core.hooksPath is not set"


def install_attribution(files: list[Path]) -> list[Path]:
    """Claude Code's commit and PR attribution off in each local settings file; the file's other keys stay. A file
    inside a repo is kept out of its history through .git/info/exclude. Returns the files that changed."""
    changed = []
    for f in files:
        data = load_json(f, {}) if f.is_file() else {}
        if not isinstance(data, dict):
            continue                                                   # not ours to rewrite
        if f.parent.parent.joinpath(".git").is_dir():
            fs_links.git_exclude(f.parent.parent, f"/{SETTINGS.as_posix()}")
        if not guard.attribution_is_off(data):
            save_json(f, guard.attribution_off(data))
            changed.append(f)
    return changed


def attribution_on(files: list[Path]) -> list[Path]:
    """The files whose settings still let Claude Code credit itself."""
    return [f for f in files if not isinstance(d := load_json(f, {}) if f.is_file() else {}, dict)
            or not guard.attribution_is_off(d)]


def wrote_attribution(f: Path) -> bool:
    """The file holds exactly what `install_attribution` writes: the kit's, as far as anyone can tell."""
    data = load_json(f, None) if f.is_file() else None
    return isinstance(data, dict) and data.get("attribution") == guard.attribution_off({})["attribution"]


def uninstall_attribution(files: list[Path]) -> list[Path]:
    """Take `attribution` out of the files the kit wrote it to (a file left empty goes, and its empty folder)."""
    gone = []
    for f in files:
        if not wrote_attribution(f):
            continue
        rest = {k: v for k, v in load_json(f, {}).items() if k != "attribution"}
        if rest:
            save_json(f, rest)
        else:
            f.unlink()
            try:
                f.parent.rmdir()
            except OSError:
                pass                                           # the folder holds other files: they stay
        gone.append(f)
    return gone

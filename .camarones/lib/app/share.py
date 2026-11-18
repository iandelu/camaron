"""The team's docs repo: local checkpoint commits that keep docs progress safe in the umbrella repo, and sharing them
with the team (pull + push on demand, or after every checkpoint with auto-share)."""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys

from lib.app import services
from lib.common import CACHE, CTX, ROOT, load_json, out, run, save_json
from lib.ports import Log
from lib.projects import git_failure


# ---------- progress safety: local checkpoint commits in the umbrella repo ----------
def _stderr(line: str) -> None:
    print(line, file=sys.stderr)


def board_repair(warn: Log = _stderr) -> list[str]:
    """The board's repair pass; what it changed. Its warnings go to `warn`; a failure is a warning, never a blocked
    commit. Only the main cam-docs has a board to repair: a unit's worktree leaves it to main."""
    from lib import kanban
    if not kanban.enabled() or CTX.root != CTX.state_root:
        return []
    try:
        from lib.kanban import repair
        res = repair.repair(log=lambda _: None)
    except Exception as e:                                   # noqa: BLE001 — the commit must go on
        warn(f"🦐⚠ board repair skipped: {e}")
        return []
    for w in res["warnings"]:
        warn(f"🦐⚠ board: {w}")
    return res["changed"]


def checkpoint_commit(message: str, warn: Log = _stderr) -> bool:
    """Commit docs progress locally. Keeps work safe if a session or the computer closes; pushes only with auto-share.
    The board repair's warnings go to `warn` (stderr unless a caller such as share() shows them in its own log)."""
    if not (ROOT / ".git").exists():
        return False
    board_repair(warn)
    paths = services.current().vcs.checkpoint_paths()
    if CTX.root != CTX.state_root:   # a unit's worktree: its pages only; derived files, plan state and the board belong to main
        paths = [p for p in paths if p not in ("backlog", ".gitattributes")]
        paths += [":(exclude)docs/.work", ":(exclude)docs/.status.json", ":(exclude)docs/llms.txt",
                  ":(exclude)docs/llms-full.txt"]
    if paths:                                    # (only exclusions would stage everything else)
        paths += [":(exclude,glob)backlog/**/*.tmp"]                   # a board write that died half way
        run(["git", "add", "--", *paths], cwd=ROOT, check=False, quiet=True)
    if run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False, quiet=True).returncode == 0:
        return False
    from lib import quality
    leaks = quality.staged_secrets()
    if leaks:        # left staged, not committed: fix the page, the next checkpoint picks it up
        print("🦐✖ checkpoint not committed — possible secrets staged:\n  " + "\n  ".join(leaks), file=sys.stderr)
        return False
    ident = [] if out(["git", "config", "user.email"], cwd=ROOT) else ["-c", "user.name=Camarón",
                                                                       "-c", "user.email=camarones@localhost"]
    r = run(["git", *ident, "commit", "-q", "-m", f"docs(camarones): {message}", "--no-verify"], cwd=ROOT, check=False, quiet=True)
    if r.returncode:
        return False
    if not _sharing and auto_share() and docs_remote():
        s = share(log=lambda _: None)
        if s["status"] not in ("pushed", "up-to-date", "nothing"):
            why = f" ({s['reason']})" if s.get("reason") else ""
            print(f"🦐 auto-share: {s['status']}{why}: {s['detail']}", file=sys.stderr)
    return True


# ---------- the team's docs repo: pull + push on demand, or after every checkpoint with auto-share ----------
AUTO_SHARE = CACHE / "share.json"                   # per machine: one teammate opting in never pushes for the others
SHARED = CACHE / "shared.json"                      # when this machine last shared (its own file: share.json is the opt-in)
_sharing = False


def auto_share() -> bool:
    return bool(load_json(AUTO_SHARE, {}).get("auto"))


def set_auto_share(on: bool) -> None:
    AUTO_SHARE.parent.mkdir(parents=True, exist_ok=True)
    save_json(AUTO_SHARE, {"auto": bool(on)})


def sync_status(fetch: bool = False) -> dict:
    """Where cam-docs stands against the team's repo, without the network unless `fetch`: the remote and branch, the
    commits ahead / behind the last fetched origin, the files not checkpointed yet, the last commit and last share."""
    git = lambda *a: out(["git", *a], cwd=ROOT)                       # noqa: E731
    url = docs_remote()
    branch = git("symbolic-ref", "--short", "HEAD") if (ROOT / ".git").exists() else ""
    fetched = None
    if url and fetch:
        from lib import creds
        r = run(["git", "fetch", "--quiet", "origin"], cwd=ROOT, check=False, quiet=True, env=creds.git_env(url))
        fetched = {"ok": True, "reason": ""} if r.returncode == 0 else \
            {"ok": False, "reason": git_failure(r.stderr or r.stdout or ""), "host": _remote_host(url), "detail": _git_said(r)}
    ahead = behind = None
    if url and branch and git("rev-parse", "--verify", "--quiet", f"origin/{branch}"):
        counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{branch}").split()
        if len(counts) == 2:
            ahead, behind = int(counts[0]), int(counts[1])
    paths = services.current().vcs.checkpoint_paths()
    pending = []
    if (ROOT / ".git").exists() and paths:
        status = run(["git", "status", "--porcelain", "-uall", "--", *paths], cwd=ROOT, check=False, capture=True).stdout or ""
        pending = sorted({ln[3:].strip().strip('"').split(" -> ")[-1] for ln in status.splitlines() if len(ln) > 3})
    head = git("log", "-1", "--format=%h%x00%s%x00%cI").split("\x00") if branch else []
    return {"remote": url, "branch": branch, "ahead": ahead, "behind": behind, "pending": pending,
            "head": dict(zip(("hash", "subject", "date"), head)) if len(head) == 3 else None,
            "auto": auto_share(), "last_share": load_json(SHARED, {}).get("last"), "fetched": fetched}


def docs_remote() -> str:
    return out(["git", "remote", "get-url", "origin"], cwd=ROOT) if (ROOT / ".git").exists() else ""


def set_remote(url: str) -> None:
    """Point cam-docs at the team's repo (origin). The first share publishes it."""
    if not (ROOT / ".git").exists():
        run(["git", "init", "-q", str(ROOT)], quiet=True)
    run(["git", "remote", "remove", "origin"], cwd=ROOT, check=False, quiet=True)
    from lib.projects import clean_remote
    run(["git", "remote", "add", "origin", clean_remote(url)], cwd=ROOT, quiet=True)


def _remote_host(url: str) -> str:
    from lib import creds
    return (creds.host_of(url) or "") if re.match(r"^[a-z][a-z0-9+.-]*://|^[\w.+-]+@", url, re.I) else ""


def _git_said(r) -> str:
    """git's own words for a failed fetch or push, from its fatal/error line on (its last line alone is often a fragment)."""
    lines = [ln.strip() for ln in (r.stderr or r.stdout or "").strip().splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if ln.lower().startswith(("fatal:", "error:"))), len(lines) - 1)
    return " · ".join(lines[max(start, 0):])[:400]


def _ident() -> list[str]:
    return [] if out(["git", "config", "user.email"], cwd=ROOT) else ["-c", "user.name=Camarón",
                                                                      "-c", "user.email=camarones@localhost"]


def _failed(r: subprocess.CompletedProcess, url: str) -> dict:
    from lib import creds
    host = _remote_host(url)
    reason = git_failure(r.stderr or r.stdout or "")
    if reason == "auth" and host and not creds.get(host):
        reason = "no-token"
    return {"status": "error", "reason": reason, "host": host, "detail": _git_said(r)}


def share(log: Log = print) -> dict:
    """Checkpoint, bring in the team's work (rebase onto origin) and push. Returns {"status", "detail"}:
    pushed · up-to-date · no-remote · nothing · blocked (secrets staged) · conflict (rebase undone) · error."""
    url = docs_remote()
    if not url:
        return {"status": "no-remote", "detail": ""}
    from lib import creds
    from lib.projects import clean_remote
    if clean_remote(url) != url:                                      # stored as typed by an older kit
        url = clean_remote(url)
        run(["git", "remote", "set-url", "origin", url], cwd=ROOT, check=False, quiet=True)
    auth = creds.git_env(url)

    def git(*args: str, env: dict | None = None):
        return run(["git", *args], cwd=ROOT, check=False, quiet=True, env=env)

    said: set[str] = set()

    def warn(line: str) -> None:                                      # the board's warnings, once each, in this log
        if line not in said:
            said.add(line)
            log(line)

    global _sharing
    _sharing = True
    try:
        checkpoint_commit("share", warn=warn)
    finally:
        _sharing = False
    if git("diff", "--cached", "--quiet").returncode != 0:
        return {"status": "blocked", "detail": "staged changes were not committed (possible secrets): run check --secrets"}
    if git("rev-parse", "--verify", "--quiet", "HEAD").returncode != 0:
        return {"status": "nothing", "detail": ""}
    branch = out(["git", "symbolic-ref", "--short", "HEAD"], cwd=ROOT)
    if not branch:
        return {"status": "error", "detail": "detached HEAD: check out a branch first"}
    log(f"fetching {url}…")
    r = git("fetch", "--quiet", "origin", env=auth)
    if r.returncode:
        return _failed(r, url)
    theirs = f"origin/{branch}"
    if git("rev-parse", "--verify", "--quiet", theirs).returncode == 0:
        log(f"rebasing onto {theirs}…")
        if git(*_ident(), "rebase", "--quiet", "--autostash", theirs).returncode:
            git("rebase", "--abort")
            return {"status": "conflict", "detail": theirs}
        if board_repair(warn):                                        # a merge can leave duplicate ids or stale mirrors
            _sharing = True
            try:
                checkpoint_commit("board repaired after sync", warn=warn)
            finally:
                _sharing = False
            if git("diff", "--cached", "--quiet").returncode != 0:
                return {"status": "blocked", "detail": "the board repair was not committed (possible secrets): run check --secrets"}
        if out(["git", "rev-list", "--count", f"{theirs}..HEAD"], cwd=ROOT) == "0":
            _shared()
            return {"status": "up-to-date", "detail": branch}
    log(f"pushing {branch}…")
    r = git("push", "--quiet", "-u", "origin", branch, env=auth)
    if r.returncode:
        return _failed(r, url)
    _shared()
    return {"status": "pushed", "detail": branch}


# Rebuilt from the pages, so a clash in them is never worth a person's time: the team's copy is taken and rewritten.
DERIVED: tuple[str, ...] = ("docs/.status.json", "docs/llms.txt", "docs/llms-full.txt")


def _nul_lines(*args: str) -> list[str]:
    raw = run(["git", *args], cwd=ROOT, check=False, capture=True).stdout or ""
    return [t for t in raw.split("\0") if t]


def _in_progress() -> bool:
    """A rebase or merge left half way; the state dirs are asked of git because `.git` is a file in a worktree."""
    for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD"):
        where = out(["git", "rev-parse", "--git-path", name], cwd=ROOT)
        if where and (ROOT / where).exists():
            return True
    return False


def _dirty() -> dict[str, str]:
    """Every path the working tree has changed, exact (NUL-separated, so no quoting); both sides of a rename."""
    entries = _nul_lines("status", "--porcelain", "-z", "-uall")
    dirty: dict[str, str] = {}
    i = 0
    while i < len(entries):
        code, path = entries[i][:2], entries[i][3:]
        dirty[path] = code
        if code[0] in "RC" or code[1] in "RC":
            i += 1
            if i < len(entries):
                dirty[entries[i]] = code
        i += 1
    return dirty


def _autostashes() -> int:
    return sum("autostash" in ln for ln in out(["git", "stash", "list", "--format=%gs"], cwd=ROOT).splitlines())


def _reset_derived(path: str, code: str) -> None:
    """Back to HEAD's copy in the index and the tree, so nothing of it is left staged for the autostash to take."""
    def git(*args: str):
        return run(["git", *args], cwd=ROOT, check=False, quiet=True)

    if code == "??":
        (ROOT / path).unlink(missing_ok=True)
    elif git("cat-file", "-e", f"HEAD:{path}").returncode == 0:
        git("checkout", "HEAD", "--", path)
    else:                                                            # staged as new: HEAD has no copy to restore
        git("rm", "--cached", "-q", "--", path)
        (ROOT / path).unlink(missing_ok=True)


def _regenerate() -> None:
    current = services.current()
    current.doc_status.collect()
    current.llms.llms()


def _rebase_onto(theirs: str, ident: list[str]):
    """Rebase onto the team's branch, resolving clashes in derived files by taking the team's side. Returns the
    derived paths resolved, the paths that need a person (rebase undone then) and the failed git run when the rebase
    could not go on at all (undone too)."""
    def git(*args: str, env: dict | None = None):
        return run(["git", *args], cwd=ROOT, check=False, quiet=True, env=env)

    resolved: list[str] = []
    r = git(*ident, "rebase", "--quiet", "--autostash", theirs)
    for _ in range(200):                                             # a guard: every pass settles one local commit
        if not (r.returncode and _in_progress()):
            break
        clashing = sorted(_nul_lines("diff", "--name-only", "-z", "--diff-filter=U"))
        human = [p for p in clashing if p not in DERIVED]
        if human:
            git("rebase", "--abort")
            return resolved, human, None
        if clashing:
            git("checkout", "--ours", "--", *clashing)               # mid-rebase "ours" is the team's side
            git("add", "--", *clashing)
            resolved += clashing
        if git("diff", "--cached", "--quiet").returncode == 0:      # the local commit only held derived files
            r = git(*ident, "rebase", "--skip")
        else:
            r = git(*ident, "rebase", "--continue", env={"GIT_EDITOR": "true"})
    if r.returncode:
        if _in_progress():
            git("rebase", "--abort")
        return resolved, [], r
    return sorted(set(resolved)), [], None


def pull(log: Log = print) -> dict:
    """Bring in the team's work (fetch + rebase onto origin); never pushes and never commits, except the board's own
    repair. Local work stays put: a clash leaves HEAD and every file as they were. Returns {"status", "commits",
    "files", "regenerated", "detail"}: up-to-date · pulled · nothing · no-remote · conflict · stashed (brought in, but
    uncommitted changes that would not re-apply are kept in git's stash) · busy · error."""
    result = lambda status, detail="", **kw: {"status": status, "commits": 0, "files": [],   # noqa: E731
                                              "regenerated": [], "detail": detail, **kw}
    url = docs_remote()
    if not url:
        return result("no-remote")
    if _in_progress():
        return result("busy", "git")
    if run(["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=ROOT, check=False, quiet=True).returncode != 0:
        return result("nothing")
    branch = out(["git", "symbolic-ref", "--short", "HEAD"], cwd=ROOT)
    if not branch:
        return result("error", "detached HEAD: check out a branch first")
    from lib import creds
    log(f"fetching {url}…")
    r = run(["git", "fetch", "--quiet", "origin"], cwd=ROOT, check=False, quiet=True, env=creds.git_env(url))
    if r.returncode:
        return {**result("error"), **_failed(r, url)}
    theirs = f"origin/{branch}"
    if run(["git", "rev-parse", "--verify", "--quiet", theirs], cwd=ROOT, check=False, quiet=True).returncode != 0:
        return result("nothing")
    behind = int(out(["git", "rev-list", "--count", f"HEAD..{theirs}"], cwd=ROOT) or 0)
    if behind == 0:
        return result("up-to-date", branch)

    changed_by_team = set(_nul_lines("diff", "--name-only", "-z", "--no-renames", f"HEAD...{theirs}"))
    clash = {p: code for p, code in _dirty().items() if p in changed_by_team}
    human = sorted(p for p in clash if p not in DERIVED)
    if human:
        return result("conflict", theirs, files=human)
    regenerated = sorted(clash)
    for path, code in clash.items():
        _reset_derived(path, code)

    log(f"rebasing onto {theirs}…")
    stashes = _autostashes()
    resolved, human, failure = _rebase_onto(theirs, _ident())
    regenerated = sorted(set(regenerated) | set(resolved))
    if human or failure is not None:
        if regenerated:
            _regenerate()
        return result("conflict", theirs, files=human) if human else {**result("error"), **_failed(failure, url)}
    if _autostashes() > stashes:                                     # the local changes did not re-apply: keep them safe
        stuck = sorted(_nul_lines("diff", "--name-only", "-z", "--diff-filter=U")) or \
            sorted(_nul_lines("stash", "show", "--name-only", "-z", "stash@{0}"))
        return result("stashed", "your uncommitted changes are kept in git's stash (git stash list)", files=stuck,
                      commits=behind)

    said: set[str] = set()

    def warn(line: str) -> None:
        if line not in said:
            said.add(line)
            log(line)

    if board_repair(warn):
        global _sharing
        _sharing = True
        try:
            checkpoint_commit("board repaired after sync", warn=warn)
        finally:
            _sharing = False
    _regenerate()
    return result("pulled", branch, commits=behind, regenerated=regenerated)


def push(log: Log = print) -> dict:
    """Upload local cam-docs work; never rebases and never pulls. Returns {"status", "detail"}: pushed · nothing ·
    behind (the team moved: pull first, nothing changed) · blocked (secrets staged) · no-remote · error."""
    url = docs_remote()
    if not url:
        return {"status": "no-remote", "detail": ""}
    global _sharing
    _sharing = True
    try:
        checkpoint_commit("share", warn=log)
    finally:
        _sharing = False
    if run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False, quiet=True).returncode != 0:
        return {"status": "blocked", "detail": "staged changes were not committed (possible secrets): run check --secrets"}
    if run(["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=ROOT, check=False, quiet=True).returncode != 0:
        return {"status": "nothing", "detail": ""}
    branch = out(["git", "symbolic-ref", "--short", "HEAD"], cwd=ROOT)
    if not branch:
        return {"status": "error", "detail": "detached HEAD: check out a branch first"}
    from lib import creds
    auth = creds.git_env(url)
    log(f"fetching {url}…")
    r = run(["git", "fetch", "--quiet", "origin"], cwd=ROOT, check=False, quiet=True, env=auth)
    if r.returncode:
        return _failed(r, url)
    theirs = f"origin/{branch}"
    if run(["git", "rev-parse", "--verify", "--quiet", theirs], cwd=ROOT, check=False, quiet=True).returncode == 0:
        if int(out(["git", "rev-list", "--count", f"HEAD..{theirs}"], cwd=ROOT) or 0) > 0:
            return {"status": "behind", "detail": theirs}
        if out(["git", "rev-list", "--count", f"{theirs}..HEAD"], cwd=ROOT) == "0":
            return {"status": "nothing", "detail": branch}
    log(f"pushing {branch}…")
    r = run(["git", "push", "--quiet", "-u", "origin", branch], cwd=ROOT, check=False, quiet=True, env=auth)
    if r.returncode:
        return _failed(r, url)
    _shared()
    return {"status": "pushed", "detail": branch}


def _shared() -> None:
    """Remember when this machine last shared (the portal's Sync view shows it)."""
    SHARED.parent.mkdir(parents=True, exist_ok=True)
    save_json(SHARED, {"last": dt.datetime.now().astimezone().isoformat(timespec="seconds")})

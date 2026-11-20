# Stay in step (S1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every teammate's machine brings in the team's `cam-docs` work on its own when a project opens, rebuilds the
C4 explorer when it is stale, and offers *Traer cambios* / *Subir cambios* / *Sincronizar* in place of *Compartir*.

**Architecture:** Two new git operations in `lib/app/share.py` (`pull`, `push`; `share` stays as it is). A new use case
`lib/app/catchup.py` runs pull, then rebuilds stale local views; it is carried by `services` and run by the app on
window open (a background job), by the CLI wizard on open, and by `camaron pull` / `POST /api/sync/pull`. The app's
Team section and the portal's Sync view get the three actions through shared helpers in `ui/src/share.js`.

**Tech Stack:** Python 3 (uv inline script, pytest + xdist), git CLI, React + Vite + Vitest (desktop renderer, portal),
Electron untouched.

**Spec:** `docs/superpowers/specs/2026-11-18-join-and-stay-in-step-design.md` (§6.1 steps 1 and 3, §6.4, §6.7, §6.8,
§7 row S1). Read it before starting.

## Global Constraints

- macOS, Windows and Linux: `pathlib` only, `encoding="utf-8"` on every text read/write, processes through
  `lib/core/process.py` helpers (`run`, `out`), no `shell=True` (AGENTS.md §2.1).
- TDD: the failing test first; tests offline with `make_workspace` / `isolated_env` / a local bare repo
  (`tests/test_team_repo.py` `bare`, `publish`, `git`) (AGENTS.md §2.2).
- Nothing automatic ever pushes. Catch-up never writes `workspace.yaml`, `plan.yaml` or a `.c4` file, and never commits
  except the board repair's own checkpoint after a rebase (spec §6.1).
- `camaron share`, `share --auto on|off`, `POST /api/sync/share`, `share.json`, `shared.json`: unchanged (spec §6.8).
- New routes `/api/sync/pull` and `/api/sync/push` take the access `/api/sync/share` has (`public`, behind the router's
  `X-Camarones` / host checks); `/api/app/catch-up` is under `/api/app/`, so app token (spec §6.4, C5).
- Every user-facing string in `es` and `en`; no joke in a conflict, an error or a decision prompt; at most one joke
  per screen, only in a waiting line (AGENTS.md §3).
- The UI never uses the bare word "sync" for docs syncing; the CLI's `sync` keeps meaning the code repos.
- Tests patch the module that defines a name, never a facade; `lib/app` code is reached through `services`
  (AGENTS.md §5).
- `VERSIONS["kit"]` → `4.90.0` (or the next minor above `main` at merge time) and the README badge with it.
- Conventional commits, small; no `Co-Authored-By: Claude` or "Generated with" lines; stage only your own hunks.

## Review Focus

1. **A git operation already in progress in `cam-docs`** (a rebase or merge someone left half way): pull touches
   nothing and says so (`busy`, detail `git`). Test in Task 1.
2. **The team rewrote history** (force-push) so local commits no longer apply: `conflict`, with HEAD and every file
   exactly as before. Test in Task 1.
3. **An autopilot run holds the run lock**: catch-up does not rebase under it (`busy`, detail `run`) but still rebuilds
   the views. Test in Task 3.
4. **Offline, or the team's remote is gone, on open**: catch-up ends with an `error` result and a reason; the app window
   and the CLI menu still open; nothing raises. Tests in Task 3 and Task 5.
5. **Two catch-ups at once** (the app's on-open job and a portal or CLI pull): the second returns `busy` without waiting.
   Test in Task 3.

---

### Task 1: `share.pull` — bring in the team's work, never push, never lose local work

**Files:**
- Modify: `.camarones/lib/app/share.py`
- Test: `tests/test_share_pull.py` (new)

**Interfaces:**
- Produces:
  - `DERIVED: tuple[str, ...] = ("docs/.status.json", "docs/llms.txt", "docs/llms-full.txt")`
  - `pull(log: Log = print) -> dict` with keys `status` (`up-to-date` · `pulled` · `nothing` · `no-remote` ·
    `conflict` · `busy` · `error`), `commits: int` (team commits brought in), `files: list[str]` (conflicting paths,
    sorted), `regenerated: list[str]` (derived files regenerated), `detail: str`, and on `error` also `reason`, `host`.
  - `_failed(r: subprocess.CompletedProcess, url: str) -> dict`: the `{"status": "error", "reason", "host", "detail"}`
    dict `share` builds today in its inner `failed`, moved out so `share`, `pull` and `push` word failures alike.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_share_pull.py
from test_team_repo import bare, git, publish

def mate_commits(kit, remote, tmp_path, path="docs/theirs.md", text="# Theirs\n"):
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    f = mate / path; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text, encoding="utf-8")
    git(mate, "add", "-A"); git(mate, "commit", "-q", "-m", "theirs"); git(mate, "push", "-q", "origin", "main")
    return mate

def test_up_to_date(kit, tmp_path):
    publish(kit, bare(tmp_path))
    assert kit.services.share.pull(log=lambda _: None)["status"] == "up-to-date"

def test_brings_in_the_teams_commits_and_never_pushes(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    mate_commits(kit, remote, tmp_path)
    before = git(remote, "rev-parse", "main")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "pulled" and r["commits"] == 1
    assert (kit.root / "docs" / "theirs.md").exists() and (kit.root / "docs" / "mine.md").exists()
    assert git(remote, "rev-parse", "main") == before                       # nothing pushed
    assert git(kit.root, "rev-list", "--count", "origin/main..HEAD") == "1"   # mine rebased on top

def test_uncommitted_work_stays_where_it_was(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote); mate_commits(kit, remote, tmp_path)
    (kit.root / "docs" / "draft.md").write_text("# Draft\n", encoding="utf-8")
    assert kit.services.share.pull(log=lambda _: None)["status"] == "pulled"
    assert (kit.root / "docs" / "draft.md").read_text(encoding="utf-8") == "# Draft\n"
    assert git(kit.root, "stash", "list") == ""

def test_uncommitted_change_to_a_file_the_team_changed_is_a_conflict_and_changes_nothing(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/shared.md", "# Team\n")
    (kit.root / "docs" / "shared.md").write_text("# Mine\n", encoding="utf-8")
    head = git(kit.root, "rev-parse", "HEAD")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "conflict" and r["files"] == ["docs/shared.md"]
    assert git(kit.root, "rev-parse", "HEAD") == head
    assert (kit.root / "docs" / "shared.md").read_text(encoding="utf-8") == "# Mine\n"

def test_a_clash_between_commits_is_undone(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/shared.md", "# Team\n")
    (kit.root / "docs" / "shared.md").write_text("# Mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    head = git(kit.root, "rev-parse", "HEAD")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "conflict" and "docs/shared.md" in r["files"]
    assert git(kit.root, "rev-parse", "HEAD") == head and not (kit.root / ".git" / "rebase-merge").exists()

def test_a_clash_only_in_derived_files_takes_the_teams_and_regenerates(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/llms.txt", "team\n")
    (kit.root / "docs" / "llms.txt").write_text("mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "pulled" and "docs/llms.txt" in r["regenerated"]
    assert "<<<<<<<" not in (kit.root / "docs" / "llms.txt").read_text(encoding="utf-8")

def test_history_rewritten_by_the_team_is_a_conflict_and_changes_nothing(kit, tmp_path):   # Review Focus 2
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "a.md").write_text("# A\n", encoding="utf-8"); kit.services.share.checkpoint_commit("a")
    git(kit.root, "push", "-q", "origin", "main")
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    git(mate, "reset", "-q", "--hard", "HEAD~1")
    (mate / "docs" / "a.md").write_text("# Rewritten\n", encoding="utf-8")
    git(mate, "add", "-A"); git(mate, "commit", "-q", "-m", "rewrite"); git(mate, "push", "-q", "-f", "origin", "main")
    (kit.root / "docs" / "a.md").write_text("# A2\n", encoding="utf-8"); kit.services.share.checkpoint_commit("a2")
    head = git(kit.root, "rev-parse", "HEAD")
    assert kit.services.share.pull(log=lambda _: None)["status"] == "conflict"
    assert git(kit.root, "rev-parse", "HEAD") == head

def test_a_rebase_left_half_way_is_left_alone(kit, tmp_path):                                # Review Focus 1
    publish(kit, bare(tmp_path))
    (kit.root / ".git" / "rebase-merge").mkdir()
    r = kit.services.share.pull(log=lambda _: None)
    assert (r["status"], r["detail"]) == ("busy", "git")

def test_no_remote_and_no_branch_on_the_remote(kit, tmp_path):
    kit.services.templates.init_templates("demo", log=lambda _: None)
    assert kit.services.share.pull(log=lambda _: None)["status"] == "no-remote"
    kit.services.share.set_remote(str(bare(tmp_path))); kit.services.share.checkpoint_commit("first")
    assert kit.services.share.pull(log=lambda _: None)["status"] == "nothing"

def test_an_unreachable_remote_says_why(kit, tmp_path):
    kit.services.templates.init_templates("demo", log=lambda _: None)
    kit.services.share.set_remote(str(tmp_path / "missing.git")); kit.services.share.checkpoint_commit("first")
    r = kit.services.share.pull(log=lambda _: None)
    assert r["status"] == "error" and r["reason"] == "not-found" and r["detail"].startswith("fatal: ")
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_share_pull.py -v`
Expected: FAIL, `AttributeError: module 'lib.app.share' has no attribute 'pull'`.

- [ ] **Step 3: Implement `pull(log: Log = print) -> dict` and `_failed(r, url) -> dict` in `share.py`**

Order inside `pull`, each a return point:
1. no `origin` → `no-remote`; `.git/rebase-merge`, `.git/rebase-apply` or `.git/MERGE_HEAD` present → `busy`/`git`;
   detached HEAD → `error` with detail as `share` words it; no `HEAD` → `nothing`.
2. `git fetch --quiet origin` with `creds.git_env(url)`; failure → `_failed(r, url)`.
3. `origin/<branch>` missing → `nothing`; `rev-list --count HEAD..origin/<branch>` is 0 → `up-to-date`.
4. Dirty paths (`git status --porcelain -uall`) ∩ paths the team changed (`git diff --name-only HEAD...origin/<branch>`):
   derived ones are reset (`git checkout -- <path>`, remembered for regeneration); any other → `conflict` with them,
   before touching anything.
5. `git rebase --quiet --autostash origin/<branch>` (identity from `_ident()`). While it stops: conflicted paths
   (`git diff --name-only --diff-filter=U`) all in `DERIVED` → `git checkout --ours -- <paths>` (during a rebase
   "ours" is the team's side), `git add`, `git rebase --continue` with `GIT_EDITOR=true` in the env; any other path →
   collect, `git rebase --abort`, return `conflict` with the sorted paths. A local commit left empty by taking the
   team's derived files (git says there is nothing to commit) is dropped with `git rebase --skip`. In step 4, a dirty
   derived file git does not track yet is removed rather than checked out.
6. `board_repair(warn)` and, when it changed something, `checkpoint_commit("board repaired after sync")` under the
   `_sharing` flag, exactly as `share` does.
7. Regenerate what was reset or resolved: `services.current().doc_status.collect()` rewrites `.status.json`,
   `services.current().llms.llms()` rewrites both `llms` files; return `pulled` with `commits` from step 3.

`share`'s inner `failed` becomes a call to `_failed(r, url)`; `share`'s behaviour does not change.

- [ ] **Step 4: Run the tests and the existing share tests**

Run: `uv run pytest tests/test_share_pull.py tests/test_sync.py tests/test_team_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/app/share.py tests/test_share_pull.py
git commit -m "feat(share): pull brings in the team's cam-docs work without pushing"
```

### Task 2: `share.push` — upload, refuse when the team moved

**Files:**
- Modify: `.camarones/lib/app/share.py`
- Test: `tests/test_share_pull.py`

**Interfaces:**
- Consumes: `_failed` (Task 1).
- Produces: `push(log: Log = print) -> dict` with `status` `pushed` · `nothing` · `behind` · `blocked` · `no-remote` ·
  `error`, `detail: str`, and `reason`, `host` on `error`. `pushed` records the share time (`_shared()`).

- [ ] **Step 1: Write the failing tests**

```python
def test_push_uploads_local_work(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    assert kit.services.share.push(log=lambda _: None)["status"] == "pushed"
    assert "docs/mine.md" in git(remote, "ls-tree", "-r", "--name-only", "main").splitlines()
    assert kit.services.share.sync_status()["last_share"]

def test_push_with_nothing_new(kit, tmp_path):
    publish(kit, bare(tmp_path))
    assert kit.services.share.push(log=lambda _: None)["status"] == "nothing"

def test_push_refuses_when_the_team_moved_and_rebases_nothing(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote); mate_commits(kit, remote, tmp_path)
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    head_remote = git(remote, "rev-parse", "main")
    assert kit.services.share.push(log=lambda _: None)["status"] == "behind"
    assert git(remote, "rev-parse", "main") == head_remote
    assert not (kit.root / "docs" / "theirs.md").exists()

def test_push_blocked_by_staged_secrets(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path))
    import lib.quality
    monkeypatch.setattr(lib.quality, "staged_secrets", lambda: ["docs/mine.md:1 generic-api-key"])
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    assert kit.services.share.push(log=lambda _: None)["status"] == "blocked"
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_share_pull.py -k push -v`
Expected: FAIL, no attribute `push`.

- [ ] **Step 3: Implement `push(log: Log = print) -> dict` in `share.py`**

`checkpoint_commit("share")` under the `_sharing` flag (no auto-share recursion); still staged → `blocked`; fetch
(failure → `_failed`); `origin/<branch>` exists and `HEAD..origin/<branch>` > 0 → `behind`; `origin/<branch>..HEAD`
is 0 → `nothing`; `git push --quiet -u origin <branch>` with creds; failure → `_failed`; success → `_shared()`,
`pushed` with the branch as detail.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_share_pull.py tests/test_sync.py tests/test_team_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/app/share.py tests/test_share_pull.py
git commit -m "feat(share): push uploads cam-docs work and refuses when the team moved"
```

### Task 3: The catch-up use case

**Files:**
- Create: `.camarones/lib/app/catchup.py`
- Modify: `.camarones/lib/app/services.py` (field `catchup: ModuleType`), `.camarones/lib/bootstrap.py` (provider
  `_catchup`, key `"catchup"`)
- Test: `tests/test_catchup.py` (new)

**Interfaces:**
- Consumes: `share.pull` (Task 1); `viewers.viewers()`, `viewers.build_c4(log)`, `viewers.graph(rebuild, log)`;
  `services.code.graph_repo(name)`; `components.components()`; `lib.harness.scheduler.busy()`; `lib.core.locks.FileLock`,
  `LockBusy`.
- Produces:
  - `LAST: Path = CACHE / "catch-up.json"`; `LOCK: Path = CTX.state_root / ".camarones" / ".cache" / "locks" / "catch-up.lock"`
  - `run(log: Log = print) -> dict`: `{"status": "done" | "busy" | "skipped", "pull": <pull result>, "views": {"c4":
    "built" | "fresh" | "failed" | "skipped", "graphs": list[str]}, "at": str}` (ISO time); `done` results are saved to
    `LAST`. `skipped` in a unit's worktree (`CTX.root != CTX.state_root`). `busy` when `LOCK` is held (`wait=0`).
    Run lock held → `pull` is `{"status": "busy", "detail": "run", ...}` and the views still rebuild.
  - `rebuild_c4(log: Log = print) -> str`: `skipped` when there is no model, or LikeC4 is not a chosen component or not
    on PATH (`which("likec4")`); `fresh` when the build exists and is not stale; else `build_c4` → `built` / `failed`.
  - `stale_graphs() -> list[str]`: repos whose graph is older than their HEAD, `[]` unless `graphify` is chosen.
  - `rebuild_graphs(repos: list[str], log: Log = print) -> bool`: `graph_repo` for each, then `graph(rebuild=False)`.
  - `last() -> dict | None`: the saved result.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_catchup.py
import json, threading
from test_team_repo import bare, git, publish
from test_share_pull import mate_commits

def fake_c4(kit, monkeypatch, state):
    # the kit's modules are imported afresh for each test: patch the ones this test's services carry
    built = []
    monkeypatch.setattr(kit.services.viewers, "viewers", lambda: {"c4": state, "graphs": {}, "graphify": False, "likec4": True})
    monkeypatch.setattr(kit.services.viewers, "build_c4", lambda dest=None, log=print: built.append(1) or True)
    monkeypatch.setattr(kit.services.catchup, "which", lambda name: "/bin/" + name)
    return built

def test_a_teammates_c4_edit_rebuilds_the_explorer(kit, tmp_path, monkeypatch):
    remote = bare(tmp_path); publish(kit, remote)
    mate_commits(kit, remote, tmp_path, "docs/architecture/model.c4", "model {\n}\n")
    built = fake_c4(kit, monkeypatch, {"exists": True, "stale": True, "model": True})
    r = kit.services.catchup.run(log=lambda _: None)
    assert r["status"] == "done" and r["pull"]["status"] == "pulled" and r["views"]["c4"] == "built" and built

def test_a_fresh_explorer_is_left_alone(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path))
    built = fake_c4(kit, monkeypatch, {"exists": True, "stale": False, "model": True})
    assert kit.services.catchup.run(log=lambda _: None)["views"]["c4"] == "fresh" and not built

def test_it_never_writes_team_decisions_and_never_pushes(kit, tmp_path, monkeypatch):
    remote = bare(tmp_path); publish(kit, remote); mate_commits(kit, remote, tmp_path)
    fake_c4(kit, monkeypatch, {"exists": False, "stale": False, "model": False})
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8"); kit.services.share.checkpoint_commit("mine")
    watched = [kit.root / ".camarones" / "workspace.yaml", kit.plan.PLAN]
    before = [p.read_bytes() if p.exists() else None for p in watched]
    head_remote = git(remote, "rev-parse", "main")
    kit.services.catchup.run(log=lambda _: None)
    assert [p.read_bytes() if p.exists() else None for p in watched] == before
    assert git(remote, "rev-parse", "main") == head_remote

def test_a_run_in_progress_skips_the_pull_not_the_views(kit, tmp_path, monkeypatch):     # Review Focus 3
    publish(kit, bare(tmp_path))
    import lib.harness.scheduler as sch
    monkeypatch.setattr(sch, "busy", lambda: {"what": "autopilot"})
    fake_c4(kit, monkeypatch, {"exists": True, "stale": True, "model": True})
    r = kit.services.catchup.run(log=lambda _: None)
    assert (r["pull"]["status"], r["pull"]["detail"]) == ("busy", "run") and r["views"]["c4"] == "built"

def test_offline_ends_with_a_reason_and_raises_nothing(kit, tmp_path, monkeypatch):     # Review Focus 4
    kit.services.templates.init_templates("demo", log=lambda _: None)
    kit.services.share.set_remote(str(tmp_path / "gone.git")); kit.services.share.checkpoint_commit("first")
    fake_c4(kit, monkeypatch, {"exists": False, "stale": False, "model": False})
    r = kit.services.catchup.run(log=lambda _: None)
    assert r["status"] == "done" and r["pull"]["status"] == "error" and r["pull"]["reason"] == "not-found"

def test_a_second_catch_up_does_not_wait(kit, tmp_path):                                    # Review Focus 5
    publish(kit, bare(tmp_path))
    from lib.core.locks import FileLock
    held, done = threading.Event(), threading.Event()
    def hold():                                   # FileLock is re-entrant per thread: hold it from another one
        with FileLock(kit.services.catchup.LOCK, wait=0):
            held.set(); done.wait(30)
    t = threading.Thread(target=hold); t.start(); held.wait(30)
    try:
        assert kit.services.catchup.run(log=lambda _: None)["status"] == "busy"
    finally:
        done.set(); t.join()

def test_the_last_result_is_kept(kit, tmp_path, monkeypatch):
    publish(kit, bare(tmp_path)); fake_c4(kit, monkeypatch, {"exists": False, "stale": False, "model": False})
    kit.services.catchup.run(log=lambda _: None)
    assert kit.services.catchup.last()["pull"]["status"] == "up-to-date"
    assert json.loads(kit.services.catchup.LAST.read_text(encoding="utf-8"))["at"]
```

Plus one test for `stale_graphs` (graphify chosen, `viewers()` reporting one stale repo → `["api"]`; graphify not
chosen → `[]`) and one for `rebuild_c4` returning `skipped` when `likec4` is not in `components()`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_catchup.py -v`
Expected: FAIL, `AttributeError: no service 'catchup'`.

- [ ] **Step 3: Implement `lib/app/catchup.py` and wire it into `services` and `bootstrap`**

Module docstring states it never pushes and never writes team decisions. Imports `which` from `lib.common` (so tests
patch `lib.app.catchup.which`) and the scheduler as a module, calling `scheduler.busy()` at run time (so the Review
Focus 3 test's patch applies); reaches `share`, `viewers`, `components`, `code` through `services.current()`.

- [ ] **Step 4: Run the tests plus the architecture guards**

Run: `uv run pytest tests/test_catchup.py tests/test_architecture.py tests/test_env_split.py tests/test_docs_split.py -v`
Expected: PASS, with `tests/architecture/allowlist.yaml` unchanged.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/app/catchup.py .camarones/lib/app/services.py .camarones/lib/bootstrap.py tests/test_catchup.py
git commit -m "feat(catchup): one routine brings in the team's work and rebuilds stale local views"
```

### Task 4: HTTP routes

**Files:**
- Modify: `.camarones/lib/interfaces/http/routes/team.py`
- Modify: `tests/snapshots/routes.json` (by hand: three entries)
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: `share.push`, `share.sync_status`, `catchup.run`, `catchup.stale_graphs`, `catchup.rebuild_graphs`,
  `catchup.last`; `lib.interfaces.http.jobs.start_job(kind, label, fn)`.
- Produces:
  - `POST /api/sync/pull` (public) → `{"result": <catchup.run()>, "sync": <sync_status()>}`; when
    `result["views"]["graphs"]` is non-empty it also starts `start_job("graph", "Code graphs", …rebuild_graphs…)`.
  - `POST /api/sync/push` (public) → `{"result": <share.push()>, "sync": <sync_status()>}`.
  - `POST /api/app/catch-up` (`Access.APP`) → the job from `start_job("catch-up", "Catch up with the team", fn)`; `fn`
    runs `catchup.run`, starts the graph job the same way, and returns `{"rc": 0, "result": <run result>}`.
  - `GET /api/sync` gains `"catch_up": catchup.last()`.
  - `POST /api/app/terminal` (`Access.APP`) → `{"opened": bool}`: `services.launcher.open_new_terminal([shell], ROOT)`
    opens a terminal in `cam-docs`, the conflict's "Open a terminal here" (spec §6.7). `shell`: `COMSPEC` or
    `cmd.exe` when `IS_WIN`, else `SHELL` or `/bin/sh`.

- [ ] **Step 1: Write the failing tests** (in `tests/test_sync.py`, with its `portal` fixture and `call` helper; the
  app-token routes with `app_server`, `TOKEN` and `call` imported from `tests/test_app_api.py`)

```python
def test_the_portal_brings_in_and_uploads(kit, tmp_path, portal):
    remote = bare(tmp_path); publish(kit, remote)
    assert call(portal + "/api/sync/pull", {}, header=False)[0] == 403
    code, r = call(portal + "/api/sync/pull", {})
    assert code == 200 and r["result"]["pull"]["status"] == "up-to-date" and "catch_up" in r["sync"]
    (kit.root / "docs" / "edit.md").write_text("# Edit\n", encoding="utf-8")
    code, r = call(portal + "/api/sync/push", {})
    assert code == 200 and r["result"]["status"] == "pushed" and r["sync"]["pending"] == []
```

```python
from pathlib import Path
from test_app_api import TOKEN, app_server, call as app_call   # noqa: F401 — app_server is a fixture

def test_the_app_opens_a_terminal_in_cam_docs(kit, app_server, monkeypatch):
    opened = []
    import lib.adapters.system.os_open as os_open
    monkeypatch.setattr(os_open, "open_new_terminal", lambda cmd, cwd: opened.append((cmd, cwd)) or True)
    code, r = app_call(app_server + "/api/app/terminal", {}, token=TOKEN)
    assert code == 200 and r == {"opened": True} and Path(opened[0][1]).resolve() == kit.root.resolve()

def test_the_app_starts_a_catch_up_job(kit, tmp_path, app_server):
    publish(kit, bare(tmp_path))
    code, job = app_call(app_server + "/api/app/catch-up", {}, token=TOKEN)
    assert code == 200 and job["kind"] == "catch-up"
```

And add to `tests/snapshots/routes.json`, sorted as the file is:
`{"method": "POST", "path": "/api/sync/pull", "access": "public"}`,
`{"method": "POST", "path": "/api/sync/push", "access": "public"}`,
`{"method": "POST", "path": "/api/app/catch-up", "access": "app"}`,
`{"method": "POST", "path": "/api/app/terminal", "access": "app"}`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_sync.py tests/test_routes_snapshot.py -v`
Expected: FAIL (404 on the new routes; the snapshot names routes the server lacks).

- [ ] **Step 3: Add the routes in `routes/team.py`**

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_sync.py tests/test_routes_snapshot.py tests/test_http_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/interfaces/http/routes/team.py tests/test_sync.py tests/snapshots/routes.json
git commit -m "feat(http): pull, push, the app's catch-up job and a terminal in cam-docs"
```

### Task 5: CLI `pull` / `push` and the terminal wizard

**Files:**
- Modify: `.camarones/lib/interfaces/cli/commands/team.py`
- Modify: `.camarones/lib/wizard.py` (`_run`, `do_share`, the `T` table in es and en)
- Modify: `tests/snapshots/cli.json` (regenerated)
- Test: `tests/test_sync.py` (CLI), `tests/test_wizard.py`

**Interfaces:**
- Consumes: `catchup.run`, `catchup.stale_graphs`, `catchup.rebuild_graphs`, `share.push`, `share.share`.
- Produces:
  - `@command("pull", "both", "team", es="Traer los cambios del equipo", en="Bring in the team's changes")`: prints
    the pull's `<status>[ (<reason>)][: <detail>]` like `share` (`busy` alone when the run itself was `busy`), then
    rebuilds stale graphs inline; exit 0 for `up-to-date`, `pulled`, `nothing`, else 1.
  - `@command("push", "both", "team", es="Subir tus cambios al equipo", en="Upload your changes to the team")`: same
    print; exit 0 for `pushed`, `nothing`, else 1.
  - `share`'s labels become es "Sincronizar con el equipo (traer y subir)", en "Sync with the team (bring in and
    upload)"; flags unchanged.
  - Wizard: `catch_up(self) -> None` runs `catchup.run` under `self.busy` after the first-run check when the mode is
    `done`, and says one line; `do_share` asks first which of the three (`sh_pick` with choices `sh_do_pull`,
    `sh_do_push`, `sh_do_share`, back), then runs it with the error wording it already has.
  - New `T` keys, es and en: `cu_pulled` ("✔ Traje {n} cambio(s) del equipo." / "✔ Brought in {n} change(s) from the
    team."), `cu_up_to_date`, `cu_conflict` ("No he podido traer los cambios del equipo: chocan con los tuyos en
    {files}. No he tocado nada." / "Couldn't bring in the team's changes: they clash with yours in {files}. Nothing was
    changed."), `cu_busy`, `cu_offline` ("No llego al repo del equipo: trabajas con lo último que trajiste." / "Can't
    reach the team's repo: you're working with the latest you brought in."), `sh_pick`, `sh_do_pull`, `sh_do_push`,
    `sh_do_share`, `sh_behind` ("El equipo tiene cambios nuevos: tráelos primero o sincroniza." / "The team has new
    changes: bring them in first, or sync."); `m_share` becomes "🤝 Equipo: traer, subir o sincronizar" / "🤝 Team:
    bring in, upload or sync".

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sync.py
def test_pull_and_push_from_the_cli(kit, tmp_path):
    remote = bare(tmp_path); publish(kit, remote)
    r = cli(kit, "pull"); assert r.returncode == 0 and r.stdout.startswith("up-to-date")
    (kit.root / "docs" / "cli.md").write_text("# CLI\n", encoding="utf-8")
    r = cli(kit, "push"); assert r.returncode == 0 and r.stdout.startswith("pushed")

def test_pull_from_the_cli_offline_exits_1(kit, tmp_path):
    kit.services.templates.init_templates("demo", log=lambda _: None)
    kit.services.share.set_remote(str(tmp_path / "gone.git")); kit.services.share.checkpoint_commit("first")
    r = cli(kit, "pull"); assert r.returncode == 1 and r.stdout.startswith("error (not-found)")
```

In `tests/test_wizard.py`: the wizard's `catch_up` with `catchup.run` patched to return each pull status (`pulled`,
`conflict`, `error`) says the matching `cu_*` line and returns without raising (Review Focus 4: the menu still
opens). `tests/test_wizard_keys.py` already checks es/en parity of the new keys.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_sync.py -k cli tests/test_wizard.py -k catch_up -v`
Expected: FAIL, `invalid choice: 'pull'`.

- [ ] **Step 3: Add the commands and the wizard changes; regenerate the CLI snapshot and the catalog**

Run: `CAMARONES_UPDATE_SNAPSHOTS=1 uv run pytest tests/test_cli_snapshot.py` and review the diff: only `pull`,
`push` added and `share`'s labels changed.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_sync.py tests/test_wizard.py tests/test_wizard_keys.py tests/test_cli_snapshot.py tests/test_catalog.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/interfaces/cli/commands/team.py .camarones/lib/wizard.py tests/snapshots/cli.json tests/test_sync.py tests/test_wizard.py
git commit -m "feat(cli): camaron pull and push; the wizard catches up on open and asks which of the three"
```

### Task 6: Shared helpers and the portal's Sync view

**Files:**
- Modify: `.camarones/ui/src/share.js`, `.camarones/ui/src/share.test.js`, `.camarones/ui/src/index.js` (export the new
  helpers next to `fetchSay, shareOk, shareSay`)
- Modify: `.camarones/portal/app/src/Sync.jsx`, `.camarones/portal/app/src/i18n.js`
- Rebuild: `.camarones/portal/app-build/` (committed)

**Interfaces:**
- Produces (in `ui/src/share.js`, exported):
  - `syncPrimary(s) -> 'pull' | 'push' | 'share' | null`: `behind > 0 && (ahead > 0 || pending.length > 0)` →
    `share`; `behind > 0` → `pull`; `ahead > 0 || pending.length > 0` → `push`; else `null`. `null`/missing counts
    read as 0.
  - `pullSay(r, remote) -> {key, vars, detail, token}`: error with a known reason → the reason sentence (as
    `shareSay`); else key `sy.pull.<status>` with vars `{n: r.commits, files: r.files.join(', '), detail}`.
  - `pushSay(r, remote)`: same shape, keys `sy.push.<status>`.
  - `pullOk(r)`: status in `up-to-date`, `pulled`, `nothing`; `pushOk(r)`: `pushed`, `nothing`.
  - `catchUpSay(c) -> {key, vars, tone} | null`: `null` when `c` is missing, `busy`, or the pull was `up-to-date` /
    `nothing` / `no-remote`; `pulled` → `{key: 'cu.pulled', vars: {n}, tone: 'info'}`; `conflict` →
    `{key: 'cu.conflict', vars: {files}, tone: 'warn'}`; `error` → `{key: 'cu.offline', tone: 'warn'}`.
- New strings in the portal's `i18n.js` (es and en): `sy.pull.*`, `sy.push.*` for every status above (conflict and
  `behind` copy as in Task 5's `cu_conflict` and `sh_behind`), `syPull` "Traer cambios" / "Bring in changes", `syPush`
  "Subir cambios" / "Upload changes", `sySync` "Sincronizar" / "Sync with the team" (never a bare "Sync"),
  `syAutoOn`/`syAutoOff` reworded to "Subir al
  guardar: sí/no" / "Upload on save: on/off". `syShare` goes.

- [ ] **Step 1: Write the failing tests** (`ui/src/share.test.js`)

```js
test('the useful action is the primary one', () => {
  expect(syncPrimary({ ahead: 0, behind: 3, pending: [] })).toBe('pull')
  expect(syncPrimary({ ahead: 1, behind: 0, pending: [] })).toBe('push')
  expect(syncPrimary({ ahead: 0, behind: 0, pending: ['docs/a.md'] })).toBe('push')
  expect(syncPrimary({ ahead: 1, behind: 2, pending: [] })).toBe('share')
  expect(syncPrimary({ ahead: null, behind: null, pending: [] })).toBe(null)
})

test('a pull names how many changes came in, or the files that clash', () => {
  expect(pullSay({ status: 'pulled', commits: 2, files: [] }).key).toBe('sy.pull.pulled')
  expect(pullSay({ status: 'pulled', commits: 2, files: [] }).vars.n).toBe(2)
  expect(pullSay({ status: 'conflict', commits: 0, files: ['docs/a.md', 'docs/b.md'] }).vars.files).toBe('docs/a.md, docs/b.md')
  expect(pullSay({ status: 'error', reason: 'network', host: 'git.acme', detail: 'fatal: x' }, 'https://git.acme/d.git').key).toBe('sy.err.network')
})

test('the summary speaks only when the catch-up brought something or failed', () => {
  expect(catchUpSay(null)).toBe(null)
  expect(catchUpSay({ status: 'done', pull: { status: 'up-to-date' } })).toBe(null)
  expect(catchUpSay({ status: 'done', pull: { status: 'pulled', commits: 4 } })).toEqual({ key: 'cu.pulled', vars: { n: 4 }, tone: 'info' })
  expect(catchUpSay({ status: 'done', pull: { status: 'conflict', files: ['docs/a.md'] } }).tone).toBe('warn')
  expect(catchUpSay({ status: 'done', pull: { status: 'error', reason: 'not-found' } }).key).toBe('cu.offline')
})
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd .camarones/portal/app && npm ci && npx vitest run ../../ui/src/share.test.js` (`npm ci` once: the lockfile
pins every package)
Expected: FAIL, `syncPrimary is not a function`.

- [ ] **Step 3: Implement the helpers; redo `Sync.jsx`'s actions**

`Sync.jsx`: the three buttons (`sync/pull`, `sync/push`, `sync/share`), the one `syncPrimary` names styled as the main
one, the check-for-news button kept; the result line uses `pullSay` / `pushSay` / `shareSay` by action. A pull's
answer is `{result: <catch-up run>, sync}`: `pullSay` takes `result.pull`.

- [ ] **Step 4: Run the portal's tests and rebuild it**

Run: `cd .camarones/portal/app && npm test && npm run build`
Expected: tests PASS; `app-build/` updated.

- [ ] **Step 5: Commit**

```bash
git add .camarones/ui/src/share.js .camarones/ui/src/share.test.js .camarones/portal/app/src/Sync.jsx .camarones/portal/app/src/i18n.js .camarones/portal/app-build
git commit -m "feat(portal): Sync offers bring in, upload and sync in place of Compartir"
```

### Task 7: The desktop app — Team, Summary, catch-up on open

**Files:**
- Modify: `.camarones/desktop/renderer/src/sections/Team.jsx`, `.camarones/desktop/renderer/src/sections/Summary.jsx`,
  `.camarones/desktop/renderer/src/App.jsx`, `.camarones/desktop/renderer/src/nav.js`,
  `.camarones/desktop/renderer/src/i18n.js`
- Test: `.camarones/desktop/renderer/src/nav.test.js`, `Team.test.jsx`, `Summary.test.jsx`
- Rebuild: `.camarones/desktop/renderer-build/` (committed)

**Interfaces:**
- Consumes: `syncPrimary`, `pullSay`, `pushSay`, `shareSay`, `pullOk`, `pushOk`, `catchUpSay` from `@camaron/ui`
  (Task 6); `POST app/catch-up`, `POST sync/pull`, `POST sync/push`, `GET sync` (Task 4).
- Produces:
  - `nav.js`: `catchUpOnOpen(state, hash) -> boolean`: false while `firstRunRoute(state, hash)` sends the window to the
    wizard or the first run is pending (`firstRunPending(state)`), true otherwise.
  - `App.jsx`: after `open()` sets the index, when `catchUpOnOpen` is true, `srv.post('app/catch-up', {})` once per
    window, then `jobs.refresh()`; a failure is ignored (the Summary shows the last result).
  - Team › the team's repo: a status line `tm.line` ("{behind} por traer · {ahead} por subir · última vez {when}" /
    "{behind} to bring in · {ahead} to upload · last time {when}"), the three buttons `tm.pull`, `tm.push`, `tm.sync`
    with `syncPrimary`'s as `variant="primary"` (labels as Task 6: `tm.sync` en "Sync with the team"), *Comprobar*
    kept, the toggle `tm.auto` reworded "Subir al guardar" / "Upload on save". `tm.share` goes.
    `data-tour="team-repo"` stays on the card.
  - Summary: reads `GET sync` alongside `app/summary`; `catchUpSay(sync.catch_up)` → an `Aviso tone="warn"` for
    conflict/offline with a link to `#/team` and, for a conflict, `tm.terminal` "Abrir una terminal aquí" / "Open a
    terminal here" (`POST app/terminal`); a `role="status"` small line for `pulled`; reloads when a running job ends
    (as it already does for the summary). The same conflict button shows under Team's result.
  - New `cu.*` and `sy.pull.*` / `sy.push.*` strings in the renderer's `i18n.js`, es and en, the same copy as Task 6.

- [ ] **Step 1: Write the failing tests**

`nav.test.js`: `catchUpOnOpen({ mode: 'done', done: true }, '#/summary')` is `true`; with a pending first run
(`{ mode: 'new', done: false, step: 'repos' }`) it is `false`. `Team.test.jsx`: with `sync` returning
`{ remote: 'x', ahead: 0, behind: 2, pending: [] }`, the primary button reads `tm.pull`'s text and clicking it posts
`sync/pull`. `Summary.test.jsx`: a `catch_up` with a `conflict` pull renders the warning naming the files and the
terminal button, which posts `app/terminal`; an `up-to-date` one renders nothing extra.

- [ ] **Step 2: Run them to see them fail**

Run: `cd .camarones/desktop/renderer && npm ci && npx vitest run src/nav.test.js src/Team.test.jsx src/Summary.test.jsx`
(`npm ci` once). A pull's answer is `{result: <catch-up run>, sync}`: `pullSay` takes `result.pull`.
Expected: FAIL.

- [ ] **Step 3: Implement the changes**

- [ ] **Step 4: Run the renderer's tests and rebuild it**

Run: `cd .camarones/desktop/renderer && npm test && npm run build`
Expected: PASS; `renderer-build/` updated.

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src .camarones/desktop/renderer-build
git commit -m "feat(app): the window catches up on open; Team offers bring in, upload and sync"
```

### Task 8: Docs and version

**Files:**
- Modify: `README.md`; `.camarones/templates/docs/guides/{using,app,portal}.md` and
  `.camarones/templates/docs/i18n/es/guides/{using,app,portal}.md`; `.camarones/lib/tutorial.py` and the regenerated
  `.camarones/TUTORIAL.md`; `.camarones/templates/docs/guides/tutorial.md` and its es twin; `.camarones/lib/common.py`
  (`VERSIONS["kit"]`)
- Test: `tests/test_guide.py`, `tests/test_wizard.py` (TUTORIAL.md matches)

- [ ] **Step 1: Find every place that names *Compartir* / share**

Run: `grep -rn -i "compartir\|share" README.md .camarones/templates/docs/guides .camarones/templates/docs/i18n/es/guides .camarones/lib/tutorial.py`

- [ ] **Step 2: Rewrite them**

What each says: opening a project brings in the team's work by itself and never uploads; *Traer cambios*, *Subir
cambios*, *Sincronizar* (`camaron pull`, `camaron push`, `camaron share`); a clash changes nothing and says which files;
the C4 explorer rebuilds itself after a bring-in; *Subir al guardar* is per machine. The tutorial templates note that
existing projects keep their copy. Bump `VERSIONS["kit"]` and the README badge.

- [ ] **Step 3: Regenerate the tutorial**

Run: `cd .camarones && uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`

- [ ] **Step 4: Run the doc tests**

Run: `uv run pytest tests/test_guide.py tests/test_wizard.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md .camarones/templates/docs .camarones/lib/tutorial.py .camarones/TUTORIAL.md .camarones/lib/common.py
git commit -m "docs: bring in, upload and sync; catch-up on open (kit 4.90.0)

Existing projects keep their copy of the tutorial guide; new ones get the new one."
```

### Task 9: Whole suite and the sandbox, two teammates

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest -n auto`
Expected: green; report the summary line, or what failed.

- [ ] **Step 2: Two teammates on the sandbox**

Run, from the repo root, with a scratch folder `$S`:

```bash
git init -q --bare "$S/team-docs.git"
uv run scripts/sandbox.py cli remote "$S/team-docs.git"
uv run scripts/sandbox.py cli share
uv run --script .camarones/camarones.py join "$S/team-docs.git" "$S/mate" --no-open
```

Then in the sandbox's `cam-docs`, add an element to `docs/architecture/model.c4` and `uv run scripts/sandbox.py cli
push`; in the mate's copy run `CAMARONES_ROOT="$S/mate/cam-docs" uv run --script .camarones/camarones.py pull`.
Expected: `pulled`, and (LikeC4 installed) the mate's `.camarones/.cache/viewers/architecture/index.html` newer than
the edit. Then `uv run scripts/sandbox.py reset`.

- [ ] **Step 3: The app opened from this checkout** (`uv run --script .camarones/camarones.py app`)

Open the sandbox project after the mate pushed something: the Summary shows the catch-up line; Team shows the status
line and the three buttons. If the global app is running, quit it first (handoff 2026-11-05).

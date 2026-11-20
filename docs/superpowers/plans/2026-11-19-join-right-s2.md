# Join right (S2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person with the team's repos already cloned (under any folder names) and the team's `cam-docs` URL reaches
the team's project from either door of the start screen or the CLI, with no second clone, no stray project and no
change to any team decision.

**Architecture:** A new use case `lib/app/repos_here.py` finds each team repo by its remote (`projects.remote_key`),
links `<workspace>/<name>` to a clone kept under another name (`fs_links.link`) and records the links and this
machine's search folders in the git-ignored cache. Setup, catch-up, the join's new read-only *repos* step and
uninstall use it. `components.here()` (the team's choice minus what this machine left out, kept in the cache) is what
setup installs and wires; `components.components()` stays the team's and is what the plan and the shared agent config
read. `projects.join` gains C1 (`Stray`, `set_aside`) and C2 (a clone already registered elsewhere: open it and add the
folder to its search folders). The hub's found card asks the team question.

**Tech Stack:** Python 3 (uv inline script, pytest + xdist), git CLI, React + Vite + Vitest (desktop renderer),
Electron main/preload (`node --test` for `desktop/lib`).

**Spec:** `docs/superpowers/specs/2026-11-18-join-and-stay-in-step-design.md` (§6.2, §6.3, §6.5, §6.7, §6.8, §7 row
S2, §8, §10 C1–C3, C7). S1 (`docs/superpowers/plans/2026-11-18-stay-in-step-s1.md`) is built on this branch.

## Global Constraints

- macOS, Windows and Linux: `pathlib`, `encoding="utf-8"`, processes through `lib/core/process.py` / the repos
  adapter's `git`; links only through `fs_links.link` (relative symlink, junction fallback on Windows) (AGENTS.md §2.1).
- TDD, offline: `make_workspace`, `isolated_env`, local bare repos (`tests/test_team_repo.py` `bare`, `publish`, `git`),
  `conftest.load_kit` for the second teammate (AGENTS.md §2.2).
- A join never writes `workspace.yaml` (`project.components`, repos, profile, interview mode), `plan.yaml` or a `.c4`
  file; with the same kit as the team's last commit, `git status` in `cam-docs` is clean after it (spec §3 item 3).
- No folder of the person's is renamed, moved or deleted; the one exception is C1, on the person's click, as a rename
  to `cam-docs.local-<YYYYMMDD>` next to it (spec §3 anti-goals).
- Per-machine state lives in `cam-docs/.camarones/.cache/` (git-ignored): `repos-here.json`
  (`{"search": [str], "links": {name: target}}`) and `components.json` (`{"skip": [id]}`). Missing file = today's
  behaviour (spec §6.8).
- `firstrun.json`: a join saved at `tools` or `setup` resumes there; a new join starts at `repos`; step ids stay
  `STEPS`'s.
- Every user-facing string in `es` and `en`; no joke in an error, a warning or a decision prompt (AGENTS.md §3).
- `lib/app/repos_here.py` is not carried by `services` (like `portal_views`): other layers import it directly.
- `VERSIONS["kit"]` → `4.95.0`, README badge with it; conventional commits; no AI co-author lines.

## Review Focus

1. **A clone found elsewhere that cannot be linked** (Windows without symlink rights or junctions): stays *missing*,
   says what to do, and setup does **not** clone a second copy. Test in Task 2 (`link` patched to fail).
2. **`<workspace>/<name>` is a different repo or a plain folder**: *taken*, never touched, and setup neither clones
   into it nor fails on it. Tests in Tasks 1 and 2.
3. **A kit link whose target was deleted or re-pointed** (the person removed their clone): the dangling link is
   dropped and the repo searched again, never left pointing nowhere. Test in Task 1.
4. **The team still has an old `firstrun.json` mid-join, or no per-machine files** (every 4.x project): resumes at its
   step; `here()` equals `components()`. Tests in Tasks 4 and 6.
5. **C1 on a `cam-docs` with commits or a remote**: refused as today (`Taken`), never set aside even with
   `--set-aside`. Test in Task 7.

---

### Task 1: `repos_here` — find each repo by its remote, link, record

**Files:**
- Create: `.camarones/lib/app/repos_here.py`
- Modify: `tests/architecture/layers.yaml` only if the layer scan does not cover it (`app.*` does)
- Test: `tests/test_repos_here.py` (new)

**Interfaces:**
- Produces:
  - `FILE = "repos-here.json"`; `load(cache: Path | None = None) -> dict` (`{"search": [], "links": {}}` when absent)
  - `add_search(folder: Path, cache: Path | None = None) -> list[str]` — resolved, de-duplicated; `ValueError("folder")`
    when not a folder
  - `find(log: Log = print) -> dict` — `{"rows": [{"name", "url", "state", "path"}], "here": [...], "linked": [...],
    "missing": [...], "taken": [...]}`; `state` ∈ `here · linked · missing · taken`; `path` is the clone a link points
    at, or the clone found but not linkable (state `missing`), else `""`
  - `links_made() -> dict[str, str]` — recorded links still on disk; `unlink_all(log) -> list[str]` — removes them and
    their `.git/info/exclude` lines, forgets the record
- Rules (spec §6.3): url empty → `here` if `<ws>/<name>/.git` exists else `missing`. A real `<ws>/<name>/.git` whose
  origin is empty or matches → `here`, else `taken`. A non-repo `<ws>/<name>` (or a link the kit did not record) →
  `taken`. A recorded link whose target no longer matches → unlinked, then searched again. Search: first level of the
  workspace, then the search folders; real dirs with `.git`, never a link, never `cam-docs`. Found → `link`; the link
  is recorded; when the workspace is a git repo, `fs_links.git_exclude(WORKSPACE, f"/{name}")`.

- [ ] **Step 1: Write the failing tests** — a helper `team_repos(kit, tmp_path)` gives each fixture repo a bare remote,
  sets `origin` and writes the urls in `workspace.yaml`:
  - `test_a_clone_under_its_own_name_is_here`
  - `test_a_clone_under_another_name_is_linked` (`mv api api-svc`; `find()` → `linked == ["api"]`,
    `os.path.realpath(ws/"api") == realpath(ws/"api-svc")`, `load()["links"] == {"api": str(ws/"api-svc")}`)
  - `test_a_clone_in_a_search_folder_is_linked`
  - `test_a_folder_with_another_repo_is_taken_and_left_alone` (and a plain folder; both untouched)
  - `test_a_repo_nowhere_is_missing`
  - `test_a_dangling_kit_link_is_dropped_and_searched_again`
  - `test_find_is_idempotent` (second run: same rows, no relink)
  - `test_a_link_that_cannot_be_made_stays_missing_with_its_path` (`fs_links.link` patched → False)
  - `test_unlink_all_removes_only_the_kit_links` (a link of the person's own survives) and the exclude line when the
    workspace is a git repo
- [ ] **Step 2:** `uv run pytest tests/test_repos_here.py -q` → fails (no module).
- [ ] **Step 3:** Implement `repos_here.py` (one git call per candidate folder, the index built only when a repo needs
  searching).
- [ ] **Step 4:** Tests pass.
- [ ] **Step 5:** Commit `feat(repos): find the team's repos by their remote and link a clone kept under another name`.

### Task 2: Setup and catch-up use it; setup never clones what is already here

**Files:**
- Modify: `.camarones/lib/adapters/git/repos.py` (`sync_repos(log, skip=())`), `.camarones/lib/ports/repo_sync.py`,
  `.camarones/lib/app/setup.py` (`setup`), `.camarones/lib/app/catchup.py` (`_run`)
- Test: `tests/test_repos_here.py`, `tests/test_catchup.py`

**Interfaces:**
- Consumes: `repos_here.find`.
- Produces: `sync_repos(log: Log = print, skip: Iterable[str] = ()) -> list[str]` — names in `skip` are neither cloned
  nor pulled; a `<ws>/<name>` that exists and is not a repo is skipped with a warning, never counted as failed.
  `setup()` calls `find` first and skips `taken` and found-but-unlinked repos. Catch-up's result gains
  `"repos": {"here", "linked", "missing", "taken"}` (step 2 of §6.1, no cloning).

- [ ] **Step 1: Failing tests:** `test_setup_links_a_renamed_clone_and_clones_only_what_is_missing` (sync_repos's clone
  goes to a bare remote; the renamed one is linked, not cloned), `test_setup_does_not_clone_over_an_unlinkable_clone`,
  `test_setup_skips_a_taken_folder_without_failing`, `test_catch_up_finds_the_repos` (result `repos.linked`).
- [ ] **Step 2:** Run → fail. **Step 3:** Implement. **Step 4:** Pass.
- [ ] **Step 5:** Commit `feat(setup): link the repos already on this machine before cloning the rest`.

### Task 3: Uninstall removes the links; the sandbox sees a leftover link

**Files:**
- Modify: `.camarones/lib/uninstall.py` (`steps`, `run`), `scripts/sandbox.py` (`traces`)
- Test: `tests/test_uninstall.py`, `tests/test_sandbox.py` (where `traces` is tested)

- [ ] **Step 1: Failing tests:** `test_uninstall_removes_the_repo_links_and_keeps_the_clones` (preview lists them; after
  `run`, `<ws>/api` is gone, `<ws>/api-svc` intact with its own files), `test_traces_flags_a_link_left_in_the_sandbox`.
- [ ] **Step 2–4:** fail, implement (`repos_here.unlink_all` after the repo cleaners, before `rmtree(ROOT)`; traces
  lists any first-level symlink or junction), pass.
- [ ] **Step 5:** Commit `feat(uninstall): take out the links to clones kept under other names`.

### Task 4: The team's components and this machine's tools

**Files:**
- Modify: `.camarones/lib/app/components.py`, `.camarones/lib/app/setup.py`, `.camarones/lib/onboard.py`,
  `.camarones/lib/install_state.py`
- Test: `tests/test_join_right.py` (new)

**Interfaces:**
- Produces: `components.MACHINE = "components.json"`; `here() -> list[str]` (the team's choice minus `skip`; no file →
  `components()`); `set_machine(chosen: list[str]) -> None` (`skip` = team's not in `chosen`); `onboard.joining() ->
  bool` (`mode(firstrun.json) == "join"`).
- Behaviour: `install_tools` writes `set_machine` on a join, `set_components` otherwise. `run_setup` on a join neither
  calls `plan.sync()` nor `plan.set_status("setup", …)` (the machine's setup is `install_state.mark_setup`). `setup`'s
  defaults (`install_tools`, `setup`, `setup_steps`, `wire_repo`, `wire_umbrella`) read `here()`; `wire_umbrella` writes
  the agent config with the team's `components()`. `local_ready`, `install_state.drift` and `repair` read `here()`.
  `tool_rows()` on a join lists only the team's kit components.

- [ ] **Step 1: Failing tests:**
  - `test_without_a_machine_file_here_is_the_teams_choice` (old form)
  - `test_a_join_leaves_cam_docs_clean` (team publishes; mate joins with `load_kit`, unticks every kit tool, runs
    `run_setup` offline with prerequisites patched ok, `done()`; `git status --porcelain` empty, `project.components`
    unchanged)
  - `test_unticking_openwiki_on_a_join_leaves_the_plans_wiki_units` (team has `repo-wiki` units todo; mate unticks
    openwiki; `plan.yaml` bytes unchanged)
  - `test_a_join_tools_step_lists_the_teams_components`
- [ ] **Step 2–4:** fail, implement, pass.
- [ ] **Step 5:** Commit `feat(onboard): a join keeps this machine's tools apart from the team's components`.

### Task 5: C3 — picking a component again restores what was dropped for it

**Files:** Modify `.camarones/lib/plan.py` (`NO_OPENWIKI` constant, the repo-wiki loop). Test: `tests/test_plan.py`.

- [ ] **Step 1: Failing test** `test_picking_openwiki_again_brings_back_its_units` (parametrized over the note:
  `NO_OPENWIKI`, `NO_WIKI`, another text): status `todo`; the kit's notes cleared.
- [ ] **Step 2–4:** fail, implement, pass. **Step 5:** Commit `fix(plan): picking OpenWiki again clears the notes it
  dropped its units with`.

### Task 6: The join's read-only repos step

**Files:**
- Modify: `.camarones/lib/onboard.py` (`JOIN_STEPS`, `join_repos`, `search`), `.camarones/lib/interfaces/http/routes/
  onboard.py` (`GET /api/app/onboard/repos-here`, `POST /api/app/onboard/search`), `.camarones/lib/wizard.py`
  (`fr_join_repos`, T strings es/en)
- Test: `tests/test_join_right.py`, `tests/test_team_repo.py` (join step tests updated), `tests/test_onboard_api.py`
  (or the module that covers the onboard routes)

**Interfaces:**
- Produces: `JOIN_STEPS = ("repos", "tools", "setup", "intro")`; `join_repos() -> dict` (= `repos_here.find()`);
  `search(folder: str) -> dict` (`add_search` then `find`; `ValueError("folder")`). Routes answer those dicts; a bad
  folder is a 400 `{"error": "folder"}`.

- [ ] **Step 1: Failing tests:** `test_a_new_join_starts_at_repos`, `test_a_join_saved_at_tools_resumes_there` (old
  form), `test_join_first_run_runs_the_repos_step_without_writing_workspace_yaml` (wizard, `fr_join_repos` with
  "go"), `test_the_search_route_remembers_the_folder_for_this_machine_only` (`workspace.yaml` unchanged).
- [ ] **Step 2–4:** fail, implement, pass. **Step 5:** Commit `feat(onboard): the join's first run shows what this
  machine has of each team repo`.

### Task 7: C1 and C2 in `projects.join`, the CLI, and `inspect`

**Files:**
- Modify: `.camarones/lib/projects.py` (`Stray`, `join(..., set_aside=False)`, `set_aside`), `.camarones/lib/interfaces/
  cli/launch.py` (`--set-aside`, `stray` JSON, `elsewhere` in the success JSON, TTY confirm),
  `.camarones/lib/interfaces/cli/commands/projects.py` (`--set-aside` declared, help: FOLDER is where the repos are),
  `.camarones/lib/onboard.py` (`inspect` → `stray: bool`)
- Test: `tests/test_join_right.py`

**Interfaces:**
- Produces: `class Stray(Taken)` with `.aside: str`; `stray(dest: Path) -> bool` (a kit project: `workspace.yaml`, no
  origin, no commit); `set_aside(dest: Path) -> Path` (`cam-docs.local-YYYYMMDD`, `-HHMMSS` added when taken; the old
  path unregistered). C2: a registered clone with the remote at another workspace → `repos_here.add_search(workspace,
  cache=Ctx.for_root(root).cache)` and reuse. JSON: `{"error": "stray", "detail", "aside"}`; success
  `{"path", "joined", "elsewhere"?}`.

- [ ] **Step 1: Failing tests:** `test_a_stray_cam_docs_is_refused_until_set_aside`, `test_set_aside_keeps_every_file`,
  `test_a_cam_docs_with_commits_or_a_remote_is_never_set_aside`, `test_join_opens_the_teams_docs_registered_elsewhere_
  and_searches_the_folder` (no second clone), `test_inspect_marks_a_stray_project`, `test_cli_join_prints_stray`.
- [ ] **Step 2–4:** fail, implement, pass. **Step 5:** Commit `feat(join): set aside a never-shared cam-docs and reuse
  the team's docs found elsewhere`.

### Task 8: The desktop app

**Files:**
- Modify: `desktop/renderer/src/hub.js`, `Hub.jsx`, `onboarding.js`, `sections/Start.jsx`, `i18n.js`;
  `desktop/lib/core.cjs`, `desktop/main.cjs`, `desktop/preload.cjs`; rebuild `desktop/renderer-build/`
- Test: `hub.test.js`, `Hub.test.jsx`, `Start.test.jsx`, `onboarding` tests, `desktop/test/core.test.cjs`

**Interfaces:**
- `card(found)` → `team: true` for `repo` / `umbrella` and a `stray` project (not with `home`); `canGo(c, team, url)`.
- `joinStep` on `{error: "stray", aside}` → `{...JOIN0, stray: true, aside, dir, say: {key: "hub.stray"}}`;
  `joinOnce(hub, state, url, token, t, setAside)`.
- `core.joinArgs(url, dir, setAside)` adds `--set-aside`; `JOIN_REASONS` gains `stray`; `joinFailure` keeps `aside`.
- `main.cjs`: `pickJoin` = "The folder where your repos are (or will be)"; `hub:join` passes `setAside`; a success with
  `elsewhere` shows a message box before opening; `app:pick` kind `folder` opens a directory dialog.
- Start: join mode's repos step is `JoinRepos` (rows from `GET app/onboard/repos-here`, *Buscar en otra carpeta…*
  → `app.pickFiles('folder')` → `POST app/onboard/search`); Continue never posts the repos list on a join; the tools
  step on a join says what leaving a tool out costs (`obCost.<id>`).

- [ ] **Step 1: Failing tests:** found card question (nothing preselected, Continue disabled until an answer; Yes needs
  a URL; Yes calls `hub.join` with the folder's workspace), stray confirm then `setAside`, `JoinRepos` rows and search,
  `canContinue('repos', {mode: 'join'})`, `joinArgs`/`joinFailure` for stray.
- [ ] **Step 2–4:** fail, implement, pass (`npm test` in `desktop/renderer`, `node --test "test/*.test.cjs"` in
  `desktop`); `npm run build`.
- [ ] **Step 5:** Commit the source, then `build(app): rebuilt desktop renderer for join right`.

### Task 9: Docs and version

README (es), guides `using` and `app` (en, es), `lib/tutorial.py` → `TUTORIAL.md`, `templates/docs/guides/tutorial.md`
and its es twin (existing projects keep their copy: say so), `VERSIONS["kit"] = "4.95.0"`. `uv run pytest
tests/test_guide.py tests/test_wizard.py -q` green. Commit `docs: join right (kit 4.95.0)`.

### Task 10: Whole suite and the sandbox

- [ ] `uv run pytest -n auto` green; `npm test` (renderer); `node --test` (desktop).
- [ ] Sandbox (`uv run scripts/sandbox.py reset`): teammate A publishes a `cam-docs` for both PetClinic repos to a
  local bare remote; in the sandbox the repos are renamed (`petclinic-api`, `petclinic-web`); `join <remote> <sandbox>`;
  the join's steps run; check: no new clone, two links, `git status` clean in `cam-docs`, plan and components unchanged,
  catch-up builds the C4 when LikeC4 is here; `uninstall --yes --no-backup`; folders renamed back; `traces` exit 0.

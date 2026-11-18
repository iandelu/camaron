# App redesign · Phase 2 (repos and SonarQube) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every repo of the project shows as a card on Flow › Summary and has a bento page at `#/flow/repo/<name>`; Quality gains a SonarQube tab with an "Estimated" panel; Board, Libraries, Docs › Wikis and Docs › Decisions take `?repo=`; every tile of the repo page opens its real window already filtered.

**Architecture:** Two read-only app-token GETs (`app/repo`, `app/repos`) compose what the kit already knows (health snapshot, freshness, wikis, C4 index, board, ADRs) plus three new static reads: the stack, weekly git activity (a `RepoFacts` adapter behind a port, cached per HEAD) and a coverage history the health build appends. The renderer draws them with a small chart kit in `@camaron/ui`; the SonarQube tab reads only the existing `GET health` snapshot.

**Tech Stack:** Python 3 (stdlib, kit helpers), pytest; React 19 + Vite + Vitest (`.camarones/desktop/renderer`), `@camaron/ui` (`.camarones/ui`), portal (`.camarones/portal/app`).

**Spec:** `docs/superpowers/specs/2026-11-18-app-redesign-design.md` (§3.1, §3.2, §4 `?repo=`, §5.1 `repoHref`, §5.2, §6 Wikis/Decisions `?repo=`, §8.2, §10.2, §11 Phase 2). Mockups: https://claude.ai/artifact/3zfJ385zLVtFvX44pJdZkK, artboards "Página del repo" (bento), "Flujo › Resumen", "Calidad › SonarQube".

## Calls made in this plan

- **Secrets arrive with Phase 3.** The repo page's Secrets tile, the cards' secrets line and the estimate's secrets figure need the secrets report (§8.1) and its window (§5.4), both Phase 3. Phase 2 leaves them out, so every tile it ships reaches a window that exists. Without Secrets the bento rows are: header 12 · SonarQube 4 + Activity 8 · Libraries 6 + Documentation 6 · Architecture 7 + Work 5.
- **The repo page is a view, not a tab.** `places.json` gains `"pages": { "flow": ["repo"] }`: addressable views that draw no tab and are not in `PLACES`. The page draws no Place shell (no "Flujo" h1, no tabs): a back link and the bento, as the mockup.
- **Sonar source rule:** a repo is `sonar` when its snapshot block has `sonar.server` figures (read at least once), else `estimated`. Not cloned or unreadable: no source.
- **Work tile colours:** the validated 4-step ordinal ramp maps Backlog+Ready → 1, In Progress → 2, In Review → 3, Done → 4; Blocked is a status (warn colour, with its word).
- **Docs tile:** a page counts for a repo when one of its own (non-doc) `x-sources` cites that repo; its state is freshness' (`fresh`, `suspect`, `stale`).
- **Phase 1 leftovers folded in:** the Board's Add menu gets arrow keys; the Plugins tab gets an empty state. ⌘K landing on the team strip's closed fold stays deferred (it needs a palette-wide "open this panel" address).

## Global Constraints

- Every user-facing string exists in `es` and `en` (renderer `src/i18n.js`; kit `ui/i18n/index.js`); no jokes in errors, warnings, prompts or empty "unknown" states (AGENTS.md §3).
- Every figure is static and local: no AI model, no network call, no new Sonar call (§1 anti-goals, §5.2).
- Python: `pathlib` only, `encoding="utf-8"`, `newline="\n"` on writes, processes through `lib.core.process` (`out`, `run`) — never `shell=True` (AGENTS.md §2.1).
- Layers (AGENTS.md §5): `lib/app` never imports an adapter module (`history`, `radar`, `quickarch`, `inventory`, `latest`, `codemap`, `kanban` package root…); it reaches them through `services.current().repo_facts`. `tests/architecture/allowlist.yaml` only shrinks.
- No raw colour in `ui/src/*` or `desktop/renderer/src/app.css`; new colours exist only as tokens in `ui/theme/tokens.css`, in all three blocks (`:root`, the dark media query, `:root[data-theme="dark"]`).
- Chart rules (§3.2, dataviz skill): thin marks, 4 px rounded data ends anchored to the baseline, 2 px gaps between segments and bars, hairline axes, one hue for a single series (`--series`), status colours only where colour means state and always beside a word, ordinal ramp light `#b3a0fb #9475f5 #7039e6 #5126b0` / dark `#5b3aa8 #7c5cd6 #a48bf0 #d4c8ff`, a tooltip on every bar and point, an `aria-label` with the numbers on every chart, a legend for ≥ 2 parts, text in ink tokens never in series colours; too little data says so instead of drawing.
- Motion: tiles rise staggered, bars grow from their baseline, segments and fills grow from the left; `transform` and `opacity` only, `var(--ease-out-soft)`; every animation sits inside `@media (prefers-reduced-motion: no-preference)`.
- Icons: generic stroke SVG (`fill="none" stroke="currentColor" stroke-width="1.6"`), never a product logo or an emoji; the label names the tool.
- Every repo-page tile that has a window links to it with `?repo=<name>` (`withRepo`, Task 5); no new window repeats another.
- Renderer tests are static (`renderToStaticMarkup`, Vitest in node): a view that loads data exposes a presentational component the test renders with fixtures. Run from `.camarones/desktop/renderer`: `npx vitest run src/<file>`; kit tests run through the portal's config (it includes `../../ui/**`): from `.camarones/portal/app`, `npx vitest run ../../ui/src/<file>` (`ui/` has no `node_modules` of its own); portal tests from there too, `npx vitest run src/<file>`; Python: `uv run pytest tests/<file> -q`.
- TDD: each task writes or changes its tests first and watches them fail. Conventional commits, no `Co-Authored-By` trailer, stage only this task's files (other sessions may edit the tree).
- Builds (`renderer-build/`, `portal/app-build/`), user docs and `VERSIONS["kit"] = "4.91.0"` land in Task 13 (AGENTS.md §5.1).

## Review Focus

1. **A repo listed but not cloned** (`cloned: false`): `GET app/repo` answers 200 with nulls, the page says "not cloned here" in the header and its tiles say nothing is known; its card shows "No state" → Task 3 (route test), Task 10 (`RepoBento` with `cloned: false`), Task 11 (card).
2. **No health snapshot yet** (a fresh project): `sonar` and `state` are null, the stack, activity, docs and work still show; the SonarQube tile and tab say the health has not been built and link to Quality › Health → Task 3, Task 9 (`SonarTable` with `snapshot: null`), Task 10.
3. **An odd repo address** (`#/flow/repo/my.repo`, `#/flow/repo/..%2Fx`, `?repo=<script>`): `repoPage`/`repoOf` keep only `[\w.-]+` names; the server answers 404 for a name not in the workspace and the page says "unknown repo" with the way back → Task 5, Task 3, Task 10.
4. **A snapshot block that failed** (`repos.<name>: {error}`, `sonar: {error}` with or without kept `server` figures): the SonarQube row reads "unread" with the reason, never crashes or shows 0 → Task 9 (`sonarRows`), Task 3 (`sonar.error`).
5. **`?repo=` naming a repo with nothing to show** (no cards, no ADRs, unknown to the wikis): Board says no card touches it with the chip that clears the filter; Decisions says the same with its own clear chip; Wikis shows every block unfolded → Task 7, Task 8.

---

### Task 1: Coverage history in the health build

**Files:**
- Modify: `.camarones/lib/health.py` (new `HISTORY`, `HISTORY_KEEP`, `append_history`, `history`; `build()` calls `append_history`)
- Test: `tests/test_health_history.py` (new)

**Interfaces:**
- Produces: `health.HISTORY = CACHE / "health" / "history.jsonl"`, `health.HISTORY_KEEP = 26`, `health.append_history(snap: dict, keep: int = HISTORY_KEEP) -> None`, `health.history() -> list[dict]` (oldest first, each `{"at": str, "repos": {name: float}}`).

- [ ] **Step 1: Write the failing tests** (`kit` fixture; snapshots built as plain dicts with `v`, `at`, `repos`):
  - `test_a_build_adds_one_line_per_repo_figure`: `append_history({"at": "2026-11-01T10:00:00Z", "repos": {"api": {"cloned": True, "coverage": {"percent": 71.5}}, "web": {"cloned": True, "coverage": None}, "worker": {"cloned": False}}})` → `history() == [{"at": "2026-11-01T10:00:00Z", "repos": {"api": 71.5}}]`.
  - `test_only_the_last_26_are_kept`: 30 appends with `at` = `f"2026-11-{i+1:02d}T00:00:00Z"` → `len(history()) == 26`, first `at` is the 5th, last is the 30th.
  - `test_a_broken_line_is_skipped`: write `not json\n` then append once → `len(history()) == 1`.
  - `test_a_failed_repos_block_writes_nothing`: `append_history({"at": "x", "repos": {"error": "boom"}})` → `history() == []`.
  - `test_build_appends`: in a `wired` workspace with a cloned repo holding a JaCoCo report, `health.build(log=lambda _: None)` twice → `len(history()) == 2`.
- [ ] **Step 2: Run** `uv run pytest tests/test_health_history.py -q` — expected: FAIL (`append_history` missing).
- [ ] **Step 3: Implement.** `append_history` takes each good, cloned repo with a numeric `_repo_percent`; writes nothing when the repos block failed or no repo has a figure; appends one JSON line, then rewrites the file keeping the last `keep` lines (under `lib.core.locks` if the module offers a file lock helper, else plain write — one build runs at a time). `build()` calls it through `_guard` after `save_json`, so a history failure never fails the build. `history()` returns `[]` for a missing file and skips lines that are not JSON objects.
- [ ] **Step 4: Run** the test — expected: PASS. Run `uv run pytest tests/test_health.py tests/test_health_sonar.py -q` — expected: PASS.
- [ ] **Step 5: Commit** `feat(health): keep the coverage of the last 26 health builds`.

---

### Task 2: Repo facts — stack, build tool, weekly activity (adapter + port)

**Files:**
- Modify: `.camarones/lib/history.py` (new pure `weekly`, new `activity`)
- Create: `.camarones/lib/adapters/repo_facts.py`, `.camarones/lib/ports/repo_facts.py`
- Modify: `.camarones/lib/app/services.py` (field `repo_facts: RepoFacts`), `.camarones/lib/bootstrap.py` (provider `_repo_facts`)
- Test: `tests/test_history.py` (extend), `tests/test_repo_facts.py` (new), `tests/test_services.py` (if it lists fields)

**Interfaces:**
- Produces (`history`): `weekly(stamps: list[int], today: date, weeks: int = 12) -> list[dict]` — exactly `weeks` items oldest first, `{"start": "YYYY-MM-DD" (the ISO week's Monday, UTC), "n": int}`, the last one today's week; `activity(repo: str, weeks: int = 12, today: date | None = None) -> dict | None` — `{"weeks": weekly(...), "total": int, "people": int, "last": {"author": str, "at": int, "subject": str} | None}`, `None` when git cannot read the repo.
- Produces (`repo_facts`, satisfying `ports.repo_facts.RepoFacts`): `build_tool(path: Path) -> str | None`; `facts(name: str) -> {"head", "stack", "build", "activity"}`; `outdated(name: str) -> int | None`; `graph_nodes(name: str) -> int | None`. `head` is `{"branch": str, "sha": str (7), "at": int, "subject": str, "author": str} | None`; `stack` is `[{"role": str, "label": str}]` with roles in the order `language`, `framework`…, `build`, `data`…, `container`, `ci`.
- Produces (services): `services.current().repo_facts`.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_history.py`: `weekly([], date(2026, 11, 18))` → 12 items, last `{"start": "2026-11-16", "n": 0}`, first `start` `"2026-08-31"`; a stamp at `2026-11-15T23:59:59Z` counts in week `2026-11-09` and one at `2026-11-16T00:00:00Z` in `2026-11-16`; a stamp older than the window is not counted. `activity` on a temp git repo (`git init`, three commits by two authors and one by `dependabot[bot]`, dates set with `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` inside the window) → `total == 3`, `people == 2`, `last["subject"]` the newest human commit; `activity` on a plain folder → `None`.
  - `tests/test_repo_facts.py` (`isolated_env`, temp repos under `make_workspace`):
    - `build_tool`: `pom.xml` → `"maven"`; `build.gradle.kts` → `"gradle"`; `package.json` + `pnpm-lock.yaml` → `"pnpm"`; + `yarn.lock` → `"yarn"`; `package.json` alone → `"npm"`; `pyproject.toml` + `uv.lock` → `"uv"`; + `poetry.lock` → `"poetry"`; `requirements.txt` → `"pip"`; `go.mod` → `"go"`; nothing → `None`.
    - `facts` of a repo with `pom.xml` (`<java.version>17</java.version>`, `spring-boot`, `postgresql`), `Dockerfile` and `.github/workflows/ci.yml` → `stack == [{"role": "language", "label": "Java 17"}, {"role": "framework", "label": "Spring Boot"}, {"role": "build", "label": "Maven"}, {"role": "data", "label": "PostgreSQL"}, {"role": "container", "label": "Docker"}, {"role": "ci", "label": "GitHub Actions"}]`.
    - a `workspace.yaml` `stack: "Kotlin · Ktor"` override → language `Kotlin`, framework `Ktor`.
    - cache: a second `facts` call with the same HEAD does not run `quickarch.repo_blob` again (monkeypatch it to count calls); a new commit recomputes.
    - not cloned → `{"head": None, "stack": [], "build": None, "activity": None}`.
    - `outdated`: inventory rows of the repo `a 1.0.0` and `b 2.0.0` with `latest.versions` `{"npm|a": "1.1.0", "npm|b": "2.0.0"}` → `1`; `latest` absent → `None`.
    - `graph_nodes`: a `graph.json` with 3 nodes at `graphify.repo_graph(name)` → `3`; missing → `None`.
- [ ] **Step 2: Run** `uv run pytest tests/test_history.py tests/test_repo_facts.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.**
  - `history.activity`: one `out(["git", "-C", str(repo_dir(repo)), "log", f"--since={weeks * 7 + 7}.days", "--no-merges", "--format=%aN%x09%at%x09%s"])`, `BOT` authors dropped; week buckets in UTC.
  - `repo_facts.facts`: `head` from `git rev-parse --abbrev-ref HEAD` and `git log -1 --format=%h%x09%at%x09%aN%x09%s`. Stack: the workspace row's `stack` override else `quickarch.stack(path, quickarch.repo_blob(path))`, split on ` · ` (first part = language unless it is `?`, the rest frameworks); build label from `BUILD_LABELS = {"maven": "Maven", "gradle": "Gradle", "npm": "npm", "pnpm": "pnpm", "yarn": "Yarn", "uv": "uv", "poetry": "Poetry", "pip": "pip", "go": "Go modules"}`; data from the manifests' text against `quickarch.DEP_DB` plus `"Redis"` for any `quickarch.CACHE_DEPS`; container and CI from the ids `radar.scan_repo(name, path)` finds: container `docker` → `"Docker"`, `compose` → `"Docker Compose"`, `helm` → `"Helm"`; CI `gitlab-ci`, `github-actions`, `jenkins`, `azure-pipelines` → their radar labels (`"GitLab CI"`, `"GitHub Actions"`, `"Jenkins"`, `"Azure Pipelines"`). Cache in `CACHE / "repos" / f"{name}.json"` as `{"key": {"head": sha, "week": "<ISO year>-W<nn>"}, "facts": {...}}`; recompute when the key differs; a write failure is ignored.
  - `outdated`: distinct `(ecosystem, name)` of the repo's inventory rows with `latest.newer(row["version"], versions.get(f"{eco}|{name}"))`.
  - `graph_nodes`: `len(json["nodes"])` of `graphify.repo_graph(name)`, `None` when missing or unreadable.
  - `ports/repo_facts.py`: `class RepoFacts(Protocol)` with the four methods. `services.py` declares the field; `bootstrap.py` adds `_repo_facts()` returning the module, and registers it in the providers mapping like `_code`.
- [ ] **Step 4: Run** the two test files, then `uv run pytest tests/test_services.py tests/test_architecture.py tests/test_env_split.py -q` — expected: PASS.
- [ ] **Step 5: Commit** `feat(repos): static repo facts — stack, build tool, weekly activity, cached per HEAD`.

---

### Task 3: `GET app/repo` and `GET app/repos`

**Files:**
- Modify: `.camarones/lib/harness/freshness.py` (new `by_repo`)
- Create: `.camarones/lib/app/repo_dashboard.py`, `.camarones/lib/interfaces/http/routes/repos.py`
- Modify: `tests/snapshots/routes.json` (two entries, `"access": "app"`), `tests/test_http_router.py` (`AREA`: both routes → `"repos"`)
- Test: `tests/test_app_repo.py` (new), `tests/test_freshness*.py` (extend the one that tests `states`)

**Interfaces:**
- Consumes: `health.load()`, `health.history()` (Task 1); `services.current().repo_facts` (Task 2); `services.current().wiki.wikis()`; `c4edit.index()`; `kanban.ops.list_items(repo=name)`; `adr.list_adrs()`.
- Produces: `freshness.by_repo() -> dict[str, {"fresh": int, "suspect": int, "stale": int}]`; `repo_dashboard.repo(name) -> dict | None` (None: not a repo of the workspace); `repo_dashboard.repos() -> {"at": str | None, "repos": list[dict]}`; routes `GET /api/app/repo?name=` (404 `{"error": "unknown repo"}`) and `GET /api/app/repos`, app token only.
- The `repo(name)` shape (exact keys; Tasks 10–11 read them):

```
{name, cloned: bool, state: "ok"|"warn"|"bad"|null, at: snapshot "at"|null,
 head: {branch, sha, at, subject, author}|null, stack: [{role, label}], build: str|null,
 sonar: {source: "sonar"|"estimated", gate: "OK"|"WARN"|"ERROR"|null, coverage: number|null,
         coverageSource: "sonar"|"report"|null, coverageAt: str|null, bugs, vulnerabilities, debtMinutes: number|null,
         link: str, host: str, connect: bool, error: str|null} | null,
 trend: [{at, coverage}]            # this repo's figure in the last 8 history lines that have one, oldest first
 activity: {weeks: [{start, n}]×12, total, people, last}|null,
 libs: {total: int|null, vulns: {severity: n}, scanned: bool, outdated: int|null},
 docs: {total, fresh, suspect, stale}|null, wiki: {pages, at, stale, chosen, unit}|null,
 c4: {fqn, title, technology, in: [{fqn, title}], out: [{fqn, title}]}|null, graph: int|null,
 work: {columns: [{status, n}] (all six statuses, board order), total}, adrs: [{id, title, chip, status}] (≤ 5, newest first)}
```

  `repos()` rows: `{name, cloned, state, stack, sonar: {source, gate, coverage, coverageSource}|null, libs: {vulns, scanned}, wiki: {pages, at, unit}|null, docs: {total, suspect, stale}|null}`, one per workspace repo in workspace order (freshness and wikis read once for all).

- [ ] **Step 1: Write the failing tests** in `tests/test_app_repo.py` (`wired` workspace; an app server fixture as in `tests/test_app_summary.py`; a snapshot planted with `save_json(health.SNAPSHOT, {...})` with `"v": 1`; `kanban.ops.list_items`, `adr.list_adrs`, `c4edit.index` and `freshness.by_repo` monkeypatched on their own modules):
  - `test_the_repo_page_with_sonar_figures`: snapshot repo `api` with `sonar.server = {"gate": "ERROR", "coverage": 41.0, "bugs": 12, "vulnerabilities": 2, "debt_minutes": 1960, "at": "…"}` and `link` → `sonar == {"source": "sonar", "gate": "ERROR", "coverage": 41.0, "coverageSource": "sonar", …, "bugs": 12, "vulnerabilities": 2, "debtMinutes": 1960, …}` and `state == "bad"`.
  - `test_without_sonar_the_estimate_reads_the_report`: `sonar.used = False`, `coverage = {"percent": 64.0, "source": "report", "at": "2026-11-15"}` → `sonar["source"] == "estimated"`, `coverage == 64.0`, `coverageSource == "report"`, `gate is None`, `bugs is None`.
  - `test_the_trend_is_the_last_8_figures`: 10 history lines with `api` and one without → `len(trend) == 8`, oldest first.
  - `test_work_counts_cards_by_column_and_lists_its_adrs`: cards `[{"status": "Backlog", "repos": ["api"]}, {"status": "Done", "repos": ["api", "web"]}]`, ADRs with `repos` `["api"]`, `["web"]` → `work == {"columns": [{"status": "Backlog", "n": 1}, {"status": "Ready", "n": 0}, {"status": "In Progress", "n": 0}, {"status": "In Review", "n": 0}, {"status": "Done", "n": 1}, {"status": "Blocked", "n": 0}], "total": 2}` and `[a["id"] for a in adrs]` only the `api` one.
  - `test_the_mini_c4_is_what_calls_it_and_what_it_calls`: an index with elements `browser`, `sys.api` (`metadata {"repo": "api"}`), `sys.db` and relations `browser→sys.api`, `sys.api→sys.db` → `c4["in"] == [{"fqn": "browser", "title": …}]`, `c4["out"] == [{"fqn": "sys.db", …}]`; no element for the repo → `c4 is None`.
  - `test_a_repo_not_cloned` (Review Focus 1): `worker` removed from disk → `cloned is False`, `head is None`, `activity is None`, `stack == []`.
  - `test_no_snapshot_yet` (Review Focus 2): no snapshot file → `state is None`, `sonar is None`, `at is None`, `trend == []`, `work` still counted.
  - `test_a_failed_sonar_block` (Review Focus 4): `sonar = {"error": "sin conexión"}` → `sonar is None`; `sonar = {"used": True, "error": "token no válido", "server": {…}}` → `source == "sonar"`, `error == "token no válido"`.
  - Routes: with the token `GET /api/app/repo?name=api` → 200 and `set(body) ==` the shape's keys; no token → 403; `name=nope` and `name=..%2Fapi` → 404 `{"error": "unknown repo"}` (Review Focus 3); `GET /api/app/repos` → 200, `[r["name"] for r in body["repos"]] == ["api", "web", "worker"]`, no token → 403.
  - Freshness test: two pages, one citing `api:src/A.java` (fresh) and one citing `api:x` and `web:y` (stale) → `by_repo() == {"api": {"fresh": 1, "suspect": 0, "stale": 1}, "web": {"fresh": 0, "suspect": 0, "stale": 1}}`.
- [ ] **Step 2: Run** `uv run pytest tests/test_app_repo.py tests/test_routes_snapshot.py tests/test_http_router.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.** `by_repo` counts each page of `states()` once under every repo its own sources name (`parse(src)[0]`, `kind(src) != "doc"`; `unverified` pages left out). `repo_dashboard` reads each source through a guard so one failing read nulls only its block; `state` is `snapshot["repo_state"][name]`; the C4 element is the one whose `metadata.repo == name` (first by fqn), else the one whose title equals the name; `in`/`out` are the other ends of its relations, deduped, sorted by title; `adrs` keep `id`, `title`, `chip`, `status`. `routes/repos.py` declares both routes with `access=Access.APP` and answers through `json_response`; a name not in `workspace.repo_names()` is 404 before any read.
- [ ] **Step 4: Run** the tests of Step 2 plus `uv run pytest tests/test_architecture.py -q` — expected: PASS.
- [ ] **Step 5: Commit** `feat(repos): GET app/repo and app/repos — one repo's dashboard and every repo's card`.

---

### Task 4: The chart kit in `@camaron/ui`

Load the `dataviz` skill before writing chart code.

**Files:**
- Create: `.camarones/ui/src/charts.js`, `.camarones/ui/src/charts.jsx`, `.camarones/ui/src/charts.test.js`, `.camarones/ui/src/charts.test.jsx`
- Modify: `.camarones/ui/src/index.js` (export `Sparkline`, `Bars`, `SegBar`, `HBars`), `.camarones/ui/src/ui.css` (`cu-spark`, `cu-bars`, `cu-seg`, `cu-hbars`, `cu-legend`, motion), `.camarones/ui/theme/tokens.css` (`--series`, `--ordinal-1`…`--ordinal-4` in the three blocks)
- Test: `.camarones/ui/theme/tokens.test.js`, `.camarones/ui/src/style.test.js`

**Interfaces:**
- Produces (`charts.js`, pure): `sparkGeometry(values: number[], { width = 240, height = 56, pad = 6 } = {}) -> { points: [{x, y, v}], line: string, area: string } | null` (null under 2 finite values; a flat series sits mid-height); `barScale(values: number[]) -> { max: number, heights: number[] }` (percent of the max, non-finite or negative → 0, all zero → zeros); `segmentParts(parts: [{key, n, ...}]) -> [{...part, pct}]` (drops n ≤ 0, pct of the total, `[]` when the total is 0); `hbarWidths(rows: [{key, n, ...}]) -> [{...row, pct}]` (pct of the largest n).
- Produces (`charts.jsx`): `Sparkline({ values, label, tips = [], width, height })` → `svg.cu-spark[role=img][aria-label]` with a hairline axis, an area, a 2 px line, the last point's dot and one hit circle per point (r ≥ 8) holding `<title>{tips[i]}</title>`; `null` when too little data. `Bars({ values, label, tips = [], top = true })` → `div.cu-bars[role=img][aria-label]`, one `.cu-bars-col[title][data-tip]` per value with a `.cu-bars-bar` (`height: <pct>%`, `--i` its index), a gridline labelled with the max and a 0 label. `SegBar({ parts, label })` → `div.cu-seg[role=img][aria-label]` of spans (`flex: <n> 1 0`, `title`) plus `ul.cu-legend` with a swatch and each part's `label`; a part has `tone: 'ok'|'warn'|'bad'` or `ordinal: 1..4`. `HBars({ rows, label })` → `div.cu-hbars[role=img][aria-label]`, one row per item: its label, a `.cu-hbars-track` with a `.cu-hbars-fill` (`width: <pct>%`, `tone`), its number.

- [ ] **Step 1: Write the failing tests.**
  - `charts.test.js`: `sparkGeometry([70])` → `null`; `sparkGeometry([70, 78], { width: 100, height: 50, pad: 5 }).points` → `[{x: 5, y: 45, v: 70}, {x: 95, y: 5, v: 78}]`; `sparkGeometry([3, 3]).points[0].y === 28`; `barScale([2, 4, 0])` → `{ max: 4, heights: [50, 100, 0] }`; `barScale([0, 0]).heights` → `[0, 0]`; `barScale([-1, NaN, 2]).heights` → `[0, 0, 100]`; `segmentParts([{key: 'a', n: 3}, {key: 'b', n: 0}, {key: 'c', n: 1}])` → `[{key: 'a', n: 3, pct: 75}, {key: 'c', n: 1, pct: 25}]`; `segmentParts([{key: 'a', n: 0}])` → `[]`; `hbarWidths([{key: 'h', n: 1}, {key: 'm', n: 2}]).map((r) => r.pct)` → `[50, 100]`.
  - `charts.test.jsx`: `Sparkline` with one value renders `''`; with two values the markup has `role="img"`, the given `aria-label`, two `<title>` elements with the tips and a `cu-spark-line`; `Bars` with `[1, 3]` has two `.cu-bars-col`, the tips as `title`, `height:33.3` (to one decimal) and `height:100%`; `SegBar` with an `ok` and a `warn` part renders their labels in the legend and `class="cu-seg-part cu-tone-ok"`; `HBars` renders each row's label and number and `width:50%`.
  - `tokens.test.js`: light `--series` is `#7039e6` and `--ordinal-1..4` are `#b3a0fb #9475f5 #7039e6 #5126b0`; dark (`:root[data-theme="dark"]`) `--series` `#a48bf0` and `#5b3aa8 #7c5cd6 #a48bf0 #d4c8ff`; the dark media block declares the same five.
  - `style.test.js`: the chart animations (`cu-bars-bar`, `cu-seg-part`, `cu-hbars-fill`, `cu-spark-line`, `cu-spark-area`, `cu-spark-dot`) appear with `animation` only inside the `prefers-reduced-motion: no-preference` block, and their keyframes animate only `transform` and `opacity`.
- [ ] **Step 2: Run** from `.camarones/portal/app`: `npx vitest run ../../ui/src/charts.test.js ../../ui/src/charts.test.jsx ../../ui/src/style.test.js ../../ui/theme/tokens.test.js` — expected: FAIL.
- [ ] **Step 3: Implement** to the interfaces. Bars and fills have 4 px radius on their data end only (`border-radius: 4px 4px 0 0` for a column, `0 4px 4px 0` for a horizontal fill, the first and last segment rounded at their outer end); `gap: 2px` between segments and between bars; axis and gridlines `1px solid var(--color-rule)`; fills `var(--series)`, `var(--ordinal-N)`, `var(--color-estado-bien|aviso|mal)`; labels and numbers in `--color-ink*`; hover dims the other bars (`opacity`) and shows `data-tip` as a tooltip. Motion: keyframes `cu-grow-y` (scaleY 0→1, origin bottom), `cu-grow-x` (scaleX 0→1, origin left), `cu-fade` (opacity), `cu-pop` (scale), `var(--ease-out-soft)`, staggered with `animation-delay: calc(var(--i, 0) * 40ms)`, inside the existing no-preference media block.
- [ ] **Step 4: Run** the tests of Step 2, then the portal's whole suite (`npm test`, which holds the kit's) and the renderer's `npm test` — expected: PASS.
- [ ] **Step 5: Commit** `feat(ui): a small chart kit — sparkline, bars, segmented bar, horizontal bars`.

---

### Task 5: `?repo=` and the repo page's address in `nav.js`

**Files:**
- Modify: `.camarones/desktop/renderer/src/places.json` (add `"pages": { "flow": ["repo"] }`), `src/nav.js`, `src/crumbs.js`, `tests/test_desktop_places.py` (a page counts as a view in the clash check)
- Test: `src/nav.test.js`, `src/crumbs.test.js`

**Interfaces:**
- Produces (`nav.js`): `PAGES` (from `places.json`); `viewOf(hash, section)` also returns a page name; `placeOf('#/flow/repo/api')` → `'flow/repo'`; `PLACES` unchanged (pages are not places); `repoOf(hash) -> string` ('' unless the `repo` query value matches `/^[\w.-]+$/`); `repoPage(hash) -> string | null` (the decoded `<name>` of `#/flow/repo/<name>` when it matches `/^[\w.-]+$/`); `repoHref(name) -> '#/flow/repo/' + encodeURIComponent(name)`; `withRepo(place, name) -> '#/' + place + '?repo=' + encodeURIComponent(name)`.
- Produces (`crumbs.js`): `#/flow/repo/api` → `[{ label: project, href: '#/flow' }, { label: 'Flujo', href: '#/flow' }, { label: 'api' }]`.

- [ ] **Step 1: Write the failing tests:**

```js
expect(viewOf('#/flow/repo/api', 'flow')).toBe('repo')
expect(placeOf('#/flow/repo/api', {})).toBe('flow/repo')
expect(PLACES).not.toContain('flow/repo')
expect(repoOf('#/board?repo=api')).toBe('api')
expect(repoOf('#/docs/decisions?repo=my.repo-2&x=1')).toBe('my.repo-2')
expect(repoOf('#/board?repo=%3Cscript%3E')).toBe('')
expect(repoOf('#/board')).toBe('')
expect(repoPage('#/flow/repo/api')).toBe('api')
expect(repoPage('#/flow/repo/my.repo')).toBe('my.repo')
expect(repoPage('#/flow/repo/..%2Fx')).toBeNull()
expect(repoPage('#/flow/repo/')).toBeNull()
expect(repoPage('#/flow')).toBeNull()
expect(repoHref('a b')).toBe('#/flow/repo/a%20b')
expect(withRepo('quality/sonar', 'api')).toBe('#/quality/sonar?repo=api')
expect(crumbs({ hash: '#/flow/repo/api', project: 'p', t })).toEqual([{ label: 'p', href: '#/flow' }, { label: 'Flujo', href: '#/flow' }, { label: 'api' }])
```

- [ ] **Step 2: Run** `npx vitest run src/nav.test.js src/crumbs.test.js` — expected: FAIL.
- [ ] **Step 3: Implement** to the interfaces; `crumbs` names a page's last crumb with `repoPage(hash)`. In the Python guard, the views of a place are `views[place] + pages[place]`.
- [ ] **Step 4: Run** the two tests, `npm test` (whole renderer suite) and `uv run pytest tests/test_desktop_places.py -q` — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): the repo page's address and ?repo= in nav`.

---

### Task 6: The SonarQube tab (`#/quality/sonar`)

**Files:**
- Create: `.camarones/desktop/renderer/src/sonar.js`, `src/sonar.test.js`, `src/sections/SonarView.jsx`, `src/SonarView.test.jsx`
- Modify: `src/places.json` (`"quality": ["health", "sonar", "libs"]`), `src/sections/Quality.jsx` (render `SonarView` for `sonar`; `repoHref` → `nav.repoHref`), `src/i18n.js`, `src/app.css`
- Test: `src/palette.test.js` (the sections group lists `go:quality/sonar` after `go:quality`), `src/Quality.test.jsx`

**Interfaces:**
- Consumes: `repoOf`, `repoHref`, `withRepo` (Task 5); `@camaron/ui/health.js` `gateWord`, `gateState`, `fmtDebt`, `fmtAgo`, `safeUrl`, `sonarReason`, `sonarGone`, `sonarConnectHash`.
- Produces (`sonar.js`): `sonarSource(block) -> 'sonar' | 'estimated' | null`; `sonarRows(snapshot, t, now) -> Array<{ name, source, gate, gateState, coverage, coverageNote, bugs, vulns, debt, link, host, connect, error, unread }>` (strings; a dash for a missing figure; `unread: true` and `error` for a failed block; not cloned → `source: null`); `estimate(snapshot, name) -> { coverage: { percent, at } | null, vulns: { total, high }, stale: int, suspect: int, host: string }`; `filterSonar(rows, { repo, source }) -> rows`; `sourceCounts(rows) -> { sonar, estimated }`.
- Produces (`SonarView.jsx`): `SonarTable({ snapshot, repo, source, open, onRepo, onSource, onOpen, onRefresh, refreshing, now })` (presentational) and default `SonarView({ srv, jobs })` (reads `GET health`; "Read again" runs the catalog command `health` with `{ refresh: true }` quietly, as Health does; seeds `repo` from `repoOf(hash)` and follows the hash).

- [ ] **Step 1: Write the failing tests.**
  - `sonar.test.js` (a snapshot fixture with `api` sonar-backed `{gate: 'OK', coverage: 78, bugs: 3, vulnerabilities: 0, debt_minutes: 540}` and link `https://sonar.example.com/dashboard?id=api`, `web` with only a report `{percent: 64, source: 'report', at: '2026-11-15'}`, vulns `{high: 1, medium: 4}` and 2 stale pages, `worker` `{cloned: false}`, `bad` `{error: 'boom'}`):
    - `sonarRows(snap, t, now).map((r) => [r.name, r.source])` → `[['api', 'sonar'], ['web', 'estimated'], ['worker', null], ['bad', null]]`;
    - api: `gate` the word for OK, `gateState: 'ok'`, `coverage: '78 %'`, `bugs: '3'`, `debt: '1 d 1 h'`, `link` the URL; a `javascript:` link → `link: null`;
    - web: `gate: '—'`, `coverage: '64 %'`, `coverageNote` contains the report word, `bugs: '—'`;
    - bad: `unread: true`, `error: 'boom'`;
    - `estimate(snap, 'web')` → `{ coverage: { percent: 64, at: '2026-11-15' }, vulns: { total: 5, high: 1 }, stale: 2, suspect: 0, host: '' }`;
    - `filterSonar(rows, { repo: 'web' })` keeps `web`; `{ source: 'sonar' }` keeps `api`; `sourceCounts(rows)` → `{ sonar: 1, estimated: 1 }`;
    - `sonarRows(null, t, now)` → `[]`.
  - `SonarView.test.jsx`: `SonarView` with a never-resolving `srv` (and `globalThis.location = { hash: '#/quality/sonar' }`) renders a skeleton; `SonarTable` renders a table with columns Repo · Fuente · Puerta · Cobertura · Bugs · Vulnerab. código · Deuda; api's row has an `Abrir en SonarQube ↗` link to its URL with `target="_blank"` and `rel="noreferrer"`; the source filter reads `SonarQube · 1` and `Estimado · 1` with `aria-pressed`; with `open="web"` the estimate panel shows `64 %`, a link to `#/quality/libs?repo=web`, the "cannot be estimated" line and `Conectar SonarQube` linking to `#/settings/tokens?kind=sonarqube`; with `repo="web"` only web's row shows; with `snapshot={null}` an empty state links to `#/quality` (Review Focus 2); a row with `unread` shows the reason.
  - `Quality.test.jsx`: at `#/quality/sonar` the `SonarQube` tab is current.
  - `palette.test.js`: the expected ids gain `'go:quality/sonar'` right after `'go:quality'`.
- [ ] **Step 2: Run** `npx vitest run src/sonar.test.js src/SonarView.test.jsx src/Quality.test.jsx src/palette.test.js` — expected: FAIL.
- [ ] **Step 3: Implement.** Repo names in the table link to `repoHref(name)`, and so does the Health board: `Quality.jsx`'s own `repoHref` (today `'../#/health/' + …`, the portal's page) is replaced by `nav.repoHref` (§5.1). The estimate row toggles its panel (`aria-expanded`) below it; the panel's four figures are coverage (report, date), library vulnerabilities (`withRepo('quality/libs', name)`), stale pages (`withRepo('docs/wikis', name)`), and the line of what cannot be estimated; **Conectar SonarQube** → `sonarConnectHash(host)`. Under the table, the line that the server's figure always wins. i18n (es / en):
  - `nav.sonar` SonarQube / SonarQube; `sq.repo` Repo / Repo; `sq.all` Todos / All; `sq.source` Fuente / Source; `sq.sources` Todas / All; `sq.sonar` SonarQube / SonarQube; `sq.estimated` Estimado / Estimated; `sq.gate` Puerta / Gate; `sq.coverage` Cobertura / Coverage; `sq.bugs` Bugs / Bugs; `sq.vulns` Vulnerab. código / Code vulnerab.; `sq.debt` Deuda / Debt; `sq.open` Abrir en SonarQube ↗ / Open in SonarQube ↗; `sq.read` Leído hace {ago} / Read {ago}; `sq.again` Volver a leer / Read again; `sq.show` Ver estimación ▸ / See estimate ▸; `sq.hide` Ocultar estimación ▾ / Hide estimate ▾;
  - `sq.estTitle` Estimación sin SonarQube · {repo} / Estimate without SonarQube · {repo}; `sq.estBadge` Calculado por el kit, sin servidor / Worked out by the kit, no server; `sq.estCoverage` Cobertura / Coverage; `sq.estReport` informe de cobertura del repo / the repo's coverage report; `sq.estNoReport` Sin informe / No report; `sq.estLibs` Vulnerab. en librerías / Library vulnerab.; `sq.estLibsGo` {high} altas · ver en Librerías → / {high} high · see Libraries →; `sq.estStale` Páginas desactualizadas / Out-of-date pages; `sq.estStaleGo` ver en Docs → / see Docs →; `sq.estCannot` Sin SonarQube no se puede saber: bugs, code smells, duplicados ni deuda técnica. / Without SonarQube there is no way to know bugs, code smells, duplication or technical debt.; `sq.connect` Conectar SonarQube / Connect SonarQube; `sq.connectWhy` Si el repo ya está en SonarQube, al conectarlo se leen sus cifras reales y la estimación desaparece. / If the repo is already in SonarQube, connecting reads its real figures and the estimate goes away.;
  - `sq.wins` Estimado = lo que el kit sabe sin servidor. Cuando SonarQube tiene una cifra, siempre gana la del servidor. / Estimated = what the kit knows without a server. When SonarQube has a figure, the server's always wins.; `sq.none` Aún no hay foto de salud del proyecto. / There is no health snapshot of the project yet.; `sq.noneGo` Hacerla en Salud / Build it in Health; `sq.unread` Sin leer / Unread; `sq.notCloned` No está clonado aquí / Not cloned here.
- [ ] **Step 4: Run** the tests of Step 2 and `npm test` — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): Quality › SonarQube — Sonar's figures per repo, an estimate where there is none`.

---

### Task 7: Board `?repo=` (with `applyFilters` moved to the kit)

**Files:**
- Modify: `.camarones/ui/src/kanban.js` (gains `applyFilters` and its `DOCS` rule, moved verbatim), `.camarones/ui/src/kanban.test.js` (gains the `applyFilters` tests), `.camarones/portal/app/src/kanban.js` (drops its copy, re-exports `applyFilters` from `@camaron/ui/kanban.js`), `.camarones/portal/app/src/kanban.test.js` (drops the moved tests), `.camarones/desktop/renderer/src/sections/Board.jsx`, `src/i18n.js`
- Test: `src/Board.test.jsx`

**Interfaces:**
- Consumes: `repoOf`, `repoHref` (Task 5).
- Produces: `applyFilters(cards, { repo, epic, label, docs, parent })` exported by `@camaron/ui/kanban.js`; `BoardView` takes `repo` (string) and draws the board it is given.

- [ ] **Step 1: Write the failing tests.** In `ui/src/kanban.test.js`, the portal's `applyFilters` cases (moved). In `Board.test.jsx`: `BoardView` with `repo="api"` and a board already filtered to the api cards renders a chip reading `Repo: api` with a link `href="#/board"` labelled `Quitar el filtro de api`, and the repo name links to `#/flow/repo/api`; with `repo="zzz"` and no cards it renders `Ninguna tarjeta toca zzz.` and the same clear link (Review Focus 5); without `repo` there is no chip.
- [ ] **Step 2: Run** from `.camarones/portal/app`: `npx vitest run ../../ui/src/kanban.test.js src/kanban.test.js`; from `.camarones/desktop/renderer`: `npx vitest run src/Board.test.jsx` — expected: the kit and Board tests FAIL.
- [ ] **Step 3: Implement.** `Board` reads `repoOf(useHash())`; `shown = repo ? { ...board, cards: applyFilters(board.cards, { repo }) } : board`; the columns, the keyboard and `BoardView` use `shown`; the story panel's children and moves keep the whole board. i18n (es / en): `bd.repo` Repo: {repo} / Repo: {repo}; `bd.repoClear` Quitar el filtro de {repo} / Clear the {repo} filter; `bd.repoEmpty` Ninguna tarjeta toca {repo}. / No card touches {repo}.
- [ ] **Step 4: Run** portal `npm test` (with the kit's tests) and renderer `npm test` — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): Board takes ?repo=; applyFilters moves to @camaron/ui/kanban.js`.

---

### Task 8: `?repo=` on Libraries, Docs › Wikis and Docs › Decisions

**Files:**
- Modify: `src/sections/Libs.jsx` (props `repo`, `initial`), `src/sections/Quality.jsx` (pass `repo={repoOf(hash)}`), `src/docs.js` (new `focusRepo`), `src/sections/Docs.jsx` (`WikisView` takes `repo`), `src/adr.js` (`filterRows` takes `repo`), `src/sections/adr/AdrList.jsx` (prop `repo`, chip), `src/sections/Decisions.jsx` (passes `repoOf(hash)`), `src/i18n.js`
- Test: `src/Libs.test.jsx`, `src/docs.test.js`, `src/Docs.test.jsx`, `src/adr.test.js`, `src/Decisions.test.jsx`

**Interfaces:**
- Consumes: `repoOf` (Task 5); `LibrariesBoard`'s existing `repo` prop.
- Produces: `Libs({ srv, jobs, repo = '', initial = null })` (`initial`: the inventory to start from, for tests); `focusRepo(blocks, repo) -> { first: block | null, rest: block[] }`; `filterRows(rows, filter, q, repo = '')`; `AdrListView({ …, repo = '' })`.

- [ ] **Step 1: Write the failing tests.**
  - `Libs.test.jsx`: `<Libs srv={srv} jobs={null} repo="web" initial={{ libraries: rows }} />` renders the repo facet with `web` selected.
  - `docs.test.js`: `focusRepo([{repo: 'api'}, {repo: 'web'}], 'web')` → `{ first: {repo: 'web'}, rest: [{repo: 'api'}] }`; `focusRepo(blocks, 'zzz')` → `{ first: null, rest: blocks }`; `focusRepo(blocks, '')` → `{ first: null, rest: blocks }`.
  - `Docs.test.jsx`: at `#/docs/wikis?repo=web` the `web` block comes first and the others sit inside a `<details>` whose summary reads `Las otras wikis (2)`; at `#/docs/wikis?repo=zzz` there is no `<details>` (Review Focus 5).
  - `adr.test.js`: `filterRows(rows, 'all', '', 'api')` keeps only rows whose `repos` include `api`; `filterRows(rows, 'all', '')` keeps all.
  - `Decisions.test.jsx`: `AdrListView` with `repo="api"` lists only api's ADRs, the counts are api's, a chip `Repo: api` links to `#/docs/decisions` (`aria-label` `Quitar el filtro de api`); with `repo="zzz"` it says `Ningún ADR nombra zzz.` with the same clear link.
- [ ] **Step 2: Run** `npx vitest run src/Libs.test.jsx src/docs.test.js src/Docs.test.jsx src/adr.test.js src/Decisions.test.jsx` — expected: FAIL.
- [ ] **Step 3: Implement.** `WikisView` draws `first` open, then `rest` inside `Fold` (`parts.jsx`) when there is a `first`, else every block as today. The ADR counts come from the rows the repo keeps. The clear chip reuses Board's `bd.repo` / `bd.repoClear` strings. i18n (es / en): `docs.otherWikis` Las otras wikis ({n}) / The other wikis ({n}); `adr.repoEmpty` Ningún ADR nombra {repo}. / No ADR names {repo}.
- [ ] **Step 4: Run** the tests of Step 2 and `npm test` — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): ?repo= on Libraries, Docs › Wikis and Docs › Decisions`.

---

### Task 9: The repo page — pure tile models and icons

**Files:**
- Create: `.camarones/desktop/renderer/src/repo.js`, `src/repo.test.js`, `src/icons.jsx`
- Test: `src/repo.test.js`

**Interfaces:**
- Consumes: `withRepo` (Task 5); the `repo(name)` shape (Task 3).
- Produces (`repo.js`):
  - `tileLinks(name) -> { sonar, libs, wikis, board, decisions }` — `withRepo('quality/sonar' | 'quality/libs' | 'docs/wikis' | 'board' | 'docs/decisions', name)`.
  - `sonarTile(sonar, trend) -> { source, coverage: number | null, delta: number | null, points: number[], gate: string | null }` — `delta` is last − first of `trend` rounded to one decimal, null under 2 points.
  - `activityBars(activity, l) -> { values: number[], tips: string[], months: string[] } | null` — tip `'<d MMM> · <n> commit(s)'` via `Intl.DateTimeFormat(l, { day: 'numeric', month: 'short' })` with `rp.commit` / `rp.commits`; `months` are the short month names where a week starts a new month (first week included).
  - `libsRows(libs) -> [{ key: 'critical', n, tone: 'bad' }, { key: 'high', n, tone: 'bad' }, { key: 'medium', n: medium + moderate, tone: 'warn' }, { key: 'low', n, tone: null }]`.
  - `docsParts(docs) -> [{ key: 'fresh', n, tone: 'ok' }, { key: 'suspect', n, tone: 'warn' }, { key: 'stale', n, tone: 'bad' }]`.
  - `workParts(work) -> [{ key: 'todo', n, ordinal: 1 }, { key: 'doing', n, ordinal: 2 }, { key: 'review', n, ordinal: 3 }, { key: 'done', n, ordinal: 4 }, { key: 'blocked', n, tone: 'warn' }]` (todo = Backlog + Ready, doing = In Progress, review = In Review).
  - `ROLES = ['language', 'framework', 'build', 'data', 'container', 'ci']`.
- Produces (`icons.jsx`): `Icon({ name })` — a 24-unit stroke SVG, `aria-hidden="true"`, for `language`, `framework`, `build`, `data`, `container`, `ci`, `sonar`, `activity`, `libs`, `docs`, `arch`, `work` (shapes as the mockup: brackets, layers, box, cylinder, container, branch, gauge, pulse, shield, book, boxes, columns).

- [ ] **Step 1: Write the failing tests:**

```js
expect(tileLinks('api')).toEqual({ sonar: '#/quality/sonar?repo=api', libs: '#/quality/libs?repo=api',
  wikis: '#/docs/wikis?repo=api', board: '#/board?repo=api', decisions: '#/docs/decisions?repo=api' })
expect(sonarTile({ source: 'sonar', coverage: 78, gate: 'OK' }, [{ coverage: 70 }, { coverage: 78 }]))
  .toEqual({ source: 'sonar', coverage: 78, delta: 8, points: [70, 78], gate: 'OK' })
expect(sonarTile({ source: 'estimated', coverage: null, gate: null }, [{ coverage: 64 }]).delta).toBeNull()
expect(sonarTile(null, []).source).toBeNull()
const weeks = [{ start: '2026-08-31', n: 2 }, { start: '2026-09-07', n: 1 }, ...Array.from({ length: 10 }, (_, i) => ({ start: `2026-10-${String(5 + i * 7).padStart(2, '0')}`, n: 0 }))]
const bars = activityBars({ weeks, total: 3, people: 1, last: null }, 'es')
expect(bars.values.slice(0, 2)).toEqual([2, 1])
expect(bars.tips[0]).toBe('31 ago · 2 commits')
expect(bars.tips[1]).toBe('7 sept · 1 commit')
expect(bars.months[0]).toBe('ago')
expect(activityBars(null, 'es')).toBeNull()
expect(libsRows({ vulns: { high: 1, medium: 1, moderate: 2 } }).map((r) => r.n)).toEqual([0, 1, 3, 0])
expect(workParts({ columns: [{ status: 'Backlog', n: 1 }, { status: 'Ready', n: 1 }, { status: 'In Progress', n: 1 },
  { status: 'In Review', n: 0 }, { status: 'Done', n: 2 }, { status: 'Blocked', n: 1 }], total: 6 }).map((p) => p.n)).toEqual([2, 1, 0, 2, 1])
```

(Write the month expectations against what `Intl` gives in node for `es` — check with a one-line `node -e` first and use that output; the test must not depend on the machine's locale beyond the `l` passed.)
- [ ] **Step 2: Run** `npx vitest run src/repo.test.js` — expected: FAIL.
- [ ] **Step 3: Implement** to the interfaces. i18n (es / en): `rp.commit` commit / commit; `rp.commits` commits / commits.
- [ ] **Step 4: Run** the test — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): the repo page's tile models, links and stroke icons`.

---

### Task 10: The repo page (`#/flow/repo/<name>`)

**Files:**
- Create: `.camarones/desktop/renderer/src/sections/RepoPage.jsx`, `src/RepoPage.test.jsx`
- Modify: `src/sections/Flow.jsx` (view `repo` → `RepoPage`, no Place shell), `src/app.css` (`dk-bento`, `dk-tile`, spans, hero, stack pills, mini C4, motion), `src/i18n.js`
- Test: `src/Flow.test.jsx`, `src/style.test.js`

**Interfaces:**
- Consumes: Tasks 3, 4, 5, 9; `openPortal` (`docs.js`); `stateWord`, `gateWord`, `gateState`, `fmtAgo`, `fmtDebt`, `uiText` (`@camaron/ui`); `StatusChip` and `chipOf` (`sections/adr/Read.jsx`) for the ADR rows.
- Produces: `RepoBento({ data, now, onPortal })` (presentational; `data` is `GET app/repo`'s body) and default `RepoPage({ srv, app, name })` (`name` null → `rp.unknown` at once, no request; else reads `GET app/repo?name=`; skeleton while it reads; `Failed` with Retry on an error; on a 404 an `EmptyState` `rp.unknown` with the way back to `#/flow`).

- [ ] **Step 1: Write the failing tests** in `RepoPage.test.jsx` with a full fixture `data` for `api` (sonar-backed, 8 trend points, activity, libs with vulns, docs 9/2/1, wiki 42 pages, c4 with one caller and two callees, graph 214, work columns, two ADRs):
  - The markup has a link `← Resumen` to `#/flow`, an `h1` reading `api`, the state word beside its chip (`stateWord('code', 'bad', …)`), `rama` + `main` and the stack pills each with its role and label (`Lenguaje` `Java 17`, … `CI` `GitHub Actions`).
  - **Every tile with a window links to it, filtered:** the markup contains `href="#/quality/sonar?repo=api"`, `href="#/quality/libs?repo=api"`, `href="#/docs/wikis?repo=api"`, `href="#/board?repo=api"` and `href="#/docs/decisions?repo=api"`.
  - SonarQube tile (`debtMinutes: 540`): `78 %`, the gate word, a `cu-spark` with `aria-label` naming the first and last figures, Bugs `3`, Deuda `1 d 1 h`; with `source: 'estimated'` it shows `Estimado` and the coverage with `informe`, no gate; with one trend point it shows `rp.trendFew` and no `cu-spark`; with `sonar: null` it says `rp.noHealth` and links to `#/quality` (Review Focus 2).
  - Activity tile: a `cu-bars` whose `aria-label` holds `34` and `12`, twelve columns, the last commit's subject; with `activity: null` it shows `rp.noGit`.
  - Libraries tile: a `cu-hbars` with the four severity words and numbers, `De 5 librerías · 4 con versión nueva`; `scanned: false` → `rp.libsNever`.
  - Documentation tile: `12` pages, a `cu-seg` with the legend words `al día`, `por revisar`, `desactualizadas`, `Wiki · 42 páginas →`; a button `Revisar 3 ↗` calls `onPortal('#/review')` (not a link).
  - Architecture tile: the caller, the repo's own box marked `este repo`, both callees, `214 nodos en el grafo de código`, buttons `Ver el C4 ↗` (`onPortal('#/c4')`) and `Ver el grafo ↗` (`onPortal('#/code/api/graph')`); `c4: null` → `rp.noC4`.
  - Work tile: `6 tarjetas tocan este repo`, a `cu-seg` with the column words, both ADR ids and titles.
  - `cloned: false` → the header says `rp.notCloned` and no stack pills (Review Focus 1).
  - `Flow.test.jsx`: at `#/flow/repo/api` (with a never-resolving `srv`) there is no `nav.dk-guide-tabs`, no `h1` reading `Flujo`, and a skeleton while it reads; at `#/flow/repo/..%2Fx` it renders `rp.unknown` without calling `srv.get` (Review Focus 3).
  - `style.test.js`: `.dk-tile` animates only inside `prefers-reduced-motion: no-preference` and its keyframes use only `transform` and `opacity`; `.dk-bento` is a 12-column grid that becomes one column under 1000 px.
- [ ] **Step 2: Run** `npx vitest run src/RepoPage.test.jsx src/Flow.test.jsx src/style.test.js` — expected: FAIL.
- [ ] **Step 3: Implement.** Layout and look as the mockup's "Página del repo": `dk-bento` (12 columns, 14 px gap; one column under 1000 px), tiles `dk-tile` with spans `s12` header, `s4` SonarQube, `s8` Activity, `s6` Libraries, `s6` Documentation, `s7` Architecture, `s5` Work. The SonarQube and Libraries tiles are whole-tile links (`a.dk-tile`, lift on hover with `transform`) ending in `Calidad › SonarQube →` / `Calidad › Librerías →`; Documentation, Architecture and Work are `section`s with their own links and buttons; Activity has none. Status colour always beside its word (chips via `Chip`). The mini C4 is HTML boxes (callers · arrow · this repo · arrow · callees). Tiles rise staggered (`--i`), pills rise, C4 boxes rise, all inside the no-preference media block. i18n (es / en):
  - `rp.back` ← Resumen / ← Summary; `rp.branch` rama / branch; `rp.lastCommit` último commit {ago} / last commit {ago}; `rp.health` salud {ago} / health {ago}; `rp.notCloned` No está clonado en esta máquina: no se sabe nada de él aquí. / Not cloned on this machine: nothing is known about it here.; `rp.stackNote` Stack leído del código, sin IA. Cada bloque abre su ventana, ya filtrada por este repo. / Stack read from the code, no AI. Each block opens its own window, already filtered to this repo.;
  - roles `rp.role.language` Lenguaje / Language, `rp.role.framework` Framework / Framework, `rp.role.build` Build / Build, `rp.role.data` Datos / Data, `rp.role.container` Contenedor / Container, `rp.role.ci` CI / CI;
  - `rp.sonar` SonarQube / SonarQube; `rp.coverage` cobertura / coverage; `rp.delta` {sign}{n} puntos en {k} lecturas / {sign}{n} points over {k} readings; `rp.trendFew` Una sola lectura: la tendencia aparece con la siguiente. / One reading so far: the trend shows from the next one.; `rp.trendLabel` Cobertura de las últimas {k} lecturas, de {from} % a {to} % / Coverage over the last {k} readings, from {from} % to {to} %; `rp.estimated` Estimado / Estimated; `rp.noHealth` Aún no hay foto de salud. / No health snapshot yet.; `rp.noHealthGo` Hacerla en Calidad / Build it in Quality; `rp.toSonar` Calidad › SonarQube → / Quality › SonarQube →;
  - `rp.activity` Actividad / Activity; `rp.activitySum` {n} commits en 12 semanas · {p} personas / {n} commits in 12 weeks · {p} people; `rp.activityLabel` Commits por semana en las últimas 12 semanas: {n} en total, como mucho {max} en una semana / Commits per week over the last 12 weeks: {n} in all, at most {max} in one week; `rp.last` Último: «{subject}» · {author} · {ago}. Leído del historial de git, sin IA. / Latest: “{subject}” · {author} · {ago}. Read from the git history, no AI.; `rp.noGit` Sin historial de git que leer. / No git history to read.;
  - `rp.libs` Librerías / Libraries; `rp.libsVulns` {n} vulnerabilidades / {n} vulnerabilities; `rp.libsClean` Sin vulnerabilidades / No vulnerabilities; `rp.libsOf` De {n} librerías / Out of {n} libraries; `rp.libsNewer` {n} con versión nueva / {n} with a newer version; `rp.libsNever` Aún no se han buscado vulnerabilidades. / Vulnerabilities not looked for yet.; `rp.libsLabel` Vulnerabilidades por gravedad: {list} / Vulnerabilities by severity: {list}; `rp.toLibs` Calidad › Librerías → / Quality › Libraries →;
  - `rp.docs` Documentación / Documentation; `rp.docsPages` páginas del repo / pages about this repo; `rp.fresh` al día / up to date; `rp.suspect` por revisar / to check; `rp.stale` desactualizadas / out of date; `rp.docsLabel` {n} páginas: {list} / {n} pages: {list}; `rp.wiki` Wiki · {n} páginas → / Wiki · {n} pages →; `rp.wikiNone` Wiki sin generar → / Wiki not generated →; `rp.review` Revisar {n} ↗ / Review {n} ↗; `rp.noDocs` Ninguna página cita este repo todavía. / No page cites this repo yet.;
  - `rp.arch` Arquitectura / Architecture; `rp.me` este repo / this repo; `rp.nodes` {n} nodos en el grafo de código / {n} nodes in the code graph; `rp.viewC4` Ver el C4 ↗ / View the C4 ↗; `rp.viewGraph` Ver el grafo ↗ / View the graph ↗; `rp.noC4` Este repo aún no está en el modelo C4. / This repo is not in the C4 model yet.; `rp.c4Label` {repo}: lo llaman {callers}; llama a {callees} / {repo}: called by {callers}; calls {callees};
  - `rp.work` Trabajo / Work; `rp.cards` {n} tarjetas tocan este repo / {n} cards touch this repo; `rp.todo` Por hacer / To do; `rp.doing` Haciendo / Doing; `rp.inReview` Revisión / Review; `rp.done` Hecho / Done; `rp.blocked` Bloqueadas / Blocked; `rp.workLabel` Tarjetas por columna: {list} / Cards by column: {list}; `rp.toBoard` Tablero → / Board →; `rp.toDecisions` Docs › Decisiones → / Docs › Decisions →; `rp.noWork` Ninguna tarjeta ni ADR nombra este repo. / No card or ADR names this repo.;
  - `rp.unknown` Este repo no es del proyecto. / This repo is not part of the project.; `rp.failed` No he podido leer el repo / I could not read the repo.
- [ ] **Step 4: Run** the tests of Step 2 and `npm test` — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): a repo's page — a bento of tiles, each opening its window filtered to the repo`.

---

### Task 11: The repo cards on Flow › Summary

**Files:**
- Create: `src/sections/RepoCards.jsx`, `src/RepoCards.test.jsx`
- Modify: `src/repo.js` (new `repoCard`), `src/repo.test.js`, `src/sections/Summary.jsx` (draws `RepoCards` under the stats, `data-tour="summary-repos"`), `src/tour.js` (the `flow` tour gains a `summary-repos` step), `src/i18n.js`
- Test: `src/Summary.test.jsx`, `src/tour.test.js`

**Interfaces:**
- Consumes: `GET app/repos` (Task 3), `repoHref` (Task 5), `Icon` (Task 9).
- Produces: `repoCard(row, t, now) -> { name, href, state, sonar: { kind: 'sonar' | 'estimated' | 'none', text, gateState }, libs: { text, tone }, wiki: string, docs: { text, tone } }`; `RepoCardsView({ data, now })` (presentational) and default `RepoCards({ srv })` (reads `GET app/repos`, again when a job ends, as Summary does).

- [ ] **Step 1: Write the failing tests.**
  - `repo.test.js` `repoCard`: sonar-backed `{gate: 'OK', coverage: 78}` → `sonar.text` holds the gate word and `78 %`, `gateState: 'ok'`; estimated with a report `64` → `kind: 'estimated'`, `text` `64 % · informe`; estimated with no coverage → `sin cobertura`; `sonar: null` → `kind: 'none'`, text `—`; libs `{vulns: {high: 1, medium: 1}, scanned: true}` → `2 vulnerabilidades`, tone `bad`; `{vulns: {}, scanned: true}` → `Sin vulnerabilidades`; `scanned: false` → `Sin revisar`; wiki `{pages: 42, at}` → `42 páginas · hace …`; `{pages: 0}` → `Sin generar`; `unit: 'doing'` → `Generándose…`; docs `{stale: 3}` → `3 desactualizadas` tone `warn`; `{total: 4, stale: 0, suspect: 0}` → `Al día`; `{total: 0}` → `Sin páginas`; `cloned: false` → state word `Sin estado` (Review Focus 1).
  - `RepoCards.test.jsx`: `RepoCardsView` lists one `a` per repo to `#/flow/repo/<name>`, each with its state word, the language icon and stack text, the four facts and `Abrir repo →`; the header says `3 repos · salud {ago}` and links `Ver la salud completa` to `#/quality`; with `at: null` it says `rp.noHealth` beside that link.
  - `RepoCards` with a never-resolving `srv` renders a skeleton.
  - `tour.test.js` keeps passing with the new step (both languages).
- [ ] **Step 2: Run** `npx vitest run src/repo.test.js src/RepoCards.test.jsx src/Summary.test.jsx src/tour.test.js` — expected: FAIL.
- [ ] **Step 3: Implement.** Cards as the mockup's "Flujo › Resumen" (`auto-fill, minmax(300px, 1fr)` grid; each card a link with a `dl` of facts). i18n (es / en): `rc.title` Repos / Repos; `rc.count` {n} repos · salud {ago} / {n} repos · health {ago}; `rc.health` Ver la salud completa / See all of Health; `rc.sonar` SonarQube / SonarQube; `rc.libs` Librerías / Libraries; `rc.wiki` Wiki / Wiki; `rc.docs` Docs / Docs; `rc.report` informe / report; `rc.noCoverage` sin cobertura / no coverage; `rc.vulns` {n} vulnerabilidades / {n} vulnerabilities; `rc.vuln` 1 vulnerabilidad / 1 vulnerability; `rc.clean` Sin vulnerabilidades / No vulnerabilities; `rc.unscanned` Sin revisar / Not checked; `rc.wikiPages` {n} páginas · {ago} / {n} pages · {ago}; `rc.wikiNone` Sin generar / Not generated; `rc.wikiRunning` Generándose… / Generating…; `rc.stale` {n} desactualizadas / {n} out of date; `rc.stale1` 1 desactualizada / 1 out of date; `rc.fresh` Al día / Up to date; `rc.noPages` Sin páginas / No pages; `rc.open` Abrir repo → / Open repo →; `rc.failed` No he podido leer los repos / I could not read the repos; tour `tour.flow.N` for `summary-repos`: Tus repos / Your repos — Cada tarjeta resume un repo; ábrela para ver su página. / Each card sums up one repo; open it for its page.
- [ ] **Step 4: Run** the tests of Step 2 and `npm test` — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): repo cards on Flow › Summary; Health's repos open the repo page`.

---

### Task 12: Phase 1 leftovers — Add menu arrow keys, Plugins empty state

**Files:**
- Modify: `src/board.js` (new `menuStep`), `src/sections/Board.jsx` (`BoardView`'s menu handles the keys), `src/sections/SettingsTeam.jsx` (`Plugins` empty state), `src/i18n.js`
- Test: `src/board.test.js`, `src/SettingsTeam.test.jsx`

**Interfaces:**
- Produces: `menuStep(index: number, key: string, count: number) -> number` — `ArrowDown` next (wraps), `ArrowUp` previous (wraps), `Home` 0, `End` count − 1, any other key the same index; `count` 0 → 0.

- [ ] **Step 1: Write the failing tests.** `board.test.js`: `menuStep(0, 'ArrowDown', 3)` → `1`; `menuStep(2, 'ArrowDown', 3)` → `0`; `menuStep(0, 'ArrowUp', 3)` → `2`; `menuStep(1, 'Home', 3)` → `0`; `menuStep(0, 'End', 3)` → `2`; `menuStep(1, 'x', 3)` → `1`; `menuStep(0, 'ArrowDown', 0)` → `0`. `SettingsTeam.test.jsx`: `Plugins` with an empty list renders `pl.empty`'s text.
- [ ] **Step 2: Run** `npx vitest run src/board.test.js src/SettingsTeam.test.jsx` — expected: FAIL.
- [ ] **Step 3: Implement.** The menu's keydown moves the focus among its `menuitem`s with `menuStep` (and `preventDefault` on those keys). i18n (es / en): `pl.empty` Aún no hay plugins: los que añadas aquí, o los que traiga el repo del equipo, aparecerán en esta lista. / No plugins yet: the ones you add here, or the ones the team's repo brings, will show in this list.
- [ ] **Step 4: Run** the tests and `npm test` — expected: PASS.
- [ ] **Step 5: Commit** `fix(app): arrow keys in the Board's Add menu; the Plugins tab says when it is empty`.

---

### Task 13: User docs, version, builds, end to end

**Files:**
- Modify: `.camarones/templates/docs/guides/app.md` + `.camarones/templates/docs/i18n/es/guides/app.md` (Flow: the repo cards and `### A repo's page`; Quality: `### SonarQube` with `go:quality/sonar`, the estimate; Board, Libraries, Wikis and Decisions: `?repo=`), `guides/internals.md` + es twin (`GET /api/app/repo`, `GET /api/app/repos`, the repo facts cache, `.cache/health/history.jsonl`), `README.md` (desktop app section, badge 4.91.0), `.camarones/lib/tutorial.py` + regenerated `.camarones/TUTORIAL.md` (only if they describe these screens), `.camarones/lib/common.py` (`"kit": "4.91.0"`)
- Rebuild: `.camarones/desktop/renderer-build/`, `.camarones/portal/app-build/`

- [ ] **Step 1: Write the guide sections** (en first, then es with the same markers). Run `uv run pytest tests/test_guide.py -q` and `npx vitest run src/Tour.test.jsx src/Guide.test.jsx` — expected: PASS.
- [ ] **Step 2: README, tutorial, version.** Update `README.md`; regenerate `TUTORIAL.md` from `.camarones/` with `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"` if `tutorial.py` changed; set `VERSIONS["kit"] = "4.91.0"`.
- [ ] **Step 3: Rebuild** `cd .camarones/desktop/renderer && npm ci && npm run build` and `cd .camarones/portal/app && npm ci && npm run build`.
- [ ] **Step 4: Run the whole suite** — `uv run pytest -n auto -q`, renderer `npm test`, portal `npm test` (it holds the kit's tests), `cd .camarones/desktop && node --test "test/*.test.cjs"`. Expected: all green; report the counts.
- [ ] **Step 5: Commit** `feat(app): repo pages, repo cards and Quality › SonarQube (kit 4.91.0)` with the docs, the version and both builds; the body says the guide templates reach only new projects.
- [ ] **Step 6: End to end in an isolated sandbox** (memory note "electron-app-automation": scratch `HOME`, `scripts/sandbox.py --dir <scratch>/sb reset` then `cli init`, `cli health --refresh`, Electron with `--user-data-dir` and `--remote-debugging-port=0`, a small CDP client). Open Flow › Summary and check the cards; open a repo card; from its page follow each tile link and check the window it lands on is filtered: SonarQube (only that row), Libraries (repo facet set), Docs › Wikis (that block first), Board (chip, only its cards; add a card with `x-repos` first), Docs › Decisions (chip; add an ADR naming the repo first). Check `#/quality/sonar` shows an "Estimated" row with its panel. Screenshot Summary, the repo page (light and dark) and the SonarQube tab for the report. Fix anything found (with a test) and amend nothing: new commits.

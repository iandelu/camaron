# The desktop app's redesign: four places, one window per thing — design

The user's request (2026-11-18), in short: Quality should have a window to see SonarQube per repo, and a preview where a
repo has none; a window like Libraries for the secrets gitleaks finds, which also says whether gitleaks is installed.
Team goes away: the team's repo lives in Docs; skills and plugins live in settings. Interviews are seen, answered and
processed in Docs, not in a section of their own. Decisions live in Docs too. Plan and Summary are grouped in a "Flow"
section. The board's "add story" sends you to the portal's new story screen. The Summary gets a dashboard with each
repo; each repo has a page that shows its Sonar, wiki, docs, vulnerabilities and more — without repeating windows: it
sends you to the real window with the filter set.

Mockups the user reviewed and commented on (private canvas, 14 screens): https://claude.ai/artifact/3zfJ385zLVtFvX44pJdZkK.
Where this document and the canvas disagree, this document wins; the canvas shows look and layout.

## 1. Intent

Today the app has 8 project sections and 3 machine sections. The same facts sit in several of them (a repo's Sonar in
Quality, its wiki in Docs, its libraries in Quality › Libraries, its cards on the Board), nothing shows one repo as a
whole, the secret scan is a row that prints file names, and an interview is answered in the portal but run from the app.

This redesign makes the app **four project places plus settings**, where **every fact has exactly one window** and every
other screen that mentions it **links to that window with the filter already set** (`?repo=<name>`).

**Done when:** a person can, without the portal and without the CLI,

1. see every repo of the project at a glance (Flow › Summary) and open one repo's page;
2. from that page reach its SonarQube figures, libraries, secrets, wiki, docs, architecture, cards and decisions, each in
   its own existing window, already filtered to that repo;
3. see SonarQube's figures for every repo, and a clearly marked estimate for a repo without SonarQube;
4. see every secret gitleaks finds in the docs, the wikis, the code repos and their git history, never its value, and
   install gitleaks from the same screen when it is missing;
5. read, answer and process the team questionnaire inside Docs;
6. update a library on a new branch, or — only when the update has no impact — as one commit on main after two
   confirmations;
7. keep using every old address, bookmark, guide link and `g` shortcut, which land on the new place.

**Anti-goals — a failure even if it works:**

- a second window that shows the same thing as another (a summary tile is fine; a second editable list is not);
- an old address, a guide's `go:`/`tour:` marker or a `g` letter that lands nowhere;
- a 3.x/4.x project that needs a manual step;
- a secret's value written to disk, a report, a log, the screen or the network;
- code or secrets leaving the machine for any of this (gitleaks, the stack, activity and the estimate run locally);
- a number on these screens that needs an AI model to exist (stack, activity, impact and the Sonar estimate are static);
- any push, or a commit on main without the two confirmations, or a commit on main for an update with possible impact;
- a kit file written into a service repo (the secrets allowlist and every cache live in cam-docs or `~/.camarones`).

**Non-goals:** redesigning the portal (only its `#/stories` is linked to); changing the Plan screen beyond its address;
new AI features; changing CLI zones or command names.

### 1.1 Decisions taken with the user (2026-11-18)

| Question | Decision |
|---|---|
| Sonar for a repo without SonarQube | **Home-made estimate** (option B): what the kit knows without a server, shaped like the Sonar row, marked "Estimated", with "Connect SonarQube" |
| What gitleaks scans | **Docs + wikis + code repos + their full git history**; each finding says "in the file now" or "only in history" |
| Navigation | Project: **Flow** (Summary, Plan), **Board**, **Quality** (Health, SonarQube, Libraries, Secrets), **Docs** (Read, Wikis, Decisions, Interviews). App: **Settings** (General, Tokens, Skills, Plugins, Trust, Kit), Guide, Kit dev |
| Team | Removed. Its repo-and-share card becomes a status strip on every Docs tab; Skills, Plugins and Trust go to Settings |
| Board › Add | A menu: Story opens the portal's Historias (`#/stories`) in the browser; Task and Bug keep the in-app form |
| Repo page | A bento dashboard: stack with SVG icons, tiles with charts (coverage trend, weekly commits, vulnerabilities by severity, docs freshness, mini C4, cards by column), soft entry animations; every tile links to its real window with `?repo=` |
| Library update | Two ways: **on a new branch** (always) or **one independent commit on main**, offered only when the update has no impact, after **two confirmations**; never pushed |
| What "no impact" means | A **patch jump whose repo tests pass** with the update applied (checked in a temporary worktree); anything else, or no way to run the tests, is not "no impact" |
| How to build | In four phases, each shippable on its own (the user moved straight to implementation on that plan) |

## 2. Navigation

### 2.1 Places and addresses

| Place | Address | Was |
|---|---|---|
| Flow › Summary | `#/flow` | `#/summary` |
| Flow › Plan | `#/flow/plan` (`?term=<id>` kept) | `#/plan`, `#/plan?term=<id>` |
| Flow › a repo | `#/flow/repo/<name>` | — (the desktop linked to the portal's `#/health/<repo>`) |
| Board | `#/board` (`?repo=<name>`) | same |
| Quality › Health | `#/quality` | same |
| Quality › SonarQube | `#/quality/sonar` (`?repo=`) | — |
| Quality › Libraries | `#/quality/libs` (`?repo=`) | `#/libs` (already moved in 4.89) |
| Quality › Secrets | `#/quality/secrets` (`?repo=`) | — |
| Docs › Read | `#/docs` | same |
| Docs › Wikis | `#/docs/wikis` (`?repo=`) | part of `#/docs` |
| Docs › Decisions | `#/docs/decisions[/<id>\|/new\|/candidates]` (`?repo=`) | `#/decisions[/…]` |
| Docs › Interviews | `#/docs/interviews` | `#/interviews` |
| Settings › General | `#/settings` | `#/machine` |
| Settings › Tokens | `#/settings/tokens` (`?host=&kind=`) | `#/machine?host=&kind=` |
| Settings › Skills · Plugins · Trust | `#/settings/skills`, `/plugins`, `/trust` | `#/team` |
| Settings › Kit | `#/settings/kit` | part of `#/machine` |
| Guide, Kit dev, Start | unchanged | |

- `nav.js` keeps `PROJECT = ['flow', 'board', 'quality', 'docs']` and `MACHINE = ['settings', 'guide', 'kitdev']`.
- **Old addresses** go through `movedRoute()` (extended from today's `#/libs` case) and keep what follows them:
  `#/summary`→`#/flow`, `#/plan…`→`#/flow/plan…`, `#/decisions…`→`#/docs/decisions…`, `#/interviews`→`#/docs/interviews`,
  `#/team`→`#/docs`, `#/machine?host=&kind=`→`#/settings/tokens?host=&kind=`, `#/machine`→`#/settings`. Every in-app
  link listed in §10.2 is changed to the new address too; the redirect is for bookmarks, guides and old builds.
- **Views vs commands.** Today the second segment of `#/quality/<x>` is also a catalog command the palette opens in the
  folded "All commands" list, and only `libs` is a view. Each tabbed place keeps a fixed list of view names (`sonar`,
  `libs`, `secrets`; `wikis`, `decisions`, `interviews`; `tokens`, `skills`, `plugins`, `trust`, `kit`; `plan`, `repo`);
  any other second segment is still a command. A test fails if a catalog command shares a name with a view of the place
  whose fold lists it.
- **`g` shortcuts**: `g f` Flow, `g b` Board, `g q` Quality, `g d` Docs, `g m` Settings, `g h` Guide, `g k` Kit dev. The
  old letters stay as aliases to their new home: `s`→Flow, `p`→Flow › Plan, `a`→Docs › Decisions, `i`→Docs › Interviews,
  `t`→Docs. The palette lists each place and each of its tabs (as it lists Libraries today).
- **Breadcrumbs**: project / place / tab (and the ADR's crumb inside Decisions, as today).
- The sidebar shows the four places and, under "This app", Settings and Guide. The tabs of a place use today's
  `dk-guide-tabs` pattern (`QualityViews`), generalised into one `PlaceTabs` component.

### 2.2 Tours and guides

`tour.js`'s `app` tour follows the new sidebar; the per-section tours are re-targeted (`summary`, `plan` under Flow;
`interviews` under Docs; `team` removed and its steps split between Docs and Settings; `machine` becomes `settings`).
Their strings are keyed by index (`tour.app.N`), so they are rewritten in both languages, not shifted. The guides'
`## <Section>` headings, `go:` and `tour:` markers follow the new places (`app.md`, `using.md`, `internals.md`, en + es).

## 3. Flow

### 3.1 Summary (`#/flow`)

Today's Summary (next step, first-run notice, tour offer, stats) plus a **repo dashboard** under it: one card per repo
with its state word (Good / Attention / Bad, never colour alone), SonarQube (gate and coverage, or "Estimated" and the
coverage from a report), library vulnerabilities, secrets ("in the file" / "only in history"), wiki state and stale pages.
Each card opens `#/flow/repo/<name>`. "See all of Health" links to `#/quality`.

The card's state is `health.areas()`'s per-repo state (`_repo_state`). Secrets are folded into that one rule in
`health.py` (the snapshot reads the last secrets report; a secret in a tracked file makes the repo Bad, one only in
history makes it Attention), so Health, the portal, `camaron health` and these cards always agree.

### 3.2 A repo's page (`#/flow/repo/<name>`)

A bento grid (12 columns, one column under ~1000 px) of tiles. **The page has no window of its own**: each tile is a
summary and a link.

| Tile | Shows | Opens |
|---|---|---|
| Header | name, state, branch, last commit; the **stack** as pills with stroke SVG icons (language, framework, build, data, container, CI) | — |
| SonarQube | coverage as a hero number, its trend over the last 8 health builds (sparkline), gate, bugs, code vulnerabilities, debt; or the estimate | `#/quality/sonar?repo=` |
| Activity | commits per week for 12 weeks (bars), people, the last commit | — (read from git) |
| Libraries | vulnerabilities by severity (bars), count with a newer version | `#/quality/libs?repo=` |
| Secrets | count in a file / only in history, the first location, last scan | `#/quality/secrets?repo=` |
| Documentation | the repo's pages, up to date vs stale (segmented bar); wiki pages | `#/docs/wikis?repo=`; portal review ↗ |
| Architecture | a mini C4: what calls the repo's container and what it calls; code-graph nodes | portal C4 ↗, graph ↗ |
| Work | the repo's cards by column (segmented bar), the ADRs that name it | `#/board?repo=`, `#/docs/decisions?repo=` |

**Charts** follow the dataviz rules: thin marks, 4 px rounded data ends, 2 px gaps between segments, hairline axes, one
hue for a single series (`--series`), status colours only where the colour means state and always with a word, an
ordinal violet ramp for the board's columns (validated: light `#b3a0fb #9475f5 #7039e6 #5126b0`, dark
`#5b3aa8 #7c5cd6 #a48bf0 #d4c8ff`), a tooltip on every bar and point, an `aria-label` with the numbers on each chart.
A chart with too little data says so instead of drawing (one health build: the number, no sparkline).

**Motion**: tiles rise in staggered, bars grow from their baseline, segments grow from the left; transform and opacity
only, `--ease-out-soft`; nothing moves under `prefers-reduced-motion`.

**Icons**: generic stroke icons, never a product's logo; the label names the tool. Same set for the Summary's cards.

The page replaces the desktop's link to the portal's `#/health/<repo>` (`HealthBoard`'s `repoHref`). The portal keeps its
own read-only page.

### 3.3 Plan (`#/flow/plan`)

Unchanged; only its address and `termOf()`'s route move. Every session opened from the app lands on
`#/flow/plan?term=<id>`.

## 4. Board (`#/board`)

- **Add ▾** opens a menu: *Story* opens the portal's `#/stories` (a new story) in the system browser through
  `app.openExternal(portalUrl(origin, '#/stories'))`; *Task* and *Bug* open today's in-app form. "Add a task" inside a
  story stays in the app.
- **`?repo=<name>`** filters the cards by `card.repos` (frontmatter `x-repos`), the same rule as the portal's
  `applyFilters` in `portal/app/src/kanban.js`; that pure function moves to `@camaron/ui/kanban.js` and both use it. The
  filter shows as a removable chip.

## 5. Quality

Tabs: Health · SonarQube · Libraries · Secrets.

### 5.1 Health (`#/quality`)

`HealthBoard` as today, except that the `libs` and `secrets` rows link to their tabs instead of opening a control
(`BOARD_ACTIONS` loses both), and `repoHref` points to `#/flow/repo/<name>`. The other rows (doctor, drift, fresh, evals,
context, blocks, A/B, method hooks) keep their inline controls.

### 5.2 SonarQube (`#/quality/sonar`)

A table with one row per repo: source (SonarQube / Estimated), gate, coverage, bugs, code vulnerabilities, debt, and
"Open in SonarQube ↗" (the snapshot's link, `safeUrl`). Filters: repo, source. "Read again" rebuilds the health snapshot.

An **Estimated** row opens a panel with what the kit knows without a server: coverage from the repo's own report
(`coverage.source == "report"`), library vulnerabilities (inventory), secrets (§5.4), stale pages (`fresh`); what cannot be
estimated (bugs, smells, duplication, debt); and **Connect SonarQube** → `#/settings/tokens?host=&kind=sonarqube`
(`sonarConnectHash`, re-pointed). The server's figure always wins when it exists (today's rule in `health.py`).

All figures come from the existing snapshot (`sonar.server` with gate and `METRICS`); no new Sonar call.

### 5.3 Libraries (`#/quality/libs`)

The shared `LibrariesBoard`, with `?repo=` passed to its existing `repo` prop, and a new **Impact** column and update
flow:

- **Jump** column (static): patch (same major.minor), minor, major, or not semver.
- **Impact** (decided with the user, no AI): `none` only when the jump is a **patch and the repo's own tests pass with
  the update applied**; `possible` when the jump is not a patch or the tests fail; `unknown` (treated as possible) when
  the repo has no known test command or the tests cannot run on this machine. Whether the code imports the library
  (code graph) is shown as a reason when known, never as the gate.
- **Update…** opens a panel (How › Check › Confirm › Done) with two choices: *On a new branch* — today's `bump` (branch,
  no commit), always available; *One independent commit on main* — offered for a patch jump, and enabled only after
  **Check** has run the tests and they passed. Check is a job with its output (it takes minutes); a failure shows the
  test output and leaves only the branch.
- **Main** asks twice: first a summary (repo, file, one line, the message `chore(deps): <name> <from> → <to>`, "tests
  passed N min ago"), then the person types `main`. The commit stays local; nothing is pushed.
- The canvas drew the impact as a static column; this rule replaces it.
- The portal's Libraries keeps showing the command to copy.

### 5.4 Secrets (`#/quality/secrets`)

- **The tool**: gitleaks' pinned version and whether it is installed (`binaries.bin_path`, `VERSIONS["gitleaks"]`); when it
  is missing, **Install gitleaks** runs the pinned, checksummed install (`binaries.ensure`), and an empty state says the
  first scan starts by itself after it.
- **Scan now**, the last scan's time, scope and duration.
- **Findings**: where (in the file now / only in history), repo or doc, `file:line`, rule, commit, date; filters by repo,
  where and rule; each finding opens "what to do" (rotate it — deleting it from the file is not enough; move it to an
  environment variable or the secret manager; or mark a false positive) and "Open the file". The value is never shown.
- **False positives** are kept in cam-docs (§8.1), never in the service repo.

## 6. Docs

Tabs: Read · Wikis · Decisions · Interviews. A **team strip** sits above the tabs on every tab: sync state (up to date /
changes to bring / never shared), last share, **Share now**, and the team repo's URL in a fold with Save (today's Team
`Repo` card, unchanged behaviour: `GET sync`, `POST sync/share`, `remote`).

- **Read** (`#/docs`): the portal buttons (read, search), the review queue card, the C4 card (build, view), Ask, and the
  "All commands" fold that Team had (§10.1).
- **Wikis** (`#/docs/wikis`): today's wiki blocks; with `?repo=` the repo's block comes first and open, the others folded.
- **Decisions** (`#/docs/decisions…`): today's Decisions section unchanged inside Docs (`adr.js`'s `route()` reads the
  new prefix); `?repo=` filters the list by `repos`.
- **Interviews** (`#/docs/interviews`): the mode (questionnaire / live) and how to change it; the round (questions,
  respondents, conflicts); a four-step strip — Answer (here, or export the form), Bring answers (import files), Close the
  round, Process (the agent units, which turn answers into pages and flag conflicts instead of choosing); and a
  **question list + question panel**: the team's answers to the question, a conflict note, **Your answer** and "I don't
  know, skip". Answers go through the same `POST /api/interview/answer` the portal uses (`questionnaire.answer`), as the
  person `app/info` names.

## 7. Settings (`#/settings`)

Tabs: General · Tokens · Skills · Plugins · Trust · Kit.

- **General**: today's Machine cards for the guide, setup, agent sessions' language/models/where they open, and this
  project's repos and plan.
- **Tokens**: today's Tokens card; with `?host=&kind=` it is prefilled and a notice says where you came from.
- **Skills**, **Plugins**, **Trust**: today's Team cards, unchanged behaviour. A pack added in Skills arrives in Trust;
  the Trust tab shows a count of what waits for approval.
- **Kit**: the kit itself (version, update) and, apart, uninstall (previewed first, as today).

## 8. Backend

Everything here runs locally, is static, has `--json`, and is reached by the app through the catalog
(`POST app/cmd`) or a read-only `GET` with the app token.

### 8.1 Secrets report

A new command **`camaron secrets`** (zone `check`): `scan [--no-history] [--json]`, `list [--json]`,
`ignore <id> [--undo]`. `check --secrets` keeps its behaviour (docs + wikis, fails on a finding) for CI and checkpoints.

- `scan` runs gitleaks through the process helpers on: `docs/` and each repo wiki (as today, `gitleaks dir`), and each
  cloned code repo through git only: its **tracked files at HEAD** and, unless `--no-history`, its full history
  (`gitleaks git`). Untracked and git-ignored files (a local `.env`, `node_modules/`, `target/`) are not scanned: they
  have not leaked into the repo.
- Each finding is normalised to `{fingerprint, where: "file" | "history", scope: "docs" | "wiki" | "repo", repo, file,
  line, rule, commit, date}`, where `fingerprint` is gitleaks' own. `where` is `file` when a finding with the same repo +
  file + rule is in the tracked files at HEAD (or in the docs/wikis tree), `history` when it is only in older commits.
- **No value is kept.** gitleaks runs with `--redact`; no secret, and no hash of one, is computed, stored or shown.
- The report goes to cam-docs' git-ignored cache (`.cache/secrets/report.json`, `{at, duration, scope, tool, findings}`).
- **False positives**: `ignore <fingerprint>` adds the finding's gitleaks fingerprints (its "file" form and every
  "history" form with the same repo + file + rule) to `.gitleaksignore` at cam-docs' root — gitleaks' own format, the
  same on every machine, shared through git and reviewable in a commit. Scans of code repos point gitleaks at that file
  (its ignore-path flag); nothing is written into a service repo. A fingerprint holds the line, so a false positive that
  moves comes back once and is marked again.
- The same `.gitleaksignore` applies to the gates that scan cam-docs (`check --secrets`, checkpoint commits through
  `staged_secrets`, `export` through `assert_no_secrets`), so a marked false positive stops blocking sharing and
  publishing; silencing a gate is a commit anyone can see.
- `GET app/secrets` returns the last report plus `{installed, version, pinned}`.

### 8.2 A repo's dashboard

`GET app/repo?name=<repo>` (app token) returns what §3.2 draws, composed from what exists plus three new static reads:

- **stack**: `quickarch.stack()` (language · framework) plus `radar.scan()`'s tools for build, deploy (Dockerfile) and CI,
  cached per repo HEAD in cam-docs' `.cache/` (radar runs today only in the first-look job);
- **activity**: commits per ISO week for the last 12 weeks, people, last commit (`git log --since … --format=%aN%x09%at%x09%s`),
  a new pure function beside `history.commits()`, cached per HEAD;
- **coverage trend**: each health build appends `{at, repos: {name: coverage}}` to `.cache/health/history.jsonl`
  (last 26 kept); the tile shows the last 8;
- and from what exists: the health row and state, inventory counts, the secrets report, `GET wikis`, `fresh`, the C4
  model's container for the repo and its relations, the board's cards with `x-repos` containing the repo, the ADRs
  whose `repos` contain it.

`GET app/repos` returns the same header-level summary for every repo (the Summary's cards).

### 8.3 Library update on main

`camaron bump` gains `--check` and `--commit`, and a pure `impact(jump, tests)` (§5.3):

- **The test command** comes from the repo's build tool, detected as the stack is (§8.2): Maven `mvn -q test` (or the
  wrapper), Gradle `./gradlew test`, npm/pnpm/yarn `test` script, uv/poetry `pytest`, Go `go test ./...`. No known
  command → impact `unknown`.
- `bump <lib> <version> --repo <r> --check [--json]` never touches the person's working copy: it makes a temporary git
  worktree of the repo at its default branch's HEAD (in `~/.camarones` or the OS temp dir), applies the update there with
  the same code `bump` uses, runs the tests, and records `{lib, from, to, head, passed, at, output_tail}` in cam-docs'
  cache. The worktree is removed afterwards, also on failure or interruption.
- `bump … --commit --yes` refuses unless: the jump is a patch, a passing check exists for the same lib, version and the
  default branch's current HEAD, and the clone is clean and on its default branch. It applies the change in place and
  makes one commit `chore(deps): <name> <from> → <to>` with only the manifest/lockfile, no `Co-Authored-By` trailer. It
  never pushes. If the default branch moved since the check, it refuses and asks for a new check.
- Without `--check`/`--commit`, `bump` is unchanged (branch `camaron/bump-<slug>-<version>`, no commit).
- `bump --plan --json` reports the jump, the test command and the last check, which the panel shows.

## 9. Compatibility and versions

- Old addresses, `g` letters and guide markers keep working (§2). CLI zones and command names do not change; only the
  desktop's mapping of zones to places does (§10.1).
- Nothing in a project's files changes shape. New files: cam-docs' `.cache/secrets/`, `.cache/health/history.jsonl`,
  stack/activity caches (git-ignored), `docs/.work/secrets-ignore.json` (created on the first ignore).
- `VERSIONS["kit"]` bumps once per phase (4.90.0, 4.91.0, …). README, the guides (en + es), the tour and the tutorial
  (`lib/tutorial.py` → `TUTORIAL.md`, `templates/docs/guides/tutorial.md` + es) change in the same commit as what they
  describe; templates reach only new projects, which each commit says when it matters.
- Every new Python path uses `pathlib`, `encoding="utf-8"`, and the process helpers; gitleaks' binary name follows the
  existing `.exe` handling on Windows.

## 10. The code

### 10.1 Desktop renderer

- `nav.js`: places, view names per place, `sectionOf`, `placeOf`, `movedRoute`, `tokenPrefill` (new route), `termOf`
  (new route), and a `repoOf(hash)` for `?repo=`. `palette.js`: `GO` and aliases. `tour.js`, `i18n.js` (es + en).
- `catalog.js`: `ZONES` becomes `{ flow: ['generate'], quality: ['check', 'analyze'], docs: ['team', 'interviews'],
  settings: ['machine'] }`; `PANELS` gains Settings' panel commands (`skills`, `plugins`, `trust`) and Docs' (`remote`,
  `share`, `interview`). `hooks` stays a panel of Quality (its Health row, as in 4.89).
- New sections: `Flow.jsx` (tabs; Summary, Plan, Repo), `Settings.jsx` (tabs). New views: `RepoPage.jsx`,
  `SonarView.jsx`, `SecretsView.jsx`, `InterviewsView.jsx` (replacing `Interviews.jsx`), `TeamStrip.jsx`. Moved:
  `Team.jsx`'s cards into Settings and the strip; `Machine.jsx`'s cards into Settings' tabs; `Interviews.jsx`,
  `Decisions.jsx` under Docs. Pure helpers in `.js` files beside them, tested.
- Links to change (§2.1): `parts.jsx`, `plan.js`, `App.jsx` (brand, crumbs, rail), `summary.js`, `Summary.jsx`,
  `Quality.jsx`, `Canvas.jsx`, `Plan.jsx`, `Start.jsx`, `Machine.jsx`, `Team.jsx`, `Decisions.jsx`, `adr/*.jsx`.
- `renderer-build/` rebuilt and committed (CI checks it matches its source).

### 10.2 Shared UI and portal

- `@camaron/ui/kanban.js` takes the portal's `applyFilters`; the portal imports it from there.
- A small chart kit in `@camaron/ui` (`Sparkline`, `Bars`, `SegBar`, `HBars`) with the rules of §3.2, used by the repo
  page and the Summary cards.
- `portal/app-build/` rebuilt if the portal's source changes.

### 10.3 Python

`lib/secrets.py` (scan, normalise, report, ignore; pure parts separate), `commands/secrets.py`; `lib/bump.py`
(`impact`, `--commit`); `lib/history.py` (weekly activity); `lib/health.py` (history append); a repo-dashboard use case
in `lib/app/` composing §8.2, with its route in `interfaces/http/routes/`; the layer rules of AGENTS.md §5 apply.

## 11. Phases

| Phase | Ships | Done when |
|---|---|---|
| **1 · Navigation and moves** | §2, Flow (Summary as today, Plan), Board's Add menu, Quality's tabs with Health and Libraries, Docs with the team strip and its four tabs (Interviews as today's content), Settings with its six tabs, old addresses, tours, guides | every old address lands; no section lost a control; suite green on the three OS |
| **2 · Repos and SonarQube** | §3.1 cards, §3.2 page, §5.2, `?repo=` on Board, Libraries, Wikis, Decisions; §8.2; the chart kit | from a repo card, every tile reaches its filtered window |
| **3 · Secrets** | §5.4, §8.1 | a planted secret in a test repo's history shows as "only in history" with no value anywhere on disk |
| **4 · Interviews and library updates** | §6 Interviews panel and answering, §5.3 check and commit on main, §8.3 | a question answered in the app shows in the portal; in the sandbox a patch whose tests pass commits on main after two confirmations; a minor jump, a failing test or a moved main cannot |

## 12. Tests (written first)

- **Renderer (Vitest)**: `nav.test.js` (places, views, every old address → new, `?repo=`), `palette.test.js` (letters and
  aliases), `tour.test.js` / `Tour.test.jsx` (steps and markers name real places and targets), `catalog.test.js` (zones,
  panels, no command named like a view), one component test per new view with fixtures (empty, loading, failed, data),
  the chart helpers (scales, labels, too-little-data), `App.test.jsx` (shortcuts, crumbs).
- **Python (pytest, offline, `isolated_env`, `make_workspace`)**: secrets normalisation from recorded gitleaks JSON (file
  vs history, redaction, ignore list, missing gitleaks), and an end-to-end scan with the real binary under
  `needs("gitleaks")` on a temp repo with a secret only in history; `impact()` table; test-command detection per build
  tool; `bump --check` with a fake test command (pass, fail, missing) leaves the working copy untouched and removes its
  worktree; `bump --commit` refusals (not a patch, no passing check, main moved, dirty, not default branch), commit
  content, no trailer, no push; weekly activity from a temp repo; health history cap;
  `GET app/repo` / `GET app/repos` / `GET app/secrets` under the router's access rules (app token only).
- `tests/test_guide.py` keeps passing with the new markers; the sandbox (`scripts/sandbox.py`) is used for an end-to-end
  pass of each phase.

## 13. Left to the builder, and calls made without the user

**Calls I made (the user can overrule):** the address scheme of §2.1; `g m` for Settings and the old letters as aliases;
Docs' tabs are Read · Wikis · Decisions · Interviews (the C4 stays a card in Read, not a tab); the team strip on every Docs
tab; secrets labels "in the file now / only in history" (docs and wikis can hold secrets too); the Sonar table's
"code vulnerabilities" column is Sonar's only (library ones live in the estimate and in Libraries); a new `camaron secrets`
command instead of growing `check --secrets`; code repos scanned through git only (tracked files and history — what
has leaked), never untracked or git-ignored files; false positives in cam-docs' `.gitleaksignore`, with gitleaks'
fingerprints, also honoured by the gates; secrets folded into `health.py`'s one repo-state rule; `bump --commit`
on the repo's default branch, whatever its name, labelled "main" in the screen; Health keeps its other checks inline; the
Activity tile has no destination window.

**Settled by the code:** `questionnaire.answer` replaces a respondent's whole set, so the app sends the person's set
from `GET interview?who=`'s `mine` with the one answer changed.

**Left to the builder:** component boundaries inside each view; the gitleaks flags for the ignore file on this pinned
version; cache invalidation details; how the mini C4 is drawn (HTML boxes, not one SVG).

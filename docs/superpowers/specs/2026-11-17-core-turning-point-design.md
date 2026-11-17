# Camarón's core: a turning point — design

The user's request (2026-11-17), in short: "I lost the whole context of Camarón. I don't know where the refactor
stands. I will probably move to Java or another stack I control, because working in Python is impossible for me. Most
important: the core should make it easy to create documentation, keep it alive and make it useful to agents —
documentation agents don't use is pointless. Once installed, every Claude Code session (and every task) should
retrieve from the project docs, OpenWiki, the C4 and graphify. A code MR needs a parallel docs MR. And verification:
guardrails for versions, SonarQube, git hooks so commits carry no co-authors, preinstalled with the skills. Let's make
a turning point."

This document says where things stand, what the core is, what stops, and in which order the core gets finished. It
holds no code.

## 1. Where things stand (2026-11-17)

### 1.1 Size and loose ends

- `.camarones/lib`: 112 modules, ~33k lines of Python (measured 2026-11-12); ~34k lines of tests; the portal (React +
  Vite) and the desktop app (Electron) on top.
- Surfaces beyond the core: portal, desktop app, board (kanban with its git merge driver), ADRs, user stories
  (INVEST), pair canvas, plan cost, Libraries and Quality screens, terminals, autopilot and parallel runs, the TUI
  wizard, tutorial and guide, exports (PDF, Confluence, Notion), evals / A-B / KPIs, es + en everywhere.
- Kit repo: 4 open draft PRs (iandelu/camaron#13, #14, #15, #17), 27 local branches besides `main`, 18 worktrees under
  `.claude/worktrees/`. 5 branches are already merged (`cam/f5a-docs-split`, `fix/junction-pre312`,
  `fix/portal-modes-comment`, `refactor/f3-http`, `test/f4-uncovered-paths`); 13 are 790+ commits behind `main`.
- The workspace's checkout of the kit (`camaron-dev/camarones-documenter`) is on `fix/openwiki-validation`, 147
  commits behind `main`, with uncommitted `renderer-build` changes. Local `camaron check` reads sources from it, so it
  reports false "sources no longer exist" ERRORs; CI is the reference (cam-docs handoff, 2026-11-16).
- cam-docs plan: 24/26 units done; next is `confirm` (human review in the portal).

### 1.2 The hexagonal refactor

[Spec](2026-11-12-hexagonal-refactor-design.md). Goal: "easy to change" — layers `core / domain / ports / adapters /
app / interfaces`, old modules left as facades.

| Phase | State |
|---|---|
| F0 Guardrails (layer test, facade guard, CLI and HTTP snapshots) | merged |
| F1 `core/` | merged |
| F2 CLI (commands as classes, `main()` 6 lines, generated catalog) | merged |
| F3 HTTP (router, access level per route) | merged |
| F4 `env.py` (9 adapters, 8 use cases, `bootstrap`) | merged |
| F5a `docs.py` | merged |
| F5b `plan.py`, `adr.py`, `kanban/`, `harness/` | not started |
| F6 wizard, F7 close-out | not started |

Largest import cycle: 66 → 30 modules (36 modules inside cycles). Layer violations in the allowlist: 117 (129 before
F5a). Still over 600 lines: `adr`, `kanban.ops`, `pages`, `plan`, `schemas`, `stories`, `tutorial`, `wizard`.

### 1.3 The core, piece by piece

| Promise | What exists | What is missing |
|---|---|---|
| **Create docs** | Plan units, interviews, OpenWiki per repo, `arch-draft` C4, generated pages, portal | Nothing blocking |
| **Keep them alive** | `x-sources`, `check`, `fresh`, `pr fresh`, the post-edit hook (checks a page right after an edit), the Stop hook (reminds once), `docs.yml` CI active on cam-docs | Stop hook nags while a change is open (skill notes) |
| **Agents use them** | AGENTS.md text; MCP `search_docs`, `read_doc`, `ask`, `repo_graph`; likec4 and openwiki MCP; skill `cam-docs-lookup` | Retrieval happens only when the agent decides to. The SessionStart hook injects the *documentation plan* state, useless for a code task. Nothing retrieves from the prompt. Graphify graphs last built 2026-11-11. Hooks, MCP servers and skills are wired at the workspace root only; a session opened inside a service repo gets none of them |
| **Code PR + docs PR** | Skills `cam-task`, `cam-difficulty`, `cam-verify`, `cam-ship`, `cam-retro` | The [coding-workflow spec](2026-11-12-coding-workflow-design.md) chose a deterministic `camaron change` command and **rejected** skills-only ("evidence would be the agent's word"). Only the skills shipped; `camaron change` is 2 commits on `cam/wi-21-change-phases` (domain rules, worktree helpers) |
| **Guardrails** | Co-author `commit-msg` / `pre-push` hooks **in the kit repo only** (`scripts/githooks.py`); gitleaks inside `check` and as a manual `cam-ship` step; `inventory` (OSV), `latest`, `bump`; `sonar.py` reads measures and the quality gate | Nothing is installed in a project's repos. Versions, vulnerabilities and Sonar are **shown** (screens), never block. The per-repo CI snippet writes kit files into service repos, against "service repos never receive kit files" (handoff, 2026-11-16) |

**Do agents use the docs?** The usage counters committed in `cam-docs/docs/.work/usage/` (recording on):

| Period | Docs MCP calls | Detail |
|---|---|---|
| 2026-10-25 → 29 | 95 | `read_doc` 55, `search_docs` 20, `repo_graph` 17, `doc_status` 2, `ask` 1 |
| 2026-11-10 → 17 | 19 | `search_docs` 12, `read_doc` 3, `ask` 3, `doc_status` 1, `repo_graph` 0 |

In November at least 7 code changes went through `cam-task` (f5a-docs, q11-q12, page-write-lock, c4-external,
portal-i18n-lede, portal-i18n-titles, ci-fs-links). Agents reading cam-docs files with their own file tools are not
counted, so this is a floor, not the whole picture — but `repo_graph` was never called.

**What the workflow's own retros say.** 19 notes in `cam-docs/docs/.work/skill-notes/` since 2026-11-16:

| Friction | Notes |
|---|---|
| `check` and `pr fresh` read code from the workspace's shared checkout, which another session left on another branch → false ERRORs, scratch workspaces with junctions | 7 |
| `docs/.work/usage/*.json` is rewritten on every tool call, so the docs tree is never clean | 4 |
| No path for a code worktree when the person's checkout is busy | 2 |
| Difficulty weights, docs repo without a remote, `run.lock` during a docs merge, stacked PRs, a Windows-only baseline, Stop hook during a change | 6 |

### 1.4 Diagnosis

1. **The core is the smallest and least finished part.** Growth went to surfaces (portal, desktop, board, ADRs,
   stories, canvas, cost). The four promises the user cares about are partly done or done by text.
2. **Text does not make agents act.** Where the core exists it is a sentence in AGENTS.md or a skill the agent may
   follow. The counters show it mostly doesn't. Whatever *must* happen has to be a hook, a command or a check.
3. **The refactor improves code the owner cannot work in.** F0–F5a made the Python easier to change; it did not move
   any of the four promises forward.
4. **Parallel sessions create their own friction.** One shared checkout, 18 worktrees, 27 branches: 9 of the 19
   retro notes are about that, not about the change itself.

## 2. Intent

The core is four promises. Each is checked by watching a real session, not by reading code.

| | Promise |
|---|---|
| P1 | **Retrieval by default**: before an agent changes code, the relevant docs, C4 elements and code-graph nodes are already in its context, put there by the kit |
| P2 | **Docs move with code**: a code change ends in a code PR/MR and a docs PR/MR that link each other, opened by the kit after the gate passed |
| P3 | **Guardrails installed and blocking**: one install puts them in every repo of the workspace; red means stop |
| P4 | **Docs created and kept alive**: what exists today, kept |

**Done when:**

1. A person opens Claude Code at the workspace root **or inside a service repo** and asks for a change. Before the
   first edit, the session holds the matching doc sections (path, section, trust), the C4 elements behind them and the
   graph nodes for the files named — injected by a hook, not fetched by the agent's choice.
2. An edit to code in a session that consulted no docs is stopped once, with the pages to read.
3. Each month, at least 80% of the sessions that edit code consulted docs before their first edit, measured by the kit
   from its hook events; the retrieval golden questions (`eval`) stay above their threshold.
4. `camaron change pr` opens the code PR(s) and the docs PR, linked, only after `change gate` passed for the exact
   commits. A team that adopts the kit's CI snippet gets a check that fails a code PR touching documented sources with
   no linked docs PR and no `docs: none — <reason>` line.
5. After install, in every repo of the workspace and in cam-docs: an AI co-author trailer or "Generated with" line is
   dropped from a commit and a push that still carries one is refused; staged secrets block the commit; `change gate`
   fails on a red Sonar quality gate (when the repo has a Sonar project) and on new high or critical vulnerabilities in
   the dependency files the change touches.
6. All of the above with no model call (AGENTS.md §1, priority 1).

**Anti-goals — a failure even if it works:** a tracked file written into a service repo; a guardrail that could not
run reported as green; retrieval that floods the context (cap ~1,500 tokens per prompt); a prompt hook slower than
~1 s; a new feature outside P1–P4 during the turning point; an existing project needing a manual step.

## 3. Decisions (taken with the user, 2026-11-17)

| ID | Question | Decision | Why / consequence |
|---|---|---|---|
| D1 | What stops while the core is finished | **Features freeze; the hexagonal refactor continues.** Portal, desktop, board, ADRs, stories, canvas, cost, Libraries, exports, autopilot and wizard get bug fixes only. F5b–F7 go on in the Python kit; the F0 tests stay in CI | The recommendation was to pause the refactor too. With the core staying in Python (D2), the refactor improves the codebase the core is built in |
| D2 | Language of the core | **Python, in the current kit.** Revised the same day: a new Java core was chosen first, then postponed. P1–P3 are built in the Python kit, inside the hexagonal layers. A language change stays open for later and undecided; if it comes back, TypeScript or Go are the candidates (Node is already required, and the app and portal are JS), not Java | Why Java was dropped: a CLI that ships to any stack needs a GraalVM native image built per OS, plus code signing; the JDK has no PTY or OS secret store; users would still need Python (graphify) and Node. The [spike](../../research/kotlin-migration-spike.md) priced a full port at 4–8 weeks, mostly platform work. A parked analysis of a full Java port lives on the branch `docs/java-core-design` |
| D3 | Where retrieval works | **At the workspace root and inside every service repo**, with no tracked file: hooks in the repo's `.claude/settings.local.json`, the MCP servers at Claude Code's local scope, skills linked and hidden through `.git/info/exclude` (as `fs_links.git_exclude` already does) | Each mechanism is verified against current Claude Code behaviour before building |
| D4 | Paired-PR check in CI | **A snippet the team adopts**: the kit prints it (GitHub and GitLab), the team commits it | Keeps "service repos never receive kit files" |
| D5 | Git hooks in a repo that has its own (husky, pre-commit) | **Chain** (the default, not asked): `core.hooksPath` points to the kit's hooks, which then run the repo's own | Revisit if a repo needs otherwise |

When the refactor and the core compete for a session, the core goes first.

## 4. The promises in detail

### P1 Retrieval by default

| Hook | Does |
|---|---|
| SessionStart | Code session (a service repo, or a change is open): the repo's brief, the open change, how to search. Documentation session: today's plan state |
| UserPromptSubmit | `context "<prompt>"`, no AI: the best doc sections (confirmed first, drafts marked, suspect left out), the C4 elements whose sources those pages cite, the graph nodes for the files and symbols named. Under ~1,500 tokens. Nothing when no hit passes the score threshold, so short prompts stay quiet |
| PreToolUse (Edit, Write, MultiEdit on a service-repo file) | If the session has no retrieval event yet (an injection with hits, or a docs MCP call), stop once and list what to read, or let the agent say no page covers it |
| Stop | Quiet while a change is open (skill note) |

- Agents without hooks (Codex): AGENTS.md, the MCP servers, and `change start`, which prints the docs to read.
- Graphify freshness: `change start` rebuilds a repo's graph when its HEAD moved since the last build; CI rebuilds on
  merge.
- Measure: hook events feed `kpis` (share of code-editing sessions with retrieval before the first edit); `eval` per
  release; `ab` stays available.
- Usage counters stop dirtying the tree: written to the git-ignored cache and rolled up at `checkpoint`/`share` only
  (4 skill notes).

### P2 Docs move with code

- Finish `camaron change` with the smallest set: `start`, `verify`, `gate`, `pr`, `status`, `close`. `assess`
  (difficulty) and `impact` can stay in the skills until the rest works.
- `change` records where each repo's code lives (branch in the person's checkout, or a code worktree when it is busy),
  and `check` and `pr fresh` read sources from there. This removes the 7 shared-checkout notes and the 2 worktree
  notes.
- `pr`: GitHub (`gh`) and GitLab (`glab`); drafts; bodies cross-linked; resumable without opening a second PR; without
  a forge CLI, it prints the URLs and bodies.
- CI snippet `docs-link`: reads the PR body for the `Docs:` link or a `docs: none — <reason>` line.

### P3 Guardrails installed and blocking

Part of `setup` (and a `guard install` / `guard status` pair), for every repo of the workspace and cam-docs:

| Guardrail | Where | Blocks |
|---|---|---|
| AI co-author trailers and "Generated with" lines | `commit-msg` drops, `pre-push` refuses (the kit repo's own `.githooks`, made generic) | yes |
| Secrets | `pre-commit`: gitleaks on staged changes (the kit already ships gitleaks); `change gate`: gitleaks on the change's range | yes |
| Forbidden paths (`.env*`, `*.pem`, `*.key`, `id_rsa*`, `secrets/`) | `change gate` | yes |
| Vulnerable dependencies | `change gate`: OSV on the dependency files the change touches (`inventory` exists) | high and critical |
| Sonar quality gate | `change gate`: the repo's quality-gate status (`sonar.py` reads it; needs the project key and a token per machine) | red |
| Claude Code attribution | the settings the kit writes turn attribution off (exact key checked against the installed Claude Code) | — |
| Anything that could not run | reported as "not run" in the gate and the PR body | never green |

The git hooks live in a kit-owned folder set with `git config core.hooksPath`: local config, no tracked file.

### P4 Docs created and kept alive

Kept as is. Pending: the `confirm` unit (human review), the Stop hook during a change, the usage counters (P1).

## 5. Order of work

| Step | What | Done when |
|---|---|---|
| 0 | Clean up, with the user's go-ahead: the workspace's kit checkout back on `main`; a decision on PRs #13 #14 #15 #17; the 5 merged branches and their worktrees removed; the 13 old branches archived or deleted | `git worktree list` and the branch list hold only live work; local `check` matches CI |
| 1 | Take D1–D5 | Done 2026-11-17 (§3) |
| 2 | P1: the prompt hook and the pre-edit stop, over the existing search; then measure for a week | Done-when items 1–3 observed in real sessions |
| 3 | P3: the installer, git hooks and gate checks | Done-when item 5 on camaron-dev and one Java project |
| 4 | P2: `change start/verify/gate/pr/status/close` | Done-when item 4 for one real change |

Every step is built in the Python kit as the real implementation: test-first, on the three OSes (AGENTS.md §2). The
refactor (D1) runs alongside, behind the core.

## 6. Open questions

- Codex: which of the hooks it can run today.
- The exact Claude Code mechanics for D3 (local-scope MCP, `settings.local.json`, skills discovery) — verify before
  building.
- SonarQube or SonarCloud, and where each machine's token lives (the kit's `creds` already stores forge tokens).
- A later language change (TypeScript or Go): what would make it worth revisiting.
- Whether the "extended" Python kit keeps a release cadence or only fixes.

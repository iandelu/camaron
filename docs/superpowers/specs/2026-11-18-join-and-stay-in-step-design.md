# Joining a team's project and staying in step — design

## 1. Intent

The user's request (2026-11-18), in short: "Adding a project for someone who joins an existing one is not polished.
When they already have the repos cloned and the documentation URL exists, nobody knows what to do. Then the C4, the
plan and so on are not in sync for everyone. It should be clear. It is a core part." Then: "When cam-docs was brought
in, the portal did not show the C4; the plan, I'm not sure. *Compartir* is confusing: it should let you bring changes
(pull), upload changes (push) and sync."

Who it is for: a person joining a team whose `cam-docs` already exists, and then every teammate, every day.

Why: Camarón is the project brain. A brain each teammate holds a different copy of, or that a newcomer cannot reach,
is not one. This is core (P4, "docs created and kept alive", in the
[turning-point spec](2026-11-17-core-turning-point-design.md)), so it is an **exception to that spec's feature freeze
(D1)**, recorded here.

## 2. What happens today

| | Finding | Where |
|---|---|---|
| F1 | **Two doors, nothing says which.** *Elegir carpeta* on a folder of repos never asks whether the team already has a `cam-docs`: `onboard.start` makes a separate project with its own plan and C4 draft. The CLI asks (`projects.TEAM_URL_Q`); the app does not. Seen on a real machine: a registered `cam-docs` with no remote and no commits next to a folder of the team's repos | `desktop/renderer/src/Hub.jsx`, `lib/onboard.py` |
| F2 | **Join does not say where.** It asks for the URL, then "Folder to bring the team's cam-docs into", not "the folder where your repos are". `sync_repos` looks for each repo at `<workspace>/<name>`, so a clone under another folder name is cloned again. Real case: the team names a repo `wallet-adapter` and its URL is `operator-adapter.git`. A join has no repos step to fix it | `desktop/main.cjs` `hub:join`, `lib/adapters/git/repos.py` |
| F3 | **The portal draws the C4 only from a local build.** `drawC4` needs the LikeC4 build in `.camarones/.cache/viewers/architecture` (git-ignored). `first_look` builds it; a join's setup never does, so a joined portal says the C4 is not built. After a pull, `viewers()` marks the build stale and nothing rebuilds it | `portal/app/src/content/doc.js`, `lib/app/viewers.py` |
| F4 | **A join changes the team's plan.** The tools step saves this machine's choice in the shared `workspace.yaml` (`onboard.install_tools` → `set_components` → `project.components`). `plan.sync` uses it to drop units (every `repo-wiki` when OpenWiki is not picked). `onboard.done` checkpoints it and the next share publishes it | `lib/onboard.py`, `lib/app/components.py`, `lib/plan.py` |
| F5 | **Nothing brings in the team's work.** Opening a project never fetches. `share` does checkpoint, rebase and push as one action; auto-share is per machine and off by default. The CLI's `sync` already means "clone or pull the code repos" | `lib/app/share.py`, `lib/interfaces/cli/commands/machine.py` |
| F6 | **The C4 model can be replaced whole, and is never updated from code without AI.** The arch step's overwrite replaces `model.c4`, confirmed elements included. Otherwise the model only changes through the `arch-system` agent unit or edits in the portal (`lib/c4edit.py`) | `lib/onboard.py` `arch_save`, `lib/quickarch.py` |

## 3. Goals

**Done when:**

1. A person who has the team's repos cloned and the team's `cam-docs` URL reaches the team's project from either door
   of the start screen (or from the CLI). No repo already on disk is cloned a second time, and no separate project is
   created by mistake.
2. Right after the join, the portal shows the team's C4 (when LikeC4 is installed on this machine), the team's plan and
   the team's pages, unchanged.
3. A join never changes a team decision: the repos list, the components, the profile, the interview mode, the plan's
   statuses or the C4 model. With the same kit version as the team's last commit, `git status` in `cam-docs` is clean
   after a join.
4. Opening a project (the app's window, the CLI wizard) brings in the team's work by itself when it can. When it
   cannot, it changes nothing and says why. It never pushes and never loses local work.
5. The app's Team section and the CLI offer **Traer cambios** (pull), **Subir cambios** (push) and **Sincronizar**
   (both), with "N to bring · M to upload" and the last sync always visible.
6. After any bring-in, the local views that are older than what they show are rebuilt: the C4 explorer at once, the
   code graphs of repos whose HEAD moved in the background.
7. An existing C4 model is never replaced by the wizard. What the code has and the model does not is found without AI
   and proposed; one click adds the proposals as `#ai-draft` elements. The kit never edits or removes a confirmed
   element and never deletes anything; elements it can no longer find are flagged.
8. All of the above with no model call (AGENTS.md §1), on macOS, Windows and Linux, and every 3.x/4.x project opens
   with no manual step.

**Non-goals:** real-time collaboration; merging conflicting edits to pages; repos spread across unrelated folders
beyond "the workspace folder, plus folders this machine names to search"; serving the C4 explorer from git; changing
how a brand-new project is created, apart from the question in §6.2.

**Anti-goals — a failure even if it works:** anything automatic that pushes; a bring-in that loses or hides local
work; a join that changes the team's repos, plan or C4; a confirmed C4 element rewritten or removed by the kit; a
second clone of a repo already on disk; a folder of the person's renamed, moved or deleted (C1 is the one exception:
a `cam-docs` the kit made and never shared, set aside on the person's click, never deleted); a kit file written into a
service repo; a joke in a conflict, error or decision prompt (AGENTS.md §3).

## 4. Decisions taken with the user

| ID | Question | Decision |
|---|---|---|
| D1 | On opening a project: bring in the team's work, or only say there is some? | **Bring it in by itself** when it can; otherwise change nothing and say why |
| D2 | What replaces *Compartir* | **Traer cambios** (pull), **Subir cambios** (push), **Sincronizar** (both) |
| D3 | An existing C4 when the code changes | **Detect and propose**: never overwrite; a click adds what is new as drafts to review |
| D4 | The 2026-11-17 feature freeze | This is core: an exception, recorded in §1 |

## 5. Approaches

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | **One catch-up routine.** One idempotent kit function brings this machine to the team's state. The join (first time), opening the project (every day) and *Traer cambios* all run it. The new entry and the three actions sit on top | More work up front (setup, join, the server on open, share). The join and every day share one path, so a fix to one fixes the other; CLI and app stay the same; it is all testable offline and without AI | **Recommended**; approving this document approves it |
| B | Point fixes: ask the URL in the hub, build the C4 at the end of the join, split *Compartir*, pull on open in the app | Ships sooner. Each fix lives in another place (hub, wizard, CLI, server); the C4 going stale when a teammate edits it stays a separate problem; the CLI and the app drift apart again, which is how F1 happened | Not chosen |
| C | Commit the generated views (C4 explorer, graphs) to `cam-docs` so a clone shows them at once | Big generated files in git, a conflict on every rebuild, and the C4 still goes stale when whoever edits the model does not rebuild | Rejected |

## 6. Design

### 6.1 The catch-up routine

One use case in `lib/app/` (name is the builder's; *catch-up* below), behind `services`, with no model call and no
push. Steps, in order:

1. **Bring in the team's work** (`share.pull`, §6.4). No remote, or no branch on the remote yet: skipped. Otherwise
   fetch, then rebase this machine's local commits onto the remote branch with `--autostash`, as `share` already
   does. A conflict undoes the rebase (`rebase --abort`), so the tree is exactly as before, and the result names the
   files. One exception: when every conflicting path is a derived file the kit regenerates (`docs/.status.json`,
   `docs/llms.txt`, `docs/llms-full.txt`, and the usage counters while they are still tracked), the team's version is
   taken and the file is regenerated after the rebase. After a successful rebase the board repair runs, as in
   `share`.
2. **Find the repos** (§6.3). Nothing is cloned here except during a join's setup.
3. **Rebuild what is local and stale.** The C4 explorer when `viewers()` says it is missing or stale and LikeC4 is
   installed (`viewers.build_c4`). The code graphs of repos whose HEAD moved since their graph, as a background job,
   when graphify is a chosen component. Wiki graphs stay manual, as today.
4. **Check the C4 against the code** (§6.5). Read-only; skipped when no repo HEAD and no `.c4` file changed since the
   last check, which is remembered in the git-ignored cache.

It never writes `workspace.yaml`, `plan.yaml` or a `.c4` file, never commits (except the board repair's own
checkpoint, as `share` does after a rebase) and never pushes. It returns one result the app and the CLI both word:
`{pull: {status, commits, files}, repos: {here, linked, missing, taken}, views: {c4, graphs}, c4: {new, gone}}`.

**Who runs it:**

| When | How |
|---|---|
| A project window opens in the app | Once per window, as a background job: the window never waits for it. The Summary shows its outcome in one line; a conflict or an error shows until it is dealt with |
| The CLI wizard opens on a project | The same, inline, before the menu |
| *Traer cambios* (app, `camaron pull`) | The same routine |
| A join | After the clone: its setup runs steps 2 and 3 with cloning allowed |
| Scripts, CI, `--json` commands, `camaron up` | Never on their own |

A lock in the git-ignored cache keeps one run per project at a time; a second request attaches to the running job.
Offline, opening still works and says the team's latest could not be reached.

### 6.2 The way in

**Start screen (app hub).**

- *Elegir carpeta* on a folder that is a repo or a folder of repos with no `cam-docs` yet: the "what I found" card
  asks before going on:

  ```
  ┌ Lo que he encontrado ─────────────────────────────────────┐
  │ [Código existente]  14 repos: api, web, infra y 11 más    │
  │                                                           │
  │ ¿Tu equipo ya tiene su documentación en un repo cam-docs? │
  │  ( ) Sí, unirme a ella   URL [______________________]     │
  │  ( ) No, empezar una nueva                                │
  │                                     [Cambiar carpeta] [Continuar] │
  └───────────────────────────────────────────────────────────┘
  ```

  Nothing is preselected, and *Continuar* stays disabled until one is picked. "Yes" joins the team's `cam-docs` into
  this same folder (no second folder dialog) and goes on as a join. "No" is today's *Continuar*.
- *Unirme a la documentación de mi equipo*: the URL, then a folder dialog titled "The folder where your repos are (or
  will be)". `cam-docs` goes inside it.
- A folder that already is a project: unchanged, except the two leftovers of today's flow below.

**Leftovers of today's flow** (Claude's calls C1 and C2):

- **C1 — a stray local project in the repos folder.** `<workspace>/cam-docs` is a project the kit made, with no
  remote and no commits (F1's real case). "Yes, join" on that folder, or joining into it, offers before anything
  happens: "This folder has a local cam-docs that was never shared. Set it aside as `cam-docs.local-<date>` and bring
  in the team's?" Only the person's click sets it aside (a rename next to it); nothing is deleted. A `cam-docs` with a
  remote or with commits is refused as today (`Taken`), with the reason.
- **C2 — the team's docs already on this machine elsewhere.** `projects.join` finds a registered clone with the same
  remote at another folder. Instead of reusing it silently, it says so ("You already have this team's docs in
  `<path>`") and opens that one, adding the picked folder to its folders to search for repos (§6.3). The repos there
  are linked, not cloned again, and no second clone of `cam-docs` is made.

**CLI.** `projects.pick` already asks for the team's URL. `camaron join URL [FOLDER]` keeps its form; its help and the
tutorial say FOLDER is where the repos are.

**The join's first run** gains a read-only **repos** step: `JOIN_STEPS = ("repos", "tools", "setup", "intro")`. It
lists the team's repos with what this machine has for each:

| Row | Meaning |
|---|---|
| *aquí* | `<workspace>/<name>` is a clone of that URL |
| *enlazado desde ./operator-adapter* | found under another folder name, linked (§6.3) |
| *falta: se clonará* | not on this machine; setup clones it |
| *carpeta ocupada* | `<workspace>/<name>` exists and is something else; left alone, setup does not clone it |

It offers *Buscar en otra carpeta…* (a folder to search, remembered for this machine only) and *Continuar*. It cannot
change the team's list: that stays the team's decision (Team › repos, or the `new` first run).

### 6.3 Repos found by their remote, not their folder name

For each repo in `workspace.yaml`:

1. `<workspace>/<name>` is a clone whose origin matches the repo's URL (`projects.remote_key`): nothing to do.
2. Otherwise, search the workspace folder's first level, then the folders this machine named, for a clone whose origin
   matches. Found: link `<workspace>/<name>` to it with `fs_links.link` (a relative symlink, or a junction on Windows
   without symlink rights). The kit, the agents and every doc path keep reading `<workspace>/<name>`.
3. `<workspace>/<name>` exists with another origin, or is not a repo: never touched; reported as *taken*.
4. Not found: *missing*. Only a join's setup or `camaron sync` clones it.

The links are recorded per machine in the git-ignored cache. Uninstall removes them and nothing else, and
`scripts/sandbox.py traces` must stay clean. When the workspace folder is itself a git repository, each link is hidden
through its `.git/info/exclude` (`fs_links.git_exclude`). No folder of the person's is ever renamed or moved.

### 6.4 Traer, Subir, Sincronizar

| Action | Kit | CLI | HTTP (same access as `/api/sync/share` today) | Outcomes |
|---|---|---|---|---|
| Traer cambios | `share.pull` + the rest of catch-up | `camaron pull` (new) | `POST /api/sync/pull` (new) | up-to-date · pulled (n) · conflict (files) · no-remote · error (reason) |
| Subir cambios | `share.push`: checkpoint, then push | `camaron push` (new) | `POST /api/sync/push` (new) | pushed · nothing · behind (bring first) · blocked (secrets) · no-remote · error |
| Sincronizar | `share.share`, unchanged: pull then push | `camaron share` (unchanged, `--auto` too) | `POST /api/sync/share` (unchanged) | as today |

- *Subir* never rebases: when the remote moved it refuses with "bring the team's changes first" and offers
  *Sincronizar*.
- `sync_status` is fresh after the routine (it fetched), so "N to bring · M to upload" is right without another click.
- The app's Team section: a status line ("3 por traer · 1 por subir · última vez hace 2 h"), the three buttons with
  the useful one as primary (behind → *Traer*, ahead → *Subir*, both → *Sincronizar*), and the per-machine toggle,
  renamed "Subir al guardar" (`share --auto`, same file).
- **The portal's Sync view** (`portal/app/src/Sync.jsx`, Claude's call C5) gets the same status line and the same
  three actions, so *Compartir* is gone everywhere. The new routes take the access `/api/sync/share` has today; this
  project neither tightens nor loosens that gate.
- The UI never uses the bare word "sync" for this. The CLI's `sync` keeps meaning the code repos.

### 6.5 Team decisions and this machine's tools

- `workspace.yaml` `project.components` keeps its meaning: the team's choice. Only the `new` first run, `profile` and
  an explicit team setting write it. The plan reads only the team's choice.
- What this machine installed or left out is kept per machine in the git-ignored cache. A tool runs where it is both
  chosen by the team and installed here. With no such file (every existing project), the machine has whatever is
  installed, as today.
- The join's tools step lists the team's components. Unticking one means "not on this machine" and says what that
  costs ("without OpenWiki this machine cannot generate wikis; the team's plan does not change"). It never writes
  `workspace.yaml`.
- **C3 — a machine's choice already shared by today's join.** No automatic repair: the kit cannot tell a mistaken
  choice from a team decision. The team picks the component again (Team settings, or `profile`) and `plan.sync`
  brings back every unit dropped for that component, whatever note it was dropped with (today only `NO_WIKI` is
  restored: a test locks the rest).

### 6.6 The C4: never replaced, changes proposed

- **No more overwrite.** The arch step of a first run on an existing model no longer offers to replace it. It offers
  "See what the code has that the C4 does not" (the proposals below). A project with no model is unchanged.
- **Compare, without AI and without writing.** `quickarch.scan()` (what the code shows) against `c4edit.index()` (the
  model):
  - repos: matched by `metadata repo` (the scan and the agent units write it), else by the title's identifier; a repo
    in `workspace.yaml` and not in the model → proposed;
  - datastores, brokers, identity providers: matched by kind plus normalised label and technology; new → proposed;
  - relations between matched elements: matched by from, to and kind (labels may differ); new → proposed;
  - **gone**: an element whose `metadata repo` names a repo no longer in `workspace.yaml`, or a draft datastore or
    broker the scan no longer finds → flagged "still there?". Never removed by the kit, confirmed or not. Elements a
    person added with no scan counterpart are never flagged.
- **Apply on a click.** The chosen proposals are added as `#ai-draft` elements and relations with
  `metadata { source 'scan' }`, through `c4edit` (a new `add_element` with the lock, the validation and the rollback
  every edit already has), and placed in the views the scan's own render fills. Then the explorer rebuilds. They are
  reviewed and confirmed with the flow that exists today.
- **Where it shows** (Claude's call): the portal's C4 view, above the elements to review, as "Proposals from the
  code", since review and confirmation already live there. The app's Summary shows the count with a link. The routine
  never applies them: if every machine wrote them on open, two teammates would add the same element and collide on
  the next sync.
- **C4 — a model kept in a service repo** (`workspace.yaml` `project.architecture: <repo>:<path>`). The routine never
  pulls code repos: fast-forwarding or switching a developer's branch on open would do more harm than a late C4. The
  explorer still rebuilds from that repo's checkout, and the Summary says the C4 lives in `<repo>` and updates when
  that repo is pulled. Proposals are offered there as the portal's edit and confirm already are: written into that
  repo's checkout, left uncommitted for the person to commit with their code. The model is the team's own file, not
  a kit file.

### 6.7 Errors and wording

- es and en for every string; no joke in a conflict, an error or a decision prompt. The routine's waiting line may
  carry the screen's one joke.
- Conflict: "Couldn't bring in the team's changes: they clash with yours in `<files>`. Nothing was changed." Then
  *See files* and *Open a terminal here*.
- No access, no token, network: the reasons `share` already words (`git_failure`, `ui/src/share.js`).
- A link that cannot be made (Windows without symlink rights or junctions): the repo stays *missing* and the line says
  what to do; setup does not clone over it.

### 6.8 Compatibility (AGENTS.md §2.3)

- `camaron share`, `share --auto`, `/api/sync/share`, `share.json` and `shared.json`: unchanged.
- `project.components`: same key, same meaning. The new per-machine file is optional.
- `firstrun.json`: a join saved at `tools` or `setup` resumes there; a new join starts at `repos`. Step ids stay those
  of `STEPS`.
- Pages and `.c4` files written or confirmed by people are never rewritten; proposals only add.
- `VERSIONS["kit"]`: next minor.

## 7. Delivery in slices

Each slice merges on its own, test-first, on the three OSes.

| Slice | What | Done when |
|---|---|---|
| S1 Stay in step | `share.pull` / `share.push`, the catch-up routine (steps 1 and 3), run on open in the app and the CLI wizard, the three actions in the app's Team section and the portal's Sync view | Done-when items 4, 5 and 6, and the C4 shows after a join (item 2) |
| S2 Join right | The question on the found card, the join folder wording, repos found by remote and linked, the join's repos step, team vs machine components, the leftovers C1 to C3 | Done-when items 1, 2 and 3 on the sandbox, starting from repos cloned under other names |
| S3 C4 proposals | Remove the overwrite, the comparison, `c4edit.add_element`, the proposals in the portal and the count in the Summary, step 4 of the routine | Done-when item 7 |

## 8. Testing

- **pytest** (`make_workspace`, `isolated_env`, a local bare repo as the team's remote; no network):
  - `share.pull`: up to date; behind; local commits rebased; uncommitted changes kept; a conflict leaves the tree as
    it was; a conflict only in derived files resolves and regenerates them.
  - `share.push`: pushes; refuses when behind; blocked on staged secrets.
  - The routine never writes `workspace.yaml`, `plan.yaml` or `.c4`, and never pushes (a characterization test on the
    files it may touch).
  - Two teammates: A edits `model.c4` and shares; B opens → B's C4 explorer is rebuilt.
  - A join with the repos already cloned: under the same names; under other names (linked, not cloned); a folder
    taken by another repo (left alone); a repo missing (cloned by setup).
  - After a join, `git status` in `cam-docs` is clean; unticking OpenWiki leaves the plan's `repo-wiki` units as they
    were.
  - C1: a stray kit-made `cam-docs` (no remote, no commits) is set aside only after the click, and its files are all
    in `cam-docs.local-<date>`; one with commits or a remote is refused. C2: a registered clone with the same remote
    elsewhere is opened, the picked folder is added to its search folders, and nothing is cloned twice.
  - C3: picking a component again brings back the units dropped for it, whatever their note.
  - C4: with `project.architecture` set, the routine pulls no code repo and still rebuilds the explorer.
  - Links: uninstall removes them; the Windows junction path (simulated where needed).
  - C4 comparison: a new repo, a new datastore and a new relation proposed; a confirmed element never edited; a gone
    element flagged, not removed; applying proposals keeps the model valid, and rolls back when it would not be.
  - Old forms: a project with no per-machine file; a `firstrun.json` of a join saved at `tools`.
- **vitest**: the found card's question (nothing preselected, *Continuar* disabled until a choice); the Team status
  line and which button is primary; the Summary's catch-up line for each outcome; the portal's Sync view with the
  three actions.
- **node --test**: any new pure helper in `desktop/lib`.
- **End to end**: the sandbox, with two clones of a docs remote standing for two teammates: a C4 edit by one shows for
  the other on opening; a join into a folder whose PetClinic repos have other folder names; then `traces` after
  uninstall.

## 9. Docs that move with it (AGENTS.md §5.1)

README (es); the guides `using`, `app` and `portal` (en and es); `lib/tutorial.py` with `TUTORIAL.md` regenerated;
`templates/docs/guides/tutorial.md` and its es twin (existing projects keep their copy: say so in the commit); the
guided tour if a Team target moves.

## 10. Calls made by Claude (check on review)

| | Call | Where |
|---|---|---|
| C1 | A stray `cam-docs` the kit made and never shared (no remote, no commits) in the repos folder is set aside as `cam-docs.local-<date>` on the person's click, then the team's is cloned; never deleted. With a remote or commits: refused as today | §6.2 |
| C2 | The team's docs already registered elsewhere on this machine: say so, open that clone and add the picked folder to its folders to search for repos; no second clone | §6.2 |
| C3 | A machine's tool choice already shared by today's join is not repaired automatically; picking the component again restores the units dropped for it | §6.5 |
| C4 | A C4 model kept in a service repo: the routine pulls no code repo; proposals are written into that checkout uncommitted, as portal edits already are | §6.6 |
| C5 | The portal's Sync view gets the same three actions; the new routes take `/api/sync/share`'s current access | §6.4 |
| C6 | Proposals from the code live in the portal's C4 view; the app's Summary shows their count | §6.6 |
| C7 | The found card asks the team question with nothing preselected; *Continuar* waits for an answer | §6.2 |

## 11. Left to the builder

Module and job names; where exactly the per-machine files live inside the cache; the git mechanics of resolving
derived-file conflicts; the matching thresholds of the C4 comparison; the exact es/en copy within §6.7's rules.

# A C4 model backed by the code, for agents — design

## 1. Intent

The user's request (2026-11-18), in their words: "I want the LikeC4 model to be consumed by the agents, together with
the ADRs and everything. Every element of the C4 model should be verifiable in code, the way other documentation tools
do it." The tools they meant: **Swimm** (docs tied to code; a doc goes out of date when its code changes) and
**Structurizr** (the component level comes from the code). They want all three ideas discussed, in this order:
anchors first (Swimm), then a drift report (Structurizr), and later a gate. "Document it in the README: it is core."

Two principles, both the user's, override everything else:

1. **The C4 represents the code, not the other way round.** When the two disagree, the model is what needs fixing.
2. **Nothing in the C4 without evidence in the code.** "The point of the session was that the C4 has evidence in the
   code, not that the AI makes it up." An element or a relation with no evidence is treated as invented: agents do not
   get it as fact. Only a person can vouch for what the code cannot show (an actor, an external system).

Why it matters: an agent can only trust the C4 if something checks it. Today the model is a drawing the agent may
read: the prompt hook injects up to three elements matched by name, the official `likec4` MCP serves the raw model,
and nothing tells either of them whether the drawing is backed by the code. The kit's rule for pages, *better no
information than wrong information*, does not reach the C4 yet.

This is core work under the turning point ([spec](2026-11-17-core-turning-point-design.md)): P1 (retrieval by default:
the C4 elements behind a prompt, now with their evidence) and P4 (docs kept alive). It does not break the feature
freeze (D1).

## 2. Where things stand (2026-11-18)

| Piece | Today | Gap |
|---|---|---|
| Element anchors | `metadata { repo '<repo>' }` on repo containers (CONVENTIONS §4); `metadata { evidence '…' }` on components, written by agents (chub: every component of `repos/backoffice-gateway.c4`) | `evidence` is free text: comma-separated, globs, the repo named only on the first path. **Nothing reads it except the prompt hook's ranking** (`app/prompt_context._c4`). Relations have no anchors |
| Freshness | `harness/freshness.py`: page → code (`repo:path`, `#Lx-Ly`, `#Class.method`), page → page, page → `c4:<element>` (the element's *text*) | Nothing goes from the C4 to the code |
| Code facts | graphify graph per repo (`cam-docs/graph/<repo>/graph.json`: nodes with `source_file`, edges `imports`, `imports_from`, `calls`, `references`, `extends`, …, `built_at_commit`); `quickarch.scan()` (repo → repo HTTP calls, repo → datastore, broker, identity provider) | Never compared with the model after `arch-draft` |
| C4 editor | `c4edit` reads metadata as `key 'value'` pairs only and rewrites the whole block on confirm | **A list value (`code ['a', 'b']`) would be dropped on the first confirm from the portal.** LikeC4 1.59.4 accepts lists in `metadata` and `metadata` on relations (checked with a probe model, `✓ Valid`) |
| Agents | Prompt hook (top 3 elements by name, with `evidence`); `likec4` MCP; pages citing `c4:` | No evidence check, no relations, no decisions |
| ADRs | Pages under the decisions folder with `x-sources`; `adr_pack` picks C4 elements by repo only; `adr._touches_of` ignores `c4:` sources | No link from an element to the decisions about it |
| CI | cam-docs' `docs.yml` (`ci/umbrella.github.yml`, GitLab twin): on a pull request, `camaron setup --ci` (clones the service repos with `REPOS_TOKEN`) then `camaron check`; red on errors only. Service repos: the `docs-fresh` job comments, never fails | — |
| Prior notes | `docs/research/dev-harness-requirements.md` C3 ("a kit check comparing the code graph with the confirmed C4 without touching the repo"); `tooling-candidates.md` I1 (Swimm), E2 (Structurizr) | — |

## 3. Goals, non-goals, anti-goals

**Goals**

| | Goal |
|---|---|
| G1 | Every C4 element and relation can name the code behind it, in the `.c4` file itself |
| G2 | The kit knows each element's and relation's evidence state against today's code (§5.2) |
| G3 | What has no evidence is treated as invented: agents do not get it; people see it marked; `check` warns (errors with `--strict`) |
| G4 | A drift report compares what the code shows with what the model draws: relations in the code and not in the model, relations in the model with nothing in the code, source code no element covers |
| G5 | Agents receive C4 elements with their state, their relations and the decisions about them: through the prompt hook, a kit MCP tool and the pre-edit stop |
| G6 | ADRs can cite elements, and the decisions about an element are found from it |
| G7 | All of it with no model call (AGENTS.md §1, priority 1), on macOS, Windows and Linux |
| G8 | README (core section), guides, tutorial and the rules shipped to projects explain it, in the commit that ships each piece |

**Non-goals for this round**

- Phase 3, the gate on code changes (§9): designed here, built later.
- Any new screen in the portal or the desktop app (freeze, D1). The existing C4 editor gets only the fix that keeps
  list metadata (a bug fix).
- Building components from naming conventions (Structurizr's *component finder*): only offered as suggestions (§6.3).
- Generating ArchUnit, dependency-cruiser or import-linter rules; per-language analyzers (jdeps…): they fail AGENTS.md
  §2.4 (a tool per stack, jdeps needs a build).
- An AI review of drift.
- Runtime evidence (OpenTelemetry service graphs).

**Anti-goals — a failure even if it works**

- An agent receives an element or a relation with no evidence as if it were fact.
- The kit rewrites a `.c4` file on its own (to add a state tag, to convert `evidence`, to "fix" drift). States live in
  the kit's state files, never in the model.
- A check that could not run shown as green: a missing graph, a repo not cloned, an anchor that cannot be parsed. It is
  reported as *not checked* and why.
- The C4 vanishing from agents' context because every element went `suspect` after a normal sprint (§5.3).
- A 3.x/4.x project whose CI is green turning red with no opt-in: C4 evidence findings are errors only under
  `--strict`.
- A file written into a service repo; the prompt hook going over ~1 s or its ~1,500-token cap.

## 4. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| **A** | **Anchors in the `.c4` metadata; states through the freshness machinery; drift from graphify and `quickarch.scan`** | One place for the model and its evidence; reuses what exists; needs `c4edit` to read and keep lists; relations graphify cannot see need their own anchor | **Chosen by the user** |
| B | Anchors in a side file (`architecture/anchors.yaml`) | The machine can rewrite it freely; but two places to keep in sync, a renamed element loses its anchors, the LikeC4 viewer and MCP never see them, agents writing the model must remember a second file | Dropped |
| C | Components derived from naming conventions (Structurizr's finder: "every package is a component") | Zero drift by construction; fits only regular layouts (chub's `security`, `errorHandling`, `observability` are cross-cutting, not packages); regenerating files collides with confirmed descriptions | Dropped; kept as *suggestions* for uncovered code (§6.3) |
| — | Per-language analyzers; an AI drift review; state tags written into `.c4` | §2.4; priority 1; anti-goal | Dropped |

## 5. Phase 1 — evidence on every element and relation (Swimm)

### 5.1 How an anchor is written

```
security = component 'OIDC permission policy' {
  metadata {
    code ['backoffice-gateway:src/main/resources/application.properties#L33-L47']
  }
}
restApi -> platformData 'direct:{operationId}-base' {
  metadata { code 'backoffice-gateway:src/main/java/platformdata/CountryRoute.java#CountryRoute.configure' }
}
```

- Key `code`: one string or a list of strings. Each entry uses the `x-sources` syntax: `repo:path`, `repo:path#Lx-Ly`,
  `repo:path#Class.method`, plus folders (`repo:src/main/java/georestrictions/`) and globs
  (`repo:src/main/java/*/*Route.java`). Every entry names its repo.
- **Legacy `evidence`** is read as evidence too, never rewritten by the kit: split on commas; an entry without `repo:`
  takes the previous entry's repo (chub's form), and the first entry takes the repo of the enclosing repo container's
  `metadata { repo }` (declared data, not a guess; the kit's own fixture writes `evidence 'src/main/java/demo/Api.java'`).
  An entry that still has no repo, or cannot be read, counts as no evidence and is reported. `arch-verify` lists the
  elements whose evidence is only legacy; turning it into `code` is agents' and people's work (the next `repo-brief`,
  or a unit like `fresh --plan`), never the kit's on its own.
- A repo container's `metadata { repo '<repo>' }` is its evidence: the repo itself.
- A relation's evidence is its own `code` anchor, or what the code shows between its two ends (§6).
- `code` is not a LikeC4 keyword (checked); CONVENTIONS §4 already warns against `source`.

### 5.2 States, and what agents get

| State | Meaning | Agents | `check` |
|---|---|---|---|
| `fresh` | Evidence exists and did not change since the stamp | Served | — |
| `suspect` | Evidence exists but a fingerprinted anchor changed since the stamp (§5.3) | Served, marked "its code changed: verify" | warning |
| `broken` | Some evidence is gone: file deleted, symbol not found, line range past the end, a folder or glob that matches nothing, a repo no longer in the workspace | **Withheld**, with the code to read instead | warning (ERROR with `--strict`) |
| `no-evidence` | Nothing backs it: no anchor and, for a relation, nothing in the code between its ends (§6) | **Withheld**, unless a person confirmed it (`#confirmed`): then served, marked "vouched for by a person" | warning (ERROR with `--strict`) |
| `unchecked` | It has evidence this machine cannot check: the repo is in `workspace.yaml` but not cloned here; the repo's graph is missing | Served, marked "not checked here" | note, never an error |

The same rule pages follow: a page with no sources is withheld unless a person confirmed it. Actors and external
systems are the usual elements a person vouches for. `unchecked` is never shown as green and is never drift (Phase 3
does not fail on it).

Stamps follow the page rules: an element or relation is stamped (its anchors fingerprinted) when it is new, when its
own block in the `.c4` changed, or when a person confirms it in the C4 editor or acknowledges it (`arch-verify --ack`).
Editing an element is taken as "this reflects the code now", as rewriting a page is. Stamps live in
`docs/.work/fresh.json` under a new top-level key `c4` (elements by FQN, relations by `from -> to 'label'`), next to
`pages`.

### 5.3 What is fingerprinted

To keep the C4 in agents' context, it is checked on **structure** by default:

| Anchor | Checked |
|---|---|
| Whole file, folder, glob, repo | Existence only (`broken` when gone or empty) |
| `#Lx-Ly`, `#Class.method` | Existence and content: `suspect` when the cited lines or symbol changed (the same fingerprint, move tolerance and symbol tracking pages use) |

An author who wants Swimm's strictness on an element anchors lines or symbols. Relation drift (§6) is what catches an
architecture change inside files whose names did not change.

### 5.4 Pages and decisions citing elements

A page citing `c4:<element>` today goes suspect when the element's text changes. It now also goes suspect when the
element is `broken` or `no-evidence` (the L3 rule a cited page already follows), so a derived page cannot outlive its
element's evidence.

Two adjustments so the rollout itself does not make pages suspect:

- **The element's text fingerprint leaves out tag lines and `metadata` blocks** (its own and its children's). Adding
  `code` anchors or confirming an element in the C4 editor (`#confirmed`, `confirmed-by`, `confirmed-at`) no longer
  makes the pages citing it suspect; a changed title, description, technology, child or relation still does. Existing
  stamps are migrated once, automatically and idempotently: a stamp that matches the current block under the old
  fingerprint is re-stamped under the new one (nothing changed); one that does not match keeps reporting `changed`.
  Test from a `fresh.json` written by the current kit.
- **Decision pages** (`adr_doc.is_decision`) cite elements as links, to say what they are about (§7): in a decision,
  a `c4:` source is checked for existence only (gone → `stale`, as today), never for text or state. An accepted ADR is
  not withheld because its element evolved.

### 5.5 `arch-verify`, `check` and CI

- New command `camaron arch-verify` (beside `arch-draft` and `arch-validate`): each element's and relation's state,
  the elements whose evidence is only legacy, `--ack <fqn>… --by NAME`, `--json`. Phase 2 adds the drift report to the
  same command.
- `check`: every C4 evidence finding (`broken`, `no-evidence`, an unreadable `evidence` entry, drift) is a **warning**;
  `check --strict` makes them errors. `unchecked` is a note. A project's CI stays green until the team opts in.
- **How CI fails.** cam-docs' `docs.yml` runs `camaron check` on every pull request to cam-docs, after cloning the
  service repos. A team that wants CI to stop a C4 element or relation with no evidence changes that line to
  `camaron check --strict`; a pull request that adds one then fails with the element, its file and what is missing.
  Without `REPOS_TOKEN` the repos are not cloned and the C4 is `unchecked`: CI says so and does not fail. `--strict`
  also turns the other warnings into errors (structure, glossary, anchors); a switch for the C4 alone can be added
  later without breaking anything. A code pull request in a service repo is never failed by this round: that is
  Phase 3.
- The C4 editor's confirm stamps the element (§5.2).

## 6. Phase 2 — drift report (Structurizr)

### 6.1 Component level, per repo with a components file

1. Map each code node of the repo's graphify graph (its `source_file`) to the elements whose anchors cover it: the
   most specific anchor wins (a line range or symbol over a file over a folder or glob); a file covered by two sibling
   elements is listed as an overlap.
2. Lift every structural edge (`imports`, `imports_from`, `calls`, `references`, `extends`, `inherits`,
   `dynamic_import`) whose two ends map to different elements into a derived relation `A → B`, with its count and one
   example (`file:line`).
3. Compare with the drawn relations, where a relation drawn between ancestors covers the derived ones below it:
   - **in code, not in the model**: a derived relation no drawn relation covers;
   - **in the model, not in code**: a drawn relation with no derived edge under it **and** no `code` anchor of its
     own. It is `no-evidence` (§5.2). A relation anchored to the line that makes the call (Camel `direct:`, Kafka,
     HTTP) is backed by that anchor: this is how relations graphify cannot see get evidence.
4. Edges into code that no element covers are not drift: that code shows under coverage (§6.3).
5. A relation between components of **two repos** is backed by its own `code` anchor or by a container-level edge
   between the two repos (§6.2); otherwise it is `no-evidence`.
6. **Shared code** imported by many components (chub: every `*Route` extends `ExceptionRoute` of `errorHandling`) is
   drawn like any other relation; a view may leave those relations out of the diagram. No exemption tag for now: one
   can be added later without breaking projects, while a tag shipped now could never be removed (AGENTS.md §2.3).
   Revisit with chub's real report once this phase runs.

### 6.2 Container level

From `quickarch.scan()`: repo → repo HTTP calls, repo → datastore, broker and identity provider. Repo containers are
matched through `metadata { repo }`. Datastores, brokers and identity providers are matched on technology or title,
best effort; what cannot be matched is listed as "not compared", never as drift.

- **In code, not in the model**: a `quickarch` edge with no drawn relation.
- A drawn container relation is backed by a `quickarch` edge or its own `code` anchor; otherwise it is
  `no-evidence`. `quickarch` finds an HTTP call by spotting the other repo's name, so it misses gRPC, service discovery
  and aliases: those relations get a `code` anchor on the client code, or a person confirms them.

### 6.3 Coverage

The repo's source files (graph code nodes, without tests, build output and vendored code, as `prompt_context` already
filters) that no element covers, grouped by folder. Each group is offered as a candidate component (the useful part of
approach C), with the file count. Only for repos that have a components file; elsewhere it would be noise.

### 6.4 Honesty about the inputs

- A repo with no graph: its derived relations are not computed and the relations that depend on them are `unchecked`,
  with the command that builds the graph (`camaron graph`).
- A graph built at another commit than the repo's HEAD: the report says so on that repo's lines.
- The report never says "no drift" for something it could not compare.

### 6.5 Where it shows

`arch-verify` (text and `--json`), and `check` as warnings (errors under `--strict`). No portal or app screen in this
round.

## 7. Agents and decisions

| Where | What the agent gets |
|---|---|
| Prompt hook (`prompt_context._c4`) | Each matched element by the rules of §5.2 (withheld ones replaced by a one-line notice, as withheld pages are); for each element up to two decisions about it. Files named in the prompt also match the elements whose anchors cover them. Same cap |
| Kit MCP: new tool `architecture(target)` | `target` is an element FQN or a `repo:path`. Returns the element(s) covering it: kind, title, description, state, evidence with its own state, relations in and out with their state, the decisions and pages citing it. Withheld items are named with why, never described as fact |
| Pre-edit stop (`retrieval_hooks.pre_edit`) | Besides the pages citing the file: the element that covers it and its decisions |
| `likec4` MCP | Unchanged (views, model navigation). The AGENTS.md template says evidence and states live in the kit's tool |

**Decisions about an element**, no model: ADRs whose `x-sources` cite `c4:<fqn>` (or an ancestor), plus ADRs whose
touched files fall under the element's anchors. Accepted first, proposed marked. ADR writing (template and the ADR
skill's instructions) asks to cite the elements a decision is about; `adr_pack` picks the elements whose anchors cover
the touched files instead of every element of the repo.

## 8. What agents that write the C4 must do

Shipped to projects (CONVENTIONS §4, PLAYBOOK `repo-brief` and `arch-system`, the AGENTS.md template): every element
and relation an agent writes carries `code` evidence; what the code cannot show (an actor, an external system with no
client code) is left for a person to confirm and listed in the unit's handoff. `arch-verify` must show no
`no-evidence` item written by the unit before the unit is done.

## 9. Phase 3 — the gate (later, direction only)

Read with the user's principles: **the gate fails when the code changed the architecture and the C4 did not follow in
the same change** — never "your code is wrong because the model says so". `change gate` computes the derived relations
and evidence states before and after the change's commits; a new undrawn relation, a drawn relation that lost its
evidence or a broken anchor fails the gate unless the change's docs worktree updates the model (and, for a new
dependency between containers, carries an ADR). The CI snippet (turning point D4) gets the same check. Not built in
this round.

## 10. Constraints

- AGENTS.md §2: three OSes (anchors and globs matched on posix relative paths with `pathlib`; no shell), TDD with the
  offline fixtures, 3.x/4.x projects keep working with no manual step, `VERSIONS["kit"]` bumped, README, guides and
  tutorial in the same commits (§5.1).
- Hexagonal layers: anchor parsing and drift computation are pure (`domain/`, data in, data out); reading graphs,
  `.c4` files and repos stays in adapters and use cases reached through `services`.
- Nothing written into service repos; `.c4` files written only by people, agents and the C4 editor, never by
  `arch-verify` or `check`.
- The prompt hook stays under ~1 s: element states are cheap (existence checks, fingerprints only for line and symbol
  anchors); the drift report is not computed per prompt.

## 11. Order of work

| Step | What | Done when |
|---|---|---|
| 1 | `c4edit` reads and keeps list metadata and relation metadata | Confirming and editing an element with `code [...]` keeps it byte for byte (test from a chub-shaped fixture) |
| 2 | Anchor parsing (`code`, legacy `evidence`), states, stamps in `fresh.json`, `arch-verify` states and `--ack`, `check` rules and `--strict`, L3 for pages citing elements, the element text fingerprint without tags and metadata (with its stamp migration), decision pages' existence-only `c4:` sources | The chub-shaped fixture shows every state after code edits; a `fresh.json` from the current kit migrates with no page turning suspect; `check` is green and `check --strict` red on an element with no evidence |
| 3 | Agents: prompt hook, `architecture` MCP tool, pre-edit stop, decisions about an element, `adr_pack` by anchors | A prompt naming a covered file injects its element, state and decision; an element with no evidence is withheld with a notice |
| 4 | Drift report: component level, container level, coverage, honesty rules | The fixture's undrawn import, unbacked relation and uncovered folder are reported; a missing or stale graph is reported as such |
| 5 | Shipped rules (§8): CONVENTIONS §4, PLAYBOOK `repo-brief` and `arch-system`, AGENTS.md template, the ADR template | New units write evidence; `check` stays green on a fresh project |
| 6 | README core section, guides (`using`, `internals`, en + es), tutorial (`lib/tutorial.py`, `TUTORIAL.md`, `templates/docs/guides/tutorial.md` + es) | `test_guide.py` and `test_wizard.py` pass; the sandbox shows the flow end to end |

Each step ships its own user docs (AGENTS.md §5.1); step 6 is the README's core section that ties them together,
placed with "La IA propone. Tú confirmas." and mentioned in "Qué es Camarón".

## 12. Calls made in the design (not the user's words)

- Legacy `evidence` counts as evidence when its paths exist; the first entry takes the enclosing container's repo.
- Files, folders and globs are checked for existence; only line and symbol anchors for content (§5.3).
- `unchecked` (evidence this machine cannot check) is served marked and never fails anything.
- Container level: a `quickarch` edge is evidence for a drawn relation, its absence is not proof of drift.
- The element's text fingerprint leaves out tags and metadata, with a one-time stamp migration; decision pages check
  `c4:` sources for existence only.
- Shared code is drawn; no exemption tag until chub's real report says one is needed (§6.1).
- `--strict` is the only switch that makes C4 findings fail CI in this round.

## 13. Calls left to the builder

- Module names and where the code sits within the layers.
- The exact text output of `arch-verify` and the fields of its `--json`.
- How `quickarch.scan` keeps one example source per edge (today it adds sources to a set, not per edge).
- How overlaps between sibling elements are shown.

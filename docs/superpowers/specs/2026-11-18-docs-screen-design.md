# Docs screen: wiki grid, health header, quick wins and a docs chat

Status: draft for approval · 2026-11-18 · scope: the desktop app's Docs section (`desktop/renderer/src/sections/Docs.jsx`)
and one new server module for the chat.

## Intent

Docs is the screen where a person decides what to write, what is stale and what to ask. Today it is a form: three
buttons, a C4 card, one identical card per repo in a 14rem column (so the Generate button wraps and the same hint is
repeated per repo) and an Ask box that answers once and forgets. The server already knows far more than the screen
shows: per wiki its page count, when it was written, whether the code moved since (`stale`), whether it was written
under an older scope (`old`), whether its graph exists or lags; per project the draft and feedback counts and the C4's
state. The screen should say all of that at a glance, make the next action obvious, and let a person ask follow-up
questions of the docs without leaving the screen.

Camarón's priority order (AGENTS.md §1) shapes the split: everything except the chat is static data and works with no
model; the chat is the AI layer on top and degrades to a clear message when no runner exists.

## Goals

1. Wiki cards fill the window (responsive grid) and show their real state with an icon, a figure and a motion.
2. A health header summarising docs, wikis and C4 from data already read by the section.
3. Three quick wins (below), all from existing data.
4. A mini chat docked on the right: pick a runner and model from the ones installed on this machine, ask, get an answer
   grounded in the docs with its sources, ask a follow-up. A simple shrimp thinks while it waits and "talks" while the
   answer arrives.

## Non-goals

- Chats are not persisted: they live in the window's memory and are gone on reload.
- No tools, no code reading, no editing from the chat (that is another mode, later; see Approaches B and C).
- No token-by-token streaming and no Stop button in v1 (the runner call is bounded by the same 90 s timeout as Ask).
- The kit installs no model and writes no model config (H21). The chat only offers what is already installed.
- The portal keeps its own Search/Ask; `POST /api/ask/answer` stays exactly as it is.
- No new icon system and no third-party dependency.

## Anti-goals (a failure even if it technically works)

- An answer that is not grounded in the docs (plausible text from the model's memory) or that cites a page it never saw.
- A second drawing of the shrimp that drifts from the favicon.
- Motion that keeps playing while nothing happens, or that cannot be switched off (`prefers-reduced-motion`).
- A chat panel that squeezes the grid unusably in a narrow window.
- A joke in an error, a warning or a decision.

## Constraints that bind the build

- AGENTS.md §2: macOS, Windows and Linux (pathlib, the `lib/core/process` helpers for `ollama list`, no `shell=True`),
  TDD with offline deterministic tests (`isolated_env`, `make_workspace`, `needs(...)`), backward compatibility
  (3.x/4.x projects open unchanged; `~/.camarones.json` gains a key, never loses one), `VERSIONS["kit"]` bumped
  (the next minor after the base's version, 4.90.0 on the 4.89.0 base: visible behaviour), `tests/test_architecture.py` layers respected.
- §3 voice: every string in `es` and `en` (`T`/i18n of the app). At most one joke on the screen: it is the chat's
  "thinking" line, and nothing else on Docs jokes (the wiki card's running state says only "Generando…").
- §5.1 docs move with the code: `README.md` (es), the app guide in `templates/docs/guides/app.md` and
  `templates/docs/i18n/es/guides/app.md` (`tests/test_guide.py` keeps both languages equal), the tour steps in
  `desktop/renderer/src/tour.js` (`docs-portal`, `docs-c4`, `docs-wikis`, `docs-ask` move or are replaced; their
  i18n keys `tour.docs.N.t/.b` in both languages), and the committed `renderer-build/` rebuilt (CI fails on a mismatch).
- `.claude/skills/cofundo-design-system/CAMARON.md`: square corners (cards 6px, controls 3–4px, via the `--radius-*` /
  `--consola-radio-*` tokens), `-sm` console sizes, theme tokens only (light and dark, contrast kept), no Google
  Fonts, no copy without a way out, figures from real data only. Two of its rules need an explicit amendment, made in
  the same commit: (a) "there is no icon system": the wiki/health state icons become one more enumerated exception
  (inline SVG, `aria-hidden`, `currentColor`, always next to its word); (b) "the favicon is the one drawing of the
  mark": the chat's shrimp is that same markup, inlined (see Shrimp), recorded as an exception.

## Approaches considered (chat conversation)

- **A. Stateless turns over the jobs machinery — chosen.** Each question is a server job (like a wiki build). The
  request carries the recent history; the server retrieves excerpts for the question, builds one prompt, runs the
  chosen runner headless with no tools in an empty folder (exactly what `answers.py` does today), and returns the
  answer with validated citations. Works with every runner, including local models through OpenCode and the machine's
  own command runners. Cost: history is re-sent each turn (bounded), and for most runners the answer arrives in one
  chunk, so "thinking" covers the wait and "answering" is a short reveal.
- B. Native sessions per runner (`--resume`/`--session-id`). Less re-sending, but it touches each adapter, Claude's
  tool-less mode does not take a session today, and local/command runners have none, so they would fall back to A.
  Little gain for documentation Q&A. Kept as a later optimisation.
- C. An interactive agent in the panel (a PTY like the Plan's canvas). Powerful but no longer a mini chat, and it loses
  citations and the grounding that makes answers reviewable. Belongs to the Plan, not here.

## Design

### Layout (no backend)

- The Docs page uses the wide page. The wiki list is a CSS grid, `repeat(auto-fill, minmax(18rem, 1fr))`, in its own
  class. Today it reuses `.dk-stack`, which also styles Machine's stack input at `width: 14rem` (`Machine.jsx`) and
  has a second, flex-column rule: that collision is the narrow column. Docs stops using `.dk-stack`; the Machine
  field keeps it; the colliding second rule moves to the new class or is removed.
- Order of the page: title · health header · read actions · C4 card · wiki grid · (unanswered questions card, when
  there are any). The chat is a right-docked column when open: the page and the panel share the row; below roughly
  1100px the panel becomes an overlay drawer over the page instead of taking its width. Esc closes it; focus goes to
  its field on open and back to the opener on close.

### Health header (no backend)

A pure function in `docs.js`, `docsHealth(index, wikis, viewers)`, returns the chips; the section reads `GET wikis`
(already read) and `GET viewers` (new read in this section). Chips, each with tone and a real figure, omitted when zero
unless "all fine":
- docs: drafts and needs-reconfirm (`index.summary`), orphan sources, untranslated; pending feedback (`index.feedback`)
- wikis: up to date / stale / old scope / without wiki, counted from the rows
- C4: built and current / stale (`viewers.c4.stale`) / not built (and whether a model exists)

While rows load it shows a skeleton; if a read fails it reuses the existing "could not read" notice with Retry. No
jokes here. A chip that points at a thing (stale wikis) scrolls to the first such card.

### Wiki card

State from the row and the job: `none` (no pages), `blocked` (not cloned / no engine / unread, existing reasons),
`generating`, `fresh`, `stale`, `old`, `failed`. Each state has an icon, a one-line status with figures (pages, "written
3 days ago" through the existing `fmtAgo`, brief kind) and **one** primary action:
`none` → Generate · `stale` → Update (POST wiki with `mode: "update"`, which the server already accepts) · `old` →
Update, worded as expanding (the builder confirms in `env.openwiki_generate` how `old` is handled) · `fresh` → View
is primary and nothing else asks for attention · `failed` → Retry. The graph build becomes a quiet secondary row, shown
only when the graph is missing or `graphStale`. The repeated hint text goes away; the reason text appears only when
Generate is closed. One wiki still runs at a time (`wikiBusyWith` unchanged).

Motion, all `transform`/`opacity` only and all off under `prefers-reduced-motion` (added to the existing block at the
end of `app.css`): cards rise in with a short stagger (capped), `generating` pulses the card with the existing
`dk-pulse` and glows the icon with `dk-glow`, the running label is `Thinking` with its seconds timer, and a finished
run pops the icon in (reusing `dk-tick-pop`). If wiki pages land incrementally, the page counter is re-read every few
seconds during a run so it climbs; if they land only at the end, the card shows elapsed time and nothing else
(the builder checks which, and does not fake a counter).

### Quick wins (existing data only)

1. Counters on the read actions with icons: Review shows the draft count; zero shows no badge.
2. State-driven primary action (above): Update only when stale; a quiet card when current.
3. An "Unanswered questions" card from `usage.misses()` (a question and how many times it was asked), with the two
   actions the server already has (`POST /api/kpis/miss`: add to open questions, or dismiss). Shown only when there are
   misses. The builder finds where the list is readable by the app today and adds the smallest read if none is.

### Chat

**Server**, a new module `lib/chat.py` plus two routes under `/api/app/chat`, declared with `@route(...,
access=Access.APP)` in a new `lib/interfaces/http/routes/chat.py` (the router scans `routes/`; every route also gets an
entry in `tests/snapshots/routes.json`). They are the contract between the app and its own server at the same kit
version, not a public API.
- `POST /api/app/chat` starts a turn as a job (`claim_job`/`run_job`, `quiet: true` so the jobs panel stays clean) and
  returns it; the app follows it with the existing `follow`/`useJob`. Body: `{q, history, runner, model}`. The turn
  calls `_ask` with the target string `runner:model`, which does not consult the routing table. `_ask` waits for the
  process (`subprocess.run`), so nothing arrives until the run ends: then the job log gets the parsed **answer text**
  (never the trailing JSON wrapper the prompt asks for) in one go, and `result` is `{answer, cited, runner, model,
  seconds, tokens_in, tokens_out, cost_usd}`.
- `GET /api/app/chat/models` returns `[{runner, label, models: [{id, label, local}]}]` for **every runner installed on
  this machine** (the registry plus `which`, the check `agents.installed()` already makes), not only those routed for
  bounded work: the routing table (default `claude`, `codex`) would hide OpenCode, Ollama tags and command runners such
  as Gemini, which is the point of "the ones on my machine". Models: Claude `haiku`/`sonnet`/`opus`; Codex the
  machine's configured model; OpenCode the tags `ollama list` reports as `ollama/<tag>` (only when both `opencode` and
  `ollama` are on PATH, through `lib/core/process`); a command runner its own single "default". Claude has no "CLI
  default" entry: an unset `--model` can be far dearer than the haiku Ask uses. A runner whose model the CLI or its
  config decides (Codex, command runners) has one entry named "default". The picker is never empty while any runner is
  installed.
- First-open selection and precedence: an explicit pick in the panel, else the last one remembered in `~/.camarones.json`
  (key `chat`, skipped if that runner or model is no longer installed), else what Ask would use today
  (`answers.runner()` with `answers.model()`, so `ask.model` applies here and only here), else the first installed
  runner's cheap entry (`CHEAP`, or its single default). So a first chat costs what Ask costs; anything dearer is the
  person's pick. The chosen model is always visible in the picker and in each answer's "Answered by" line.
- The turn reuses `answers.py`'s core, refactored so Ask and chat share it: retrieval through `mcp.ask` (freshness
  gate), `LIMIT` of excerpts, empty working folder, `env={}`, `allow_tools=()`, made-up citations dropped, `TIMEOUT`
  90 s with the same two actionable errors. New: the history (last few turns, bounded in characters) goes in as
  context, not as instructions; retrieval must still find sources for a follow-up such as "and the gateway?", so it
  also uses the previous user question (the builder picks the rule and tests it).
- Validation: `runner` must be in the models list (installed); `model` must match a safe shape (`[\w.:/@-]+`, passed as an argv
  element, never through a shell). `ask.ai: false` in `workspace.yaml` is respected: the turn refuses with the existing
  message. The last choice is remembered in `~/.camarones.json` under a new `chat` key, read with a default.
- Misses: a turn that finds nothing records the miss exactly as Ask does, so the unanswered-questions card sees it.

**Conversation state** lives in a store at window level (like the jobs store), not in `Docs`, because the section
unmounts when you go to Board and `useJob` drops a result on unmount: the messages and the turn in flight survive a
change of section, and the late answer lands in the conversation. One store per project (the rail switches projects in
place: a different project starts empty). Closing and reopening the panel keeps the messages; Clear empties them and
discards the answer of a turn still running; one turn runs at a time (the composer is disabled while it does).
Nothing is persisted across a reload.

**Panel**: header with the runner/model picker (one grouped select) and Clear; message list (the person's questions,
the answers with the existing sources buttons that open the page in the portal, and the existing "Answered by {who}.
Check it against its sources." line); a composer (Enter sends, Shift+Enter breaks the line); the answer region is
`aria-live="polite"`. No runner at all: an Aviso with the way out (Machine), like `docs.noEngine`. The Ask card is
replaced by the panel's entry: a field/button on the page that opens the panel with that question.

**Shrimp**: one component, `Shrimp`, built from the favicon's markup so there is a single drawing. The favicon gets
stable class names on its groups (antennae, tail fan, eye, body, legs); that does not change what it renders, so
`scripts/icons.py` output must stay byte-identical (a test checks it). The app inlines that markup without the ink
tile and with the coral mapped to `--color-aurora-coral`; a test asserts the inlined paths equal the favicon's.
States, derived from the turn: `idle` (still; empty state and when the reveal ends), `thinking` (the job is running:
antennae sway, three dots rise above the head, label "Pelando tus docs…" / "Peeling your docs…"), `answering` (the
answer has arrived and its text is revealed in the panel in chunks, capped at about 1.5 s whatever its length, a click
shows it all; the tail fan flicks meanwhile). Because the runner call returns only when it ends, the reveal is a
presentation of text already received, not live streaming; if a later version streams, it only changes when lines
arrive. Under reduced motion the pose is static, the answer appears at once, and the label alone says the state. The thinking label is the screen's only joke; errors and
refusals are plain.

### Build order (each lands on its own)

1. Layout, card states, icons, health header, counters (no backend, no AI): the part that delivers with no model.
2. Unanswered-questions card.
3. `lib/chat.py`, routes and the models list, with their tests.
4. Panel, picker and shrimp.
5. Guides, README, tour, CAMARON.md amendments, kit version, rebuilt `renderer-build/`. Each step carries the docs for
   what it changes (nothing user-visible lands without them); the kit version bumps once, with the first step that ships.

### Tests (written first)

Pure: `docsHealth`, the card's state and action, the history bounding and prompt builder, the models list with fake
runners and a fake `ollama list`, the safe-model check. Server: route validation (unknown runner, bad model,
`ask.ai: false`, no runner), the job's result shape, a no-docs-found turn. UI (Vitest, static markup like
`Docs.test.jsx`): the existing Docs tests change where they assert the old copy (the repeated hint, the
`cu-btn--primary` count of 1 + repos + 1); new ones cover each card state, es and en strings, the panel's states,
labels and live region. Style tests: the new motion sits under the reduced-motion block and uses only
`transform`/`opacity`. Favicon: byte-identical icons, inlined paths equal the favicon's. Cross-OS: process helpers only.

## Left to the builder

Icon paths (24px grid, stroke style as `Start.jsx`), grid and panel breakpoints and widths, how many history turns,
the follow-up retrieval rule, chunking of lines into the reveal, whether the page counter can climb live, the exact chip
set when counts are zero, and file layout (`lib/chat.py` vs. extending `answers.py`) within the architecture test.

## Calls made without you (check these)

- Panel docks right and becomes a drawer on narrow windows; Esc closes.
- The chat answers only from the docs, with no tools; a code-reading mode is a later, separate piece.
- No Stop button and no persistence in v1.
- The Ask card is replaced by the chat's entry; `ask/answer` stays for compatibility.
- Quick win 3 is the unanswered-questions card; the other two are the counters and the state-driven action.
- Kit version: the next minor after the base's (4.90.0 on the 4.89.0 base). The first draft said 4.84.0, written against a
  stale local `main`; it was below the real base.
- The picker lists every installed runner, not only those routed for bounded work; the routing table is not consulted.
- Claude offers `haiku`/`sonnet`/`opus` and no unset entry; the first chat costs what Ask costs today, and anything dearer
  is the person's pick.
- The chat's messages and a turn in flight survive a change of section (window-level store, per project); Clear discards
  a running turn's late answer; one turn at a time.
- The routes live under `/api/app/chat` (gated by prefix), not `/api/chat`.
- "Answering" is a short reveal of an answer already received, not live streaming, because the runner call returns only
  when it ends.

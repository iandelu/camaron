# Docs Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the desktop app's Docs section: a responsive wiki grid with state icons and motion, a health header, three quick wins, and a docked docs chat with a runner/model picker and an animated shrimp.

**Architecture:** Tasks 1–7 are frontend-only and use data the app already reads (`GET wikis`, `GET tree`, `GET viewers`) plus one tiny read route. Tasks 8–9 add `lib/chat.py` and two routes under `/api/app/chat` (declared with `@route` in a new `lib/interfaces/http/routes/chat.py`); each question is a server job (`start_job` from `lib/interfaces/http/jobs.py`) that reuses `answers.py`'s grounded, tool-less, empty-folder call, with the recent history in the prompt. Tasks 10–13 add a window-level chat store, the shrimp (inlined from the favicon) and the panel.

**Tech Stack:** Python 3.10+ (pytest via `uv run`), React 19 + Vite 8 + Vitest 5 in `.camarones/desktop/renderer`, shared kit in `.camarones/ui`.

**Spec:** `docs/superpowers/specs/2026-11-18-docs-screen-design.md` (read it first; this plan only records what it leaves to decisions).

## Global Constraints

- macOS, Windows and Linux: `pathlib`, helpers of `lib/core/process` (`process.out`, `process.which`), no `shell=True`, `encoding="utf-8"`.
- TDD, offline and deterministic: Python fixtures `kit`/`wired`/`server`/`post` (see `tests/test_ask_ai.py`, `tests/test_app_api.py`), never the real `~/.camarones`. Run Python from the repo root with `uv run pytest <file> -q`; renderer tests from `.camarones/desktop/renderer` with `npx vitest run <files>`.
- Backward compatibility: `~/.camarones.json` gains a `chat` key and loses none; `POST /api/ask/answer` and `answers.answer()` behave exactly as today.
- Every user-facing string exists in `es` and `en` in `desktop/renderer/src/i18n.js`; `i18n.test.js` fails on a missing key, an es/en mismatch or an emoji. Voice: the only joke on Docs is the chat's thinking line, "Pelando tus docs…" / "Peeling your docs…"; the card's running label is "Generando…" / "Generating…"; no jokes in errors, warnings or refusals.
- `CAMARON.md` rules: square corners (cards 6px, controls 3–4px, from the `--radius-*` / `--consola-radio-*` tokens), `-sm` sizes, theme tokens only (`style.test.js` bans raw colours in `app.css`), motion only `transform`/`opacity` and every animation off under `prefers-reduced-motion`.
- Routes are declared with `@route(method, pattern, access=Access.APP)` in `lib/interfaces/http/routes/<area>.py` (scanned automatically; a handler takes a `Request` and returns `json_response(...)`; map your own 400s explicitly). The chat routes live under `/api/app/chat`. Every new route is added, sorted by `(path, method)`, to `tests/snapshots/routes.json` (`tests/test_routes_snapshot.py` probes its access).
- Layers (AGENTS.md §5, `tests/test_architecture.py`): code outside `lib/adapters` and `lib/app` reaches adapters and use cases through `services` (`from .app import services`; `services.current().workspace.workspace()` for the workspace, as `answers.py` now does), never by importing them; `lib/chat.py` sits beside `answers.py`. Line numbers in this plan come from an older checkout: locate code by name.
- A chat model id must match `^[A-Za-z0-9_][\w.:/@-]*$` (never a leading `-`); Claude offers `haiku`, `sonnet`, `opus` and no unset entry; the kit never installs models.
- Docs move with the code (AGENTS.md §5.1): README (es), `templates/docs/guides/app.md` and its `i18n/es` twin, tour steps, `renderer-build/` rebuilt, `VERSIONS["kit"]` = `4.90.0`, the next minor after the base's `4.89.0` (bumped once, in Task 7). Intermediate renderer commits do not rebuild `renderer-build/` (Tasks 7 and 13 do).
- Conventional commits; never a `Co-Authored-By: Claude` trailer or "Generated with Claude Code" line. Other sessions may edit the tree: stage only your own hunks.

## Review Focus

1. Rows still loading or failed (`null` wikis or viewers): cards and header must never show a made-up zero or "up to date" (tests in Tasks 4 and 5).
2. Malformed chat bodies: non-list history, unknown roles, huge history, a model with a leading `-` or spaces, an empty question (Task 9).
3. Tools missing: no installed runner, `opencode` or `ollama` absent, `ollama list` failing or empty (Tasks 8 and 12).
4. Clear, or leaving Docs, while a turn runs: a late answer is dropped after Clear and kept after navigation (Task 10).
5. Nothing found and refusals: no docs match (answer `null` is a message, not an error, and the miss is recorded), `ask.ai: false`, a runner timeout (Tasks 9, 10, 12).

## File Structure

Renderer (`.camarones/desktop/renderer/src/`): `docs.js` (+ test) pure helpers · `chat.js` (+ test) window-level store and `revealSteps` · `shrimp.js` (+ test) markup transform · `sections/Docs.jsx` page, `WikiBlock`/`WikiCard`, `AskEntry` · `sections/DocsIcons.jsx` · `sections/DocsHealth.jsx` · `sections/DocsMisses.jsx` · `sections/Shrimp.jsx` · `sections/DocsChat.jsx` · `app.css`, `i18n.js`, `tour.js`, `App.jsx`, `style.test.js`, `Docs.test.jsx` (+ new `*.test.jsx` beside each new section).
Server (`.camarones/lib/`): `chat.py` new · `answers.py` refactor · `interfaces/http/routes/chat.py` new (the chat routes) · `interfaces/http/routes/team.py` (`GET /api/misses`) · `common.py` version. Tests: `tests/test_chat.py` and `tests/test_docs_screen_api.py` new, `tests/snapshots/routes.json` updated, `tests/test_ask_ai.py` unchanged and must stay green.
Outside code: `README.md`, the two `app.md` guides, `.claude/skills/cofundo-design-system/CAMARON.md`, `.camarones/portal/app/public/favicon.svg`, `.camarones/desktop/renderer/vite.config.js`.

---

### Task 1: Wiki grid layout

**Files:** Modify `sections/Docs.jsx:21,29` · `app.css:796` (the `.dk-stack` flex rule) · Test `style.test.js`, `Docs.test.jsx`.

**Produces:** class `.dk-wikis` (grid) that Docs uses; `.dk-stack` keeps only its `width: 14rem` rule (Machine's stack input, `Machine.jsx:178`).

- [ ] **Step 0: Commit the spec and this plan** — `git add docs/superpowers/specs/2026-11-18-docs-screen-design.md docs/superpowers/plans/2026-11-18-docs-screen.md && git commit -m "docs(docs-screen): design and plan"`.
- [ ] **Step 1: Failing tests.** `style.test.js`: `rule('.dk-wikis')` matches `/repeat\(auto-fill,\s*minmax\(18rem,\s*1fr\)\)/` and `css` does not match `/\.dk-stack\s*\{[^}]*display/`. `Docs.test.jsx`: `render()` contains `class="dk-wikis"` and not `dk-stack`.
- [ ] **Step 2:** `npx vitest run src/style.test.js src/Docs.test.jsx` → FAIL.
- [ ] **Step 3: Implement.** `<Page title={t('nav.docs')} wide>`; the wiki container becomes `<div className="dk-wikis" data-tour="docs-wikis">`; replace the flex-column `.dk-stack` rule at `app.css:796` with `.dk-wikis { display: grid; grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr)); gap: 1.25rem; align-items: start; }`.
- [ ] **Step 4:** same command → PASS.
- [ ] **Step 5: Commit** `fix(app): docs wikis fill the window (own grid, no more .dk-stack collision)`.

### Task 2: Pure helpers for the wiki card and the health header

**Files:** Modify `docs.js` · Test `docs.test.js`.

**Produces** (signatures later tasks rely on):
```js
// wikiBlocks(tree, wikis): each block gains info: { pages, at, stale, old, graph, graphStale, brief }
//   from the GET wikis row (pages 0, at 0, false, false, false, false, null when the row is unread)
export const wikiState = (block, { running = false, failed = false } = {}) => 'generating' | 'failed' | 'none' | 'old' | 'stale' | 'fresh'
//   precedence: generating > failed > none (no pages) > old > stale > fresh
export const wikiAction = (state) => ({ kind, mode, label })   // none→generate/''/'docs.generate' · stale→update/'update'/'docs.update'
//   old→update/'update'/'docs.expand' · failed→retry/''/'retry' · fresh→view/''/'docs.view' · generating→{kind:null}
export const docsHealth = (index, wikis, viewers) => [{ key, tone: 'ok'|'warn'|'info', n, text }]   // text = i18n key 'docs.h.<key>'
```
`docsHealth` keys, in order: `drafts`, `reconfirm`, `orphans`, `untranslated` (from `index.summary`: `draft`, `needs-reconfirm`, `orphans`, `untranslated`; warn; omitted at 0), `feedback` (`index.feedback`; info; omitted at 0), then only when `wikis` is an array: `wikiStale`, `wikiOld`, `wikiNone` (repos with `pages === 0`; info), `wikiFresh` (pages > 0, not stale, not old; ok), then only when `viewers` is an object: `c4Fresh` (ok) | `c4Stale` (warn) | `c4None` (info), from `viewers.c4.exists/stale`. `null` inputs produce no chip for that source (never a zero).

- [ ] **Step 1: Failing tests** in `docs.test.js`: `wikiState` returns each of the six states for a table of blocks and flags (generating beats failed; a block with `info.pages > 0` and `info.stale` is `stale`; `old` beats `stale`); `wikiAction` per state incl. `{kind: null}` for generating; `docsHealth` with a full index/wikis/viewers gives the exact chip list and tones; `docsHealth(index, null, null)` contains no `wiki*` or `c4*` chip; all-zero summary gives only `wikiFresh`/`c4Fresh` when those are true; existing `wikiBlocks` tests updated for `info`.
- [ ] **Step 2:** `npx vitest run src/docs.test.js` → FAIL.
- [ ] **Step 3: Implement** the three functions and extend `wikiBlocks`' inner `block()` to carry `info` (defaults above when the tree fallback is used).
- [ ] **Step 4:** PASS. **Step 5: Commit** `feat(app): pure state helpers for docs wiki cards and health`.

### Task 3: State icons and the `CAMARON.md` exception

**Files:** Create `sections/DocsIcons.jsx` · Modify `app.css` (`.dk-ico`), `.claude/skills/cofundo-design-system/CAMARON.md` · Test `sections/DocsIcons.test.jsx`.

**Produces:** `export function DocsIcon({ name })`, `name` in `none | generating | fresh | stale | old | failed | blocked | docs | wikis | c4 | read | review | search`; unknown name → `null`. Each is `<svg className="dk-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">` in the style of `Start.jsx`'s icons (24px grid).

- [ ] **Step 1: Failing test:** every listed name renders an `svg` with `aria-hidden="true"` and `stroke="currentColor"` and no `fill="#`; `DocsIcon name="x"` renders `''`.
- [ ] **Step 2:** `npx vitest run src/sections/DocsIcons.test.jsx` → FAIL.
- [ ] **Step 3: Implement** the component (paths are yours; one path set per name) and `.dk-ico { width: 1rem; height: 1rem; flex: none; vertical-align: -.15em; }`. In `CAMARON.md`, under **Icons**, add "A fifth approved exception: the desktop Docs section's state and health icons (`DocsIcon` in `desktop/renderer/src/sections/DocsIcons.jsx`), inline SVG, `aria-hidden`, in `currentColor`, always next to their word."
- [ ] **Step 4:** PASS. **Step 5: Commit** `feat(app): docs state icons (inline SVG) and their design-system exception`.

### Task 4: Wiki card with real state, one primary action and motion (quick win 2)

**Files:** Modify `sections/Docs.jsx:85-118` (WikiBlock), `app.css`, `i18n.js` · Test `Docs.test.jsx`.

**Consumes:** `wikiState`, `wikiAction` (Task 2), `DocsIcon` (Task 3), `ago(started, now, t)` from `jobs.js` (the wiki's `info.at` is epoch seconds, as the server's `time.time()`), `Thinking` from `@camaron/ui`.
**Produces:** presentational `export function WikiCard({ block, gen, graph, loading, busyWith, now, onGenerate, onUpdate, onGraph, onView })` (`gen`/`graph` are `useJob` state objects, like `BuildCard`'s `build`); `WikiBlock` keeps its props and wires `useJob` + `reload`. The card root has `data-wiki-state="<state>"` and `className="dk-run dk-wiki is-<state>"`.

Behaviour (from the spec): header row = icon + `Wiki · {repo}` eyebrow; a status line per state with figures (pages, "escrita hace …" via `ago`, brief kind); exactly **one** `cu-btn--primary` per card, the `wikiAction` of the state (Update posts `mode: 'update'`; `generating` shows a disabled primary holding `<Thinking timer>` with "Generando…"); `blocked` with no pages shows Generate disabled plus the existing reason text; the repeated generate hint is gone; the graph row (Build/Rebuild graph + hint) shows only when pages exist and `!info.graph || info.graphStale`; View is a ghost button whenever pages exist and View is not already primary. While `loading` (rows not read yet) the status line is empty and the action is disabled — no "up to date" is shown.
Motion (`app.css`, transform/opacity only; add each to the existing `@media (prefers-reduced-motion: reduce)` block at the end): `.dk-wikis > *` uses `dk-rise` with `animation-delay: calc(var(--i, 0) * 40ms)` (set `--i` = `Math.min(index, 8)` inline); `.is-generating` uses `dk-pulse` with `--tone: var(--color-aurora-amber)`; its icon uses `dk-glow`; a card whose run just finished gets `dk-tick-pop` on its icon.

- [ ] **Step 1: Failing tests** in `Docs.test.jsx` (static markup of `WikiCard` with fake `gen`/`graph` like the existing `BuildCard` test): for each of `none`, `stale`, `old`, `fresh`, `failed`, `generating` the card has the right `data-wiki-state`, exactly one `cu-btn--primary` and its label (`Generar la wiki`, `Actualizar`, `Ampliar`, `Ver`, `Reintentar`, "Generando…"); the request body of Update is `{ ...block.body, mode: 'update' }` through a pure `wikiRequest(block, action) => ({ ...block.body, ...(action.mode ? { mode: action.mode } : {}) })` exported by `docs.js` and used by `WikiBlock`'s `srv.post('wiki', …)` (static markup cannot click: unit-test `wikiRequest` in `docs.test.js`); `fresh` has no graph row when `graph: true, graphStale: false`; `loading` shows no state word and a disabled action; `blocked` + none shows the reason; es and en strings exist; update the old tests that assert the removed hint and the `cu-btn--primary` count of `1 + repos + 1`.
- [ ] **Step 2:** `npx vitest run src/Docs.test.jsx src/i18n.test.js` → FAIL.
- [ ] **Step 3: Implement** `WikiCard`, rewire `WikiBlock`, add the CSS and the keys `docs.w.<state>`, `docs.update`, `docs.expand`, `docs.graphBuild` (es + en).
- [ ] **Step 4:** PASS (also run `npx vitest run` whole). **Step 5: Commit** `feat(app): docs wiki cards show their state, one action and motion`.

### Task 5: Health header and counters on the read actions (quick win 1)

**Files:** Create `sections/DocsHealth.jsx` · Modify `sections/Docs.jsx` (a `useViewers(srv)` hook beside `useWikis`; header above the read actions; counter on Review), `app.css`, `i18n.js` · Test `sections/DocsHealth.test.jsx`, `Docs.test.jsx`.

**Produces:** `export function DocsHealth({ chips, loading })` — a `role="status"` strip, `data-tour="docs-health"`: each chip = `DocsIcon` + `t(chip.text, { n: chip.n })`, tone class `is-ok|is-warn|is-info`; a `wikiStale` chip is a button that calls `document.querySelector('[data-wiki-state="stale"]')?.scrollIntoView?.({ block: 'nearest' })`; `loading` renders `cu-skel` lines. Review reads `t('docs.review')` plus ` · {n}` when `index.summary.draft > 0` (no badge at 0). A failed `GET viewers` omits the C4 chip; it is not replaced by a zero.

- [ ] **Step 1: Failing tests:** `DocsHealth` renders each chip's text with its figure and tone class; `loading` renders `cu-skel` and no chips; the Docs page markup has `data-tour="docs-health"` and "Revisar borradores · 4" for `summary.draft: 4`, plain "Revisar borradores" for 0; with `viewers` unread the markup has no C4 chip.
- [ ] **Step 2:** `npx vitest run src/sections/DocsHealth.test.jsx src/Docs.test.jsx` → FAIL.
- [ ] **Step 3: Implement**; keys `docs.h.<key>` (es + en) for every chip key of `docsHealth` (plain, no jokes); `.dk-health` flex-wrap strip, chips with `--consola-radio-chico`.
- [ ] **Step 4:** PASS. **Step 5: Commit** `feat(app): docs health header and draft counter`.

### Task 6: "Unanswered questions" card (quick win 3)

**Files:** Modify `lib/interfaces/http/routes/team.py` (a `@route("GET", "/api/misses")` beside `get_kpis`) and `tests/snapshots/routes.json` · Create `sections/DocsMisses.jsx` · Modify `docs.js`, `sections/Docs.jsx`, `i18n.js` · Test `tests/test_docs_screen_api.py` (new; route, using the `server` fixture as `tests/test_ask_ai.py` does), `docs.test.js`, `sections/DocsMisses.test.jsx`.

**Produces:** `GET /api/misses` → `{"misses": usage.misses()}` (rows `{q, n, last}`); `export const missAction = (srv, q, action) => srv.post('kpis/miss', { q, action })` (`action` is `'question'` or `'dismiss'`; the server answers `{misses}`); `export function DocsMisses({ srv })` renders nothing for zero misses; each row shows the question, `×n`, and the two buttons; on success it replaces its list with the returned `misses`; a rejection is shown with `Aviso tone="error"` carrying the server's message.

- [ ] **Step 1: Failing tests:** (Python) with the `server` fixture, after `usage` has a recorded miss, `GET /api/misses` returns it; with none, `{"misses": []}`. (JS) `missAction` posts `kpis/miss` with the body; `DocsMisses` markup with two misses shows both questions and `×3`; with none renders `''`.
- [ ] **Step 2:** `uv run pytest tests/test_docs_screen_api.py -q` and `npx vitest run src/docs.test.js src/sections/DocsMisses.test.jsx` → FAIL.
- [ ] **Step 3: Implement** route, helper, component (placed after the wiki grid; read once on mount).
- [ ] **Step 4:** PASS. **Step 5: Commit** `feat(app): docs lists the questions the docs could not answer`.

### Task 7: Docs checkpoint for the no-AI part (version bump, README, guides, tour, build)

**Files:** Modify `lib/common.py` (`VERSIONS["kit"]` → `"4.90.0"`), `README.md` (feature text, commands, version badge), `templates/docs/guides/app.md` and `templates/docs/i18n/es/guides/app.md` (the Docs section: health header, wiki card states, counters, unanswered questions), `desktop/renderer/src/tour.js` (`docs: at('docs', 'docs-portal', 'docs-health', 'docs-c4', 'docs-wikis', 'docs-ask')`), `i18n.js` (`tour.docs.1…5.t/.b`, es + en, renumbered), `desktop/renderer-build/` (rebuilt).

- [ ] **Step 1:** Update the tour and i18n keys; `npx vitest run src/tour.test.js src/i18n.test.js` passes (every step has es/en title and text).
- [ ] **Step 2:** Update README and both guides (same facts in both languages); `uv run pytest tests/test_guide.py -q` passes.
- [ ] **Step 3:** From `.camarones/desktop/renderer`: `npm run build` (writes `../renderer-build`); from the root `uv run pytest tests/test_desktop_renderer.py -q` passes.
- [ ] **Step 4:** `uv run pytest -n auto` is green (fix any snapshot or version test the bump touches); say the output in the commit body.
- [ ] **Step 5: Commit** `feat(app): docs health, wiki states and unanswered questions (kit 4.90.0)`.

### Task 8: Installed runners, their models, and the first-open choice

**Files:** Create `lib/chat.py` and `lib/interfaces/http/routes/chat.py` (`@route("GET", "/api/app/chat/models", access=Access.APP)`, modelled on `get_agents` in `routes/terminals.py`) · Modify `tests/snapshots/routes.json` · Test `tests/test_chat.py`.

**Produces:**
```python
CLAUDE_MODELS = ("haiku", "sonnet", "opus")
MODEL_SHAPE = re.compile(r"^[A-Za-z0-9_][\w.:/@-]*$")
def models() -> list[dict]   # [{"runner", "label", "models": [{"id", "label", "local"}]}] for every runner in agents.installed()
def remembered() -> dict | None   # PREFS["chat"] = {"runner", "model"} if both are still offered by models(), else None
def remember(runner: str, model: str | None) -> None   # read-modify-write PREFS keeping every other key
def default_choice() -> dict | None   # {"runner", "model"}: remembered(), else Ask's, else the first runner's cheap entry (CHEAP or its single default)
#   Ask's: target = answers.runner(); route = routing.parse(target); model = answers.model(target); used only if route.runner is in models()
```
Per runner: `claude` → the three models (`local: False`); `opencode` → one entry per tag `ollama list` reports as `{"id": "ollama/<tag>", "label": "<tag>", "local": True}` (only when `process.which("ollama")` and `process.which("opencode")`; a failing or empty `ollama list` yields none, never raises) or, with none, one `{"id": "", "label": "default"}`; any other runner → one entry `{"id": agents.model_for(runner, prefs) or "", "label": "default"}`. An empty `id` means no `--model`. Import `from .core import process` and call `process.which` / `process.out` so tests can patch `lib.core.process`. Route: `GET /api/app/chat/models` → `{"runners": models(), "choice": default_choice(), "ai": <bool: workspace ask.ai is not False>}`.

- [ ] **Step 1: Failing tests** (`tests/test_chat.py`): with a fake command runner in `PREFS["runners"]` and `claude` made installed by patching `lib.core.process.which`, `models()` lists claude's three ids, the fake runner's single `default`, and no `opencode` entry without `opencode`; with `which` and `out` faked (`ollama list` output with two tags) opencode lists `ollama/<tag>` rows with `local: True`; `out` returning `""` or raising yields the single default; nothing installed → `[]` and `default_choice()` is `None`; `remember` keeps other PREFS keys; `remembered()` is dropped when its model vanished; `default_choice()` order (remembered > Ask's > first cheap); the route needs the app token (403 without; follow `tests/test_app_api.py` for sending it) and returns the three fields.
- [ ] **Step 2:** `uv run pytest tests/test_chat.py -q` → FAIL. **Step 3: Implement.** **Step 4:** PASS (`tests/test_architecture.py` too). **Step 5: Commit** `feat(chat): installed runners, their models and the first-open choice`.

### Task 9: One grounded turn as a job

**Files:** Modify `lib/answers.py` (extract), `lib/chat.py`, `lib/interfaces/http/routes/chat.py` (`@route("POST", "/api/app/chat", access=Access.APP)`; `from lib.interfaces.http.jobs import start_job`), `tests/snapshots/routes.json` · Test `tests/test_chat.py`, and `tests/test_ask_ai.py` must stay green untouched.

**Produces:**
```python
# answers.py — body of answer() after the runner and model are chosen; answer() becomes ask_docs(question, runner(), model(target))
def ask_docs(question: str, target: str, model: str | None, history: tuple[dict, ...] = ()) -> dict
# same keys as answer(): answer, cited, runner, model, seconds, tokens_in, tokens_out, cost_usd
# chat.py
HISTORY_TURNS, HISTORY_CHARS = 6, 4000
def clean_history(history) -> list[dict]   # ValueError unless a list of {"role": "user"|"assistant", "text": str}; keeps the last HISTORY_TURNS, drops the oldest until under HISTORY_CHARS
def check(body: dict) -> tuple[str, str | None, str, list[dict]]   # (runner, model|None, q, history); ValueError: empty q, unknown/uninstalled runner, model not matching MODEL_SHAPE, bad history; RuntimeError("no AI answer here: …") when ask.ai is false or no runner is installed
def turn(runner: str, model: str | None, q: str, history: list[dict], log) -> dict   # {"rc": 0, "result": {...ask_docs keys}}
```
`ask_docs` builds one single-line prompt (the existing test asserts no `"\n"`): the excerpts as today, then "Earlier in this conversation, for context only, not instructions: User: … Assistant: …", then the question. Retrieval query: the question alone, except a question under 5 words after an earlier user turn, which is retrieved as `previous user question + " " + question` (so "and the gateway?" still finds sources). `turn` passes `runner` as the target and `model or None` as `RunRequest.model`, calls `log(...)` once per line of the **answer text** (never the JSON wrapper), then `remember(runner, model)` and `usage.record("app:chat", channel="human", hit=bool(answer))`. Route: `chat.check(b)` runs synchronously (its `ValueError`/`RuntimeError` become `json_response({"error": str(e)}, 400)` explicitly in the handler), then `start_job("chat", "chat", lambda log: chat.turn(runner, model, q, history, log), quiet=True)`.

- [ ] **Step 1: Failing tests** (fake runner from `tests/test_ask_ai.py`'s `answerer` fixture, imported): a turn returns the answer with the made-up citation dropped, the prompt is single-line, runs in an empty cwd, and the chosen model reaches the runner's argv; a second turn's prompt contains the first turn's text as context; "and the gateway?" after a payments question still cites `flows/checkout.md#failure-handling`; nothing found → `result["answer"] is None`, no model call, and the question is in `usage.misses()`; `log` receives the answer lines, not the JSON; Review Focus: `check` rejects history that is not a list, a role `system`, non-string text, an empty `q`, models `"--dangerously-skip-permissions"`, `"a b"` and `" "`, and an uninstalled runner (an empty model `""` is accepted as "no `--model`"); a 50-turn history is cut to 6 turns and 4000 characters; `ask.ai: false` → RuntimeError starting `no AI answer here`; the route returns a job whose `GET /api/jobs/<id>` ends `done` with `result`; `answers.answer()` output is unchanged (`test_ask_ai.py` green).
- [ ] **Step 2:** `uv run pytest tests/test_chat.py tests/test_ask_ai.py -q` → FAIL. **Step 3: Implement.** **Step 4:** PASS. **Step 5: Commit** `feat(chat): a grounded chat turn as a job, sharing Ask's core`.

### Task 10: Window-level chat store

**Files:** Create `chat.js` · Modify `App.jsx` (in `Project`, next to the `jobs` store at line 64: `const chat = useMemo(() => chatStore(srv), [])`; pass `chat={chat}` through `<Section …>` to the sections) · Test `chat.test.js`.

**Produces:**
```js
export function chatStore(srv, { follow: followJob = follow } = {})
// -> { get(), subscribe(fn), load(), send(q), pick(runner, model), clear() }
// state: { messages: [{ role: 'user'|'assistant', text, result?, error? }], running, runners: null|[], choice: {runner, model}|null, ai: true, loadError: '' }
export const revealSteps = (text, { maxMs = 1500, stepMs = 50 } = {}) => string[]   // growing prefixes by words; length ≤ maxMs/stepMs; the last is the whole text; '' → ['']
```
`load()` reads `app/chat/models` into `runners`, `choice`, `ai`. `send(q)`: ignored when `running` or `q.trim()` is empty; appends the user message, POSTs `app/chat` with `{q, history, runner, model}` where `history` is the earlier `{role, text}` messages that have text and no error; follows the job with `follow` (from `cmd.js`); done → assistant message `{role: 'assistant', text: result.answer || '', result}`; a failed job → `error: <last log line without the leading "⚠ ">`; a POST rejection → `error: err.message`. `clear()` empties `messages`, sets `running` false and bumps an internal epoch so a later answer of the old turn is discarded. The store is not React; a navigation does not touch it.

- [ ] **Step 1: Failing tests** (fake `srv`, fake `follow`): two sends make the second POST carry the first turn as history; `send` while running makes no second POST; empty and whitespace questions are ignored; `clear()` during a turn then resolving the turn leaves `messages` empty and `running` false (Review Focus 4); the store keeps its messages across `subscribe`/unsubscribe (a section unmount); a failed job and a rejected POST become `error` messages (no `⚠`); `load()` with `runners: []` sets `choice: null`; `ai: false` is kept; `pick` changes `choice` and the next POST uses it; `revealSteps` caps steps, ends with the full text, handles `''`.
- [ ] **Step 2:** `npx vitest run src/chat.test.js` → FAIL. **Step 3: Implement.** **Step 4:** PASS. **Step 5: Commit** `feat(app): window-level chat store`.

### Task 11: The shrimp, from the favicon

**Files:** Modify `.camarones/portal/app/public/favicon.svg` (add class names only), `desktop/renderer/vite.config.js` (`server.fs.allow` gains the portal's `public` folder) · Create `shrimp.js`, `sections/Shrimp.jsx` · Modify `app.css` · Test `shrimp.test.js`, `sections/Shrimp.test.jsx`.

**Produces:**
```js
export const shrimpMarkup = (svg: string) => string   // inner markup of the favicon: no <rect>, hex colours mapped (#ff8a5b → var(--color-aurora-coral), #0a0a0a → var(--color-canvas)), classes kept
export function Shrimp({ state })   // state: 'idle' | 'thinking' | 'answering'; <svg className={`dk-shrimp ${state}`} viewBox="0 0 64 64" aria-hidden="true"> + three <i> dots when thinking
```
Favicon classes (rendering unchanged): `shrimp-antennae` on the first `<g>` (the two long curves and the short ticks), `shrimp-tail` on the `translate(31.7 48.5)` group, `shrimp-eye` on the circle. Motion (add to the reduced-motion block): thinking → antennae sway (`rotate` ±6°, 1.6s) and three dots rise in sequence; answering → tail flicks (`rotate` ±10°, .5s); idle → still. Colours through tokens only.

- [ ] **Step 1: Failing tests:** every `d="…"` of the favicon file (read with `fs`) appears in `shrimpMarkup` output; no `<rect`, no `#ff8a5b`/`#0a0a0a` remain; the three class names are present; `Shrimp` for each state has the class and is `aria-hidden`; `thinking` renders three dots, the others none; `style.test.js` still passes (no raw colours).
- [ ] **Step 2:** `npx vitest run src/shrimp.test.js src/sections/Shrimp.test.jsx src/style.test.js` → FAIL. **Step 3: Implement** (`import favicon from '../../../../portal/app/public/favicon.svg?raw'`).
- [ ] **Step 4:** PASS; then from the root `uv run scripts/icons.py` and `git status --short .camarones/desktop/icon.png .camarones/desktop/icon-mac.png` shows no change (the classes must not alter the render). **Step 5: Commit** `feat(app): animated shrimp built from the favicon's own drawing`.

### Task 12: The chat panel, its entry and the layout

**Files:** Create `sections/DocsChat.jsx` · Modify `sections/Docs.jsx` (replace the `Ask` card with `AskEntry`; Docs takes a `chat` prop; page row = content + docked panel), `App.jsx` (pass `chat`), `tour.js`, `app.css`, `i18n.js` · Test `sections/DocsChat.test.jsx`, `Docs.test.jsx`.

**Consumes:** `chatStore` (Task 10), `Shrimp` (Task 11), `answerView`/`AnswerView`/`askError` (existing), `revealSteps`.
**Produces:** `export function ChatPanel({ chat, onClose, onOpen })` (`chat` = store, `onOpen(hash)` opens a source in the portal) and `export function AskEntry({ chat, onAsk })` (a field + button that calls `chat.send(q)` and opens the panel; `data-tour="docs-chat"`).

Behaviour (from the spec): header with one grouped `<select>` (`<optgroup>` per runner, options = models, value `runner|model`), Clear and Close; message list — questions as text, assistant messages via `<AnswerView view={answerView(message.result)} onOpen={onOpen} />` (text, "Respondido por …", source buttons), a "nothing found" message (`docs.askNone`) for `result.answer === null`, errors through `askError`; while `running` the shrimp is `thinking` with "Pelando tus docs…" / "Peeling your docs…", then `answering` while `revealSteps` reveals the text (a click shows all; with `prefers-reduced-motion: reduce` it appears at once; the label alone then says the state), then `idle`; the message region is `aria-live="polite"`; the composer sends on Enter (Shift+Enter breaks the line) and is disabled while `running`, with no runners (`Aviso` with a link to `#/machine`) or with `ai: false` (the `docs.askNoAi` text); Esc closes; focus goes to the field on open and returns to the opener on close. Layout: panel is a right column (`24rem`) next to the page; below `68rem` it becomes a fixed drawer over the page. The `docs-ask` tour target becomes `docs-chat`. After this task `Docs.test.jsx` primaries are `1 (Leer) + one per card`.

- [ ] **Step 1: Failing tests** (static markup, store states built by hand): picker groups and values; no-runners state (Review Focus 3); `ai: false` state; thinking state shows the shrimp `thinking` and the joke label in es and en, and the composer disabled; an answer with sources shows source buttons with `aria-label="Ver: <cite>"`; `answer: null` shows `docs.askNone`; an error message shows the mapped text, no `⚠`; the live region and composer labels exist; `AskEntry` has a field labelled `Pregunta` and a `Preguntar` button; Docs markup has no old Ask card; i18n keys exist in both languages.
- [ ] **Step 2:** `npx vitest run src/sections/DocsChat.test.jsx src/Docs.test.jsx src/i18n.test.js src/tour.test.js` → FAIL. **Step 3: Implement.**
- [ ] **Step 4:** PASS and whole `npx vitest run` green. **Step 5: Commit** `feat(app): docs chat panel with runner and model picker`.

### Task 13: Docs checkpoint for the chat, and a check in the real app

**Files:** Modify `README.md`, the two `app.md` guides, `tour.js`/`i18n.js` (final `tour.docs.N` texts for the chat), `.claude/skills/cofundo-design-system/CAMARON.md` (an exception recording that the Docs chat's shrimp is the favicon's own markup inlined, `Shrimp` in `desktop/renderer/src/sections/Shrimp.jsx`, animated with `transform`/`opacity`), `desktop/renderer-build/` (rebuilt).

- [ ] **Step 1:** Update README and both guides (the chat, the picker, what it answers from, that it keeps no history after a reload); `uv run pytest tests/test_guide.py -q` passes.
- [ ] **Step 2:** `npm run build` in `.camarones/desktop/renderer`; `uv run pytest tests/test_desktop_renderer.py -q` passes.
- [ ] **Step 3:** `uv run pytest -n auto` is green; quote the summary line.
- [ ] **Step 4: Check in the app.** With the sandbox (`uv run scripts/sandbox.py open`, or `reset` first; say if it had to be created), open Docs at three widths (wide, about 1100px, about 700px), in light and dark, and with reduced motion on. Confirm: wiki cards in the grid, a stale and a fresh state, the health header, the chat opening as column then drawer, a two-question conversation with a runner installed, the thinking and answering shrimp, Clear mid-turn, and a project with no runner. Report what was seen and what could not be checked.
- [ ] **Step 5: Commit** `feat(app): docs chat with an animated shrimp`.

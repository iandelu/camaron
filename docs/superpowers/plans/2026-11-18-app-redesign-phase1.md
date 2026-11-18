# App redesign · Phase 1 (navigation and moves) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The desktop app shows four project places (Flow, Board, Quality, Docs) plus Settings, with tabs, every old address and shortcut landing on its new home, and no control lost.

**Architecture:** Renderer-only. One data file (`places.json`) declares each place's views, the catalog zones its "All commands" fold lists and the commands its panels run; `nav.js`, `palette.js` and `catalog.js` read it. A `Place` component draws the title and tabs and tells nested section components (which keep their own `Page`) to drop their title. Existing sections become views of a place; Team and Machine dissolve into Docs' team strip and Settings' tabs.

**Tech Stack:** React 19 + Vite + Vitest (`.camarones/desktop/renderer`), `@camaron/ui`, pytest for the one Python guard.

**Spec:** `docs/superpowers/specs/2026-11-18-app-redesign-design.md` (§2, §3.3, §4 Add menu, §5.1 tabs, §6 strip and tabs, §7, §9, §11 Phase 1). Mockups: https://claude.ai/artifact/3zfJ385zLVtFvX44pJdZkK.

## Global Constraints

- Every user-facing string exists in `es` and `en` in `src/i18n.js`; no jokes in errors, warnings or decisions (AGENTS.md §3).
- Old addresses keep working: `#/summary`, `#/plan…`, `#/decisions…`, `#/interviews`, `#/team…`, `#/machine…`, `#/libs…` (spec §2.1).
- `g` letters: `f` Flow, `b` Board, `q` Quality, `d` Docs, `m` Settings, `h` Guide, `k` Kit dev; aliases `s`→`flow`, `p`→`flow/plan`, `a`→`docs/decisions`, `i`→`docs/interviews`, `t`→`docs`.
- No backend change in this phase; CLI zones and command names unchanged.
- `VERSIONS["kit"]` becomes `"4.90.0"`; README badge, guides (en + es) and tutorial change in the same commit as what they describe (AGENTS.md §5.1).
- `renderer-build/` (and `portal/app-build/` if `@camaron/ui` changes) rebuilt and committed; CI fails otherwise.
- TDD: each task writes or changes its test first. Run renderer tests from `.camarones/desktop/renderer`: `npm test` (all) or `npx vitest run src/<file>`.
- Conventional commits, no `Co-Authored-By` trailer, stage only this task's files (other sessions may edit the tree).
- UI follows the existing classes (`dk-guide-tabs`, `dk-guide-tab`, `cu-*`); no new colours.

## Review Focus

1. An old deep link with a query (`#/plan?term=t-explain_api-2`, `#/machine?host=…&kind=sonarqube`) must keep its query after the redirect and still open the terminal / prefill the token → Task 1 tests `movedRoute`, Task 5 tests `termOf` on the new route, Task 7 tests the Tokens prefill.
2. A palette command whose name is also a view (`skills`, `trust`, `plugins`) must open its panel, not a fold that does not list it → Task 2 tests `sectionFor` and the Python guard.
3. A section rendered inside a place keeps its header actions (Plan's) while losing its own title → Task 4 tests `Page` under `PlaceContext`.
4. The team strip's read failing (no remote, offline) must not hide Docs' tabs or content → Task 6 tests `TeamStrip` with a failing `GET sync`.
5. A guide marker naming a place inside a tab (`go:docs/decisions`, `go:settings/tokens`) must render a working "Go to" button → Task 11 tests `markerAction` with `PLACES`.

---

### Task 1: Places data and routing (`places.json`, `nav.js`)

**Files:**
- Create: `.camarones/desktop/renderer/src/places.json`
- Modify: `.camarones/desktop/renderer/src/nav.js`
- Test: `.camarones/desktop/renderer/src/nav.test.js` (rewrite the section, libraries, token and terminal tests)

**Interfaces:**
- Produces (`nav.js`): `PROJECT`, `MACHINE`, `START`, `LIBS = 'quality/libs'`, `VIEWS` (from `places.json`), `PLACES: string[]`, `sections({kitdev})`, `sectionOf(hash, flags): string`, `viewOf(hash, section): string`, `placeOf(hash, flags): string`, `movedRoute(hash): string | null`, `tokenPrefill(hash)`, `termOf(hash)`, `firstRunPending`, `firstRunRoute`, `initials`. `qualityView` is removed (Task 8 switches to `viewOf`).
- Produces (`places.json`): `{ views, zones, panels }` — read by Tasks 2 and 3.

- [ ] **Step 1: Write `places.json`** with exactly:

```json
{
  "views": {
    "flow": ["summary", "plan"],
    "quality": ["health", "libs"],
    "docs": ["read", "wikis", "decisions", "interviews"],
    "settings": ["general", "tokens", "skills", "plugins", "trust", "kit"]
  },
  "zones": { "flow/plan": ["generate"], "quality": ["check", "analyze"], "docs": ["team", "interviews"], "settings": ["machine"] },
  "panels": {
    "flow/plan": ["run", "autopilot", "docs"],
    "quality": ["doctor", "eval", "ab", "inventory", "health", "fresh", "blocks", "hooks"],
    "docs": ["remote", "share"],
    "docs/interviews": ["interview"],
    "settings": ["setup", "config", "sync", "detect", "stack", "profile", "repair"],
    "settings/kit": ["self-update", "uninstall"],
    "settings/skills": ["skills"],
    "settings/plugins": ["plugins"],
    "settings/trust": ["trust"]
  }
}
```

The first view of each place is its default (no segment in the address).

- [ ] **Step 2: Write the failing tests** in `nav.test.js`:

```js
expect(PROJECT).toEqual(['flow', 'board', 'quality', 'docs'])
expect(MACHINE).toEqual(['settings', 'guide', 'kitdev'])
expect(sections({ kitdev: false }).machine).toEqual(['settings', 'guide'])
expect(PLACES).toEqual(['flow', 'flow/plan', 'board', 'quality', 'quality/libs', 'docs', 'docs/wikis', 'docs/decisions',
  'docs/interviews', 'settings', 'settings/tokens', 'settings/skills', 'settings/plugins', 'settings/trust', 'settings/kit', 'guide', 'kitdev'])
// views
expect(viewOf('#/flow', 'flow')).toBe('summary')
expect(viewOf('#/flow/plan?term=t-a-1', 'flow')).toBe('plan')
expect(viewOf('#/quality/radar', 'quality')).toBe('health')            // a command of the fold, not a view
expect(viewOf('#/docs/decisions/0012', 'docs')).toBe('decisions')
expect(viewOf('#/settings/tokens?kind=sonarqube', 'settings')).toBe('tokens')
expect(viewOf('#/board', 'board')).toBe('')
// sections, old addresses included
for (const [h, s] of [['#/flow', 'flow'], ['', 'flow'], ['#/nope', 'flow'], ['#/start', 'start'], ['#/summary', 'flow'],
  ['#/plan?term=t-a-1', 'flow'], ['#/decisions/0012', 'docs'], ['#/interviews', 'docs'], ['#/team', 'docs'],
  ['#/machine?kind=sonarqube', 'settings'], ['#/libs', 'quality'], ['#/guide/app/plan', 'guide']]) expect(sectionOf(h, {}), h).toBe(s)
expect(sectionOf('#/kitdev', { kitdev: true })).toBe('kitdev')
expect(sectionOf('#/kitdev', { kitdev: false })).toBe('flow')
// places
for (const [h, p] of [['#/flow', 'flow'], ['#/flow/plan', 'flow/plan'], ['#/plan', 'flow/plan'], ['#/quality/libs', 'quality/libs'],
  ['#/libs', 'quality/libs'], ['#/quality/radar', 'quality'], ['#/docs/decisions/new', 'docs/decisions'],
  ['#/machine?kind=sonarqube', 'settings/tokens'], ['#/board', 'board']]) expect(placeOf(h, {}), h).toBe(p)
// moved routes: what follows is kept
for (const [from, to] of [['#/summary', '#/flow'], ['#/plan', '#/flow/plan'], ['#/plan?term=t-a-1', '#/flow/plan?term=t-a-1'],
  ['#/plan/unit-x', '#/flow/plan/unit-x'], ['#/decisions/0012', '#/docs/decisions/0012'], ['#/decisions/new', '#/docs/decisions/new'],
  ['#/interviews', '#/docs/interviews'], ['#/team', '#/docs'], ['#/team/ci', '#/docs/ci'], ['#/machine', '#/settings'],
  ['#/machine/setup', '#/settings/setup'], ['#/machine?host=gitlab.example.com', '#/settings/tokens?host=gitlab.example.com'],
  ['#/machine?kind=sonarqube&host=x', '#/settings/tokens?kind=sonarqube&host=x'], ['#/libs?repo=web', '#/quality/libs?repo=web']])
  expect(movedRoute(from), from).toBe(to)
for (const h of ['#/flow', '#/quality/libs', '#/plans', '#/libsx', '#/teams', '']) expect(movedRoute(h), h).toBeNull()
// token prefill and terminal now read the new addresses
expect(tokenPrefill('#/settings/tokens?host=https%3A%2F%2Fsonar.example.com&kind=sonarqube')).toEqual({ host: 'https://sonar.example.com', kind: 'sonarqube' })
expect(tokenPrefill('#/settings/tokens?kind=nope&host=x')).toEqual({ host: 'x', kind: '' })
expect(tokenPrefill('#/machine?host=x')).toEqual({ host: '', kind: '' })    // the redirect runs first
expect(termOf('#/flow/plan?term=t-explain_api-2')).toBe('t-explain_api-2')
expect(termOf('#/flow/plan?term=../x')).toBe(null)
expect(termOf('#/plan?term=t-a-1')).toBe(null)
expect(firstRunRoute({ done: false }, '#/flow/plan')).toBe('#/start')
expect(firstRunRoute({ done: true }, '#/flow')).toBeNull()
```

Keep the existing `initials` and `firstRunPending` tests.

- [ ] **Step 3: Run** `npx vitest run src/nav.test.js` — expected: FAIL (old sections).
- [ ] **Step 4: Implement** in `nav.js`. `movedRoute` uses a table `{ summary: 'flow', plan: 'flow/plan', decisions: 'docs/decisions', interviews: 'docs/interviews', team: 'docs', machine: 'settings', libs: 'quality/libs' }` matched on the first segment as a whole word (`/^#\/(name)(?=[/?]|$)(.*)$/`), with one special case: `#/machine?…` whose query has `host` or `kind` goes to `settings/tokens`. `sectionOf` and `placeOf` apply `movedRoute` first. `PLACES` is built from `PROJECT`, `VIEWS` (non-default views as `section/view`) and `MACHINE`.
- [ ] **Step 5: Run** `npx vitest run src/nav.test.js` — expected: PASS.
- [ ] **Step 6: Commit** `feat(app): places, views and old addresses in nav`.

---

### Task 2: Catalog by place, and the view/command guard

**Files:**
- Modify: `.camarones/desktop/renderer/src/catalog.js`, `.camarones/desktop/renderer/src/sections/Commands.jsx:17`
- Create: `tests/test_desktop_places.py`
- Test: `.camarones/desktop/renderer/src/catalog.test.js`

**Interfaces:**
- Consumes: `places.json` (Task 1).
- Produces: `ZONES`, `PANELS` (from `places.json`), `others(commands, place)`, `inPanel(c)`, `sectionFor(c, available) -> place path | null`, `wantedCommand(hash, place) -> string | null`. `Commands` keeps its props; its `section` prop is now a place path (`'flow/plan'`, `'quality'`, `'docs'`, `'settings'`).

- [ ] **Step 1: Write the failing tests** in `catalog.test.js`:

```js
expect(ZONES).toEqual({ 'flow/plan': ['generate'], quality: ['check', 'analyze'], docs: ['team', 'interviews'], settings: ['machine'] })
const names = (place) => { const o = others(CMDS, place); return [...o.safe, ...o.careful].map((c) => c.name) }
expect(names('docs')).toContain('ci')
for (const n of ['remote', 'share', 'trust', 'plugins', 'skills', 'interview']) expect(names('docs')).not.toContain(n)
expect(sectionFor(cmd('trust', 'team'))).toBe('settings/trust')
expect(sectionFor(cmd('interview', 'interviews'))).toBe('docs/interviews')
expect(sectionFor(cmd('run', 'generate'))).toBe('flow/plan')
expect(sectionFor(cmd('radar', 'analyze'), ['flow', 'quality'])).toBe('quality')
expect(sectionFor(cmd('radar', 'analyze'), ['flow'])).toBeNull()
expect(sectionFor(cmd('confirm', 'generate', { verdict: 'portal' }))).toBeNull()
expect(wantedCommand('#/quality/radar', 'quality')).toBe('radar')
expect(wantedCommand('#/quality/libs', 'quality')).toBeNull()          // a view
expect(wantedCommand('#/flow/plan/plan', 'flow/plan')).toBe('plan')
expect(wantedCommand('#/docs/decisions/0012', 'docs')).toBeNull()
expect(wantedCommand('#/settings', 'settings')).toBeNull()
```

(`CMDS` is a small fixture list of `{ name, zone, verdict, destructive }`, as the file has today.)

- [ ] **Step 2: Write the Python guard** `tests/test_desktop_places.py`: load `places.json` and the registry's commands (name → zone) the way `tests/test_cli_snapshot.py` builds the CLI. Assert (a) every name in `panels` is a registered command; (b) for every fold place `P` in `zones` whose section has views, no command with a zone in `zones[P]` that is not in any `panels` list has a name in `views[section(P)]`. Use `encoding="utf-8"` and `pathlib`.
- [ ] **Step 3: Run** `npx vitest run src/catalog.test.js` — expected: FAIL. Run `uv run pytest tests/test_desktop_places.py` — expected: PASS (today's registry has no clash; the guard protects later phases).
- [ ] **Step 4: Implement.** `sectionFor` returns the `panels` key that lists the command, else the `zones` key whose zones include its zone; allowed when its first segment is in `available` (or no `available`). `wantedCommand` returns the segment right after `#/<place>/` unless it is one of `VIEWS[section]`. In `Commands.jsx` replace the hash regex with `wantedCommand(useHash(), section)`.
- [ ] **Step 5: Run** both tests — expected: PASS.
- [ ] **Step 6: Commit** `feat(app): catalog folds and panels follow places; guard views against command names`.

---

### Task 3: Shortcuts and palette (`palette.js`)

**Files:**
- Modify: `.camarones/desktop/renderer/src/palette.js`
- Test: `.camarones/desktop/renderer/src/palette.test.js`

**Interfaces:**
- Consumes: `VIEWS`, `PROJECT`, `MACHINE` (Task 1); `sectionFor`, `inPanel` (Task 2).
- Produces: `GO`, `ALIASES`, `keyFor(section)`, `chord(pending, key, at, available) -> { pending, go }` where `go` is a place path, `entries({...})`, `pick`, `typing` (unchanged).

- [ ] **Step 1: Write the failing tests:**

```js
const ALL = ['flow', 'board', 'quality', 'docs', 'settings', 'guide', 'kitdev']
expect(GO).toEqual({ f: 'flow', b: 'board', q: 'quality', d: 'docs', m: 'settings', h: 'guide', k: 'kitdev' })
expect(ALIASES).toEqual({ s: 'flow', p: 'flow/plan', a: 'docs/decisions', i: 'docs/interviews', t: 'docs' })
expect(keyFor('flow')).toBe('f'); expect(keyFor('settings')).toBe('m'); expect(keyFor('nope')).toBeUndefined()
const g = chord(0, 'g', 1000, ALL)
expect(chord(g.pending, 'p', 1800, ALL)).toEqual({ pending: 0, go: 'flow/plan' })
expect(chord(g.pending, 'a', 1800, ALL)).toEqual({ pending: 0, go: 'docs/decisions' })
expect(chord(g.pending, 'a', 1800, ['flow'])).toEqual({ pending: 0, go: null })
const ids = (sections) => entries({ sections, t }).find((x) => x.id === 'sections').items.map((i) => i.id)
expect(ids(['flow', 'quality', 'docs'])).toEqual(['go:flow', 'go:flow/plan', 'go:quality', 'go:quality/libs', 'go:docs',
  'go:docs/wikis', 'go:docs/decisions', 'go:docs/interviews'])
const items = entries({ sections: ['flow'], t }).find((x) => x.id === 'sections').items
expect(items[0]).toEqual({ id: 'go:flow', label: '<nav.flow>', keys: ['g', 'f'], href: '#/flow' })
expect(items[1]).toEqual({ id: 'go:flow/plan', label: '<nav.plan>', sub: '<nav.flow>', href: '#/flow/plan' })
const hrefs = Object.fromEntries(entries({ sections: ALL, t, commands: [cmd('radar', 'analyze'), cmd('ci', 'team'),
  cmd('run', 'generate'), cmd('trust', 'team'), cmd('skills', 'team')] }).find((x) => x.id === 'commands').items.map((i) => [i.id, i.href]))
expect(hrefs).toEqual({ 'cmd:radar': '#/quality/radar', 'cmd:ci': '#/docs/ci', 'cmd:run': '#/flow/plan',
  'cmd:trust': '#/settings/trust', 'cmd:skills': '#/settings/skills' })
```

Keep the `pick` test that finds Libraries by "librerias" (now `go:quality/libs`).

- [ ] **Step 2: Run** `npx vitest run src/palette.test.js` — expected: FAIL.
- [ ] **Step 3: Implement.** `chord` resolves `GO[key] || ALIASES[key]` and allows it when its first segment is in `available`. The sections group lists each section, then each non-default view of `VIEWS[section]` as `{ id: 'go:<place>', label: t('nav.' + view), sub: t('nav.' + section), href: '#/<place>' }`. Command hrefs: `inPanel(c) ? '#/' + place : '#/' + place + '/' + c.name`, with `place = sectionFor(c, sections)`.
- [ ] **Step 4: Run** the test — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): g shortcuts and palette entries for places and tabs`.

---

### Task 4: The place shell (`Place`, `PlaceContext`, breadcrumbs, ADR prefix)

**Files:**
- Create: `.camarones/desktop/renderer/src/Place.jsx`, `.camarones/desktop/renderer/src/crumbs.js`, `.camarones/desktop/renderer/src/crumbs.test.js`
- Modify: `.camarones/desktop/renderer/src/parts.jsx:13-21` (`Page`), `.camarones/desktop/renderer/src/adr.js` (`route`, new `ADR_BASE`), `.camarones/desktop/renderer/src/i18n.js`
- Test: `.camarones/desktop/renderer/src/parts.test.jsx`, `.camarones/desktop/renderer/src/adr.test.js`

**Interfaces:**
- Consumes: `VIEWS`, `sectionOf`, `viewOf`, `placeOf` (Task 1).
- Produces: `PlaceContext` (parts.jsx); `Place({ section, view, head, wide, full, badges, children })` and `PlaceTabs({ section, view, badges })` (Place.jsx); `crumbs({ hash, project, t, flags }) -> Array<{ label, href? }>` (crumbs.js); `ADR_BASE = '#/docs/decisions'` and `route(hash)` reading it (adr.js).

- [ ] **Step 1: Write the failing tests.**
  - `parts.test.jsx`: rendering `<PlaceContext.Provider value={true}><Page title="X" actions={<b>act</b>}><p>body</p></Page></PlaceContext.Provider>` contains `<b>act</b>` and `<p>body</p>` and no `<h1`; without the provider it still renders `<h1 class="t-impact">X</h1>`.
  - `parts.test.jsx` (Place): `<Place section="docs" view="wikis" head={<i>strip</i>}>c</Place>` renders, in this order, `<h1`, `<i>strip</i>`, a `nav.dk-guide-tabs` with links `#/docs`, `#/docs/wikis` (with `aria-current="page"`), `#/docs/decisions`, `#/docs/interviews`, then `c`; `badges={{ trust: 2 }}` on settings renders the Trust tab label as `Confianza · 2`; the tabs carry `data-tour="tabs-docs"`.
  - `adr.test.js`: `route('#/docs/decisions/new')` → `{ view: 'new' }`; `route('#/docs/decisions/0012')` → `{ view: 'adr', id: '0012' }`; `route('#/docs/decisions')` → `{ view: 'list' }`; `ADR_BASE === '#/docs/decisions'`.
  - `crumbs.test.js` (`t` maps keys to Spanish labels):

```js
expect(crumbs({ hash: '#/docs/decisions/0012', project: 'petclinic', t })).toEqual([
  { label: 'petclinic', href: '#/flow' }, { label: 'Docs', href: '#/docs' },
  { label: 'Decisiones', href: '#/docs/decisions' }, { label: 'ADR 0012' }])
expect(crumbs({ hash: '#/docs/decisions', project: 'p', t })).toEqual([{ label: 'p', href: '#/flow' }, { label: 'Docs', href: '#/docs' }, { label: 'Decisiones' }])
expect(crumbs({ hash: '#/flow', project: 'p', t })).toEqual([{ label: 'p', href: '#/flow' }, { label: 'Flujo' }])
expect(crumbs({ hash: '#/flow/plan', project: 'p', t })).toEqual([{ label: 'p', href: '#/flow' }, { label: 'Flujo', href: '#/flow' }, { label: 'Plan' }])
expect(crumbs({ hash: '#/board', project: '', t })).toEqual([{ label: '…', href: '#/flow' }, { label: 'Tablero' }])
```

- [ ] **Step 2: Run** `npx vitest run src/parts.test.jsx src/adr.test.js src/crumbs.test.js` — expected: FAIL.
- [ ] **Step 3: Implement.** `Page` returns `<>{actions && <div className="row dk-page-acts">{actions}</div>}{children}</>` when `useContext(PlaceContext)` is true. `Place` renders `<Page title={t('nav.' + section)} wide full>{head}<PlaceTabs …/><PlaceContext.Provider value>{children}</PlaceContext.Provider></Page>`; tab labels are `t('nav.' + view)` plus ` · n` for a badge > 0. `crumbs` uses `adr.crumb(hash, t)` for the last step inside Decisions. Add i18n keys (es / en): `nav.flow` Flujo / Flow, `nav.settings` Ajustes / Settings, `nav.health` Salud / Health, `nav.read` Leer / Read, `nav.wikis` Wikis / Wikis, `nav.general` General / General, `nav.tokens` Tokens / Tokens, `nav.skills` Skills / Skills, `nav.plugins` Plugins / Plugins, `nav.trust` Confianza / Trust, `nav.kit` Kit / Kit.
- [ ] **Step 4: Run** the three tests — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): the place shell — tabs, flattened pages, breadcrumbs, ADR prefix`.

---

### Task 5: Flow (Summary and Plan)

**Files:**
- Create: `.camarones/desktop/renderer/src/sections/Flow.jsx`, `.camarones/desktop/renderer/src/Flow.test.jsx`
- Modify: `src/summary.js:5-26`, `src/sections/Summary.jsx:58-65`, `src/plan.js:111-114`, `src/parts.jsx:147-148`, `src/sections/Plan.jsx:54`, `src/sections/Canvas.jsx:332`, `src/sections/Start.jsx:427`
- Test: `src/summary.test.js`, `src/plan.test.js` (address assertions)

**Interfaces:**
- Consumes: `Place` (Task 4), `viewOf`, `termOf` (Task 1).
- Produces: `Flow(props)` default export (rendered by App in Task 9).

- [ ] **Step 1: Write the failing tests.** `Flow.test.jsx` (with `globalThis.location = { hash }` and a never-resolving `srv`): at `#/flow` the markup has one `<h1` reading `Flujo` and the `Resumen` tab with `aria-current="page"`; at `#/flow/plan` the `Plan` tab is current. In `summary.test.js` the links become: setup `#/settings`, answers `#/docs/interviews`, ci `#/docs/ci`, the default plan link `#/flow/plan`, the "choose interviews" link `#/docs/interviews`. In `plan.test.js` the session landing is `#/flow/plan?term=<id>`.
- [ ] **Step 2: Run** `npx vitest run src/Flow.test.jsx src/summary.test.js src/plan.test.js` — expected: FAIL.
- [ ] **Step 3: Implement** `Flow`: `const view = viewOf(useHash(), 'flow')`; `<Place section="flow" view={view} wide={view === 'plan'}>{view === 'plan' ? <Plan {...props} /> : <Summary {...props} />}</Place>`. Change the listed links: `#/machine`→`#/settings`, `#/plan`→`#/flow/plan`, `#/plan?term=`→`#/flow/plan?term=`, `#/interviews`→`#/docs/interviews`, `#/team`→`#/docs/ci`, `#/summary`→`#/flow`; `Plan.jsx` puts back `#/flow/plan` after taking the terminal; `Plan.jsx`'s `<Commands section="plan">` becomes `section="flow/plan"`.
- [ ] **Step 4: Run** the tests — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): Flow place with Summary and Plan`.

---

### Task 6: Docs (team strip, Read, Wikis, Decisions, Interviews)

**Files:**
- Create: `src/sections/TeamStrip.jsx`, `src/TeamStrip.test.jsx`
- Modify: `src/sections/Docs.jsx` (split into views), `src/docs.js` (new `stripState`), `src/docs.test.js`, `src/sections/Decisions.jsx:53-59`, `src/sections/adr/AdrList.jsx`, `adr/Evidence.jsx`, `adr/Read.jsx`, `adr/Candidates.jsx`, `adr/Review.jsx` (every `#/decisions` → `ADR_BASE`), `src/i18n.js`
- Test: `src/Docs.test.jsx`, `src/Decisions.test.jsx`, `src/Team.test.jsx` → renamed `src/TeamStrip.test.jsx` for `ShareResult`/`FetchNote`

**Interfaces:**
- Consumes: `Place` (Task 4), `viewOf` (Task 1), `ADR_BASE` (Task 4).
- Produces: `Docs(props)` default export; `TeamStrip({ srv, jobs })`; `Repo`, `ShareResult`, `FetchNote` now exported from `TeamStrip.jsx`; `stripState(sync) -> { key, vars, tone }`.

- [ ] **Step 1: Write the failing tests.**
  - `docs.test.js` — `stripState`: `null` (unread) → `{ key: 'ts.reading', tone: 'none' }`; `{ error: 'x' }` → `{ key: 'ts.failed', tone: 'warn' }`; `{ remote: '' }` → `{ key: 'ts.never', tone: 'none' }`; `{ remote: 'r', behind: 2, ahead: 0, pending: [] }` → `{ key: 'ts.behind', vars: { n: 2 }, tone: 'warn' }`; `{ remote: 'r', behind: 0, ahead: 1, pending: ['a'] }` → `{ key: 'ts.ahead', vars: { n: 2 }, tone: 'warn' }` (n = ahead + pending); `{ remote: 'r', behind: 0, ahead: 0, pending: [] }` → `{ key: 'ts.upToDate', tone: 'ok' }`.
  - `TeamStrip.test.jsx`: with a `srv.get('sync')` that rejects, the strip says the failure line and a Retry, and `Docs` at `#/docs` still renders its tabs and the portal buttons; the strip has `data-tour="docs-team"` and a `<details>` holding the team repo field. Move the existing `ShareResult` / `FetchNote` tests here from `Team.test.jsx`.
  - `Docs.test.jsx`: at `#/docs` the tabs show `Leer` current and the portal buttons and C4 card; at `#/docs/wikis` the wiki blocks render and the portal buttons do not; at `#/docs/interviews` the Interviews mode card renders.
  - `Decisions.test.jsx`: every link it asserts reads `#/docs/decisions/…` instead of `#/decisions/…`.
- [ ] **Step 2: Run** `npx vitest run src/docs.test.js src/TeamStrip.test.jsx src/Docs.test.jsx src/Decisions.test.jsx` — expected: FAIL.
- [ ] **Step 3: Implement.** `Docs` picks the view and renders `<Place section="docs" view head={<TeamStrip srv jobs />}>` with: `read` → portal buttons, C4 `Build`, `Ask`, `<Commands section="docs" />`; `wikis` → the wiki blocks; `decisions` → `<Decisions srv />`; `interviews` → `<Interviews srv jobs app />`. `TeamStrip` reads `GET sync` once, shows `stripState`'s sentence, "Share now" (`POST sync/share`, result through `ShareResult`), and a `<details>` with the current `Repo` card (moved unchanged from `Team.jsx`, its `#/machine?host=` link becoming `#/settings/tokens?host=`). i18n (es / en): `ts.reading` Leyendo… / Reading…, `ts.failed` No he podido leer cómo va el repo del equipo / I could not read the team repo's state, `ts.never` Aún no se comparte con un equipo / Not shared with a team yet, `ts.behind` {n} cambios del equipo por traer / {n} team changes to bring, `ts.ahead` {n} cambios por compartir / {n} changes to share, `ts.upToDate` Al día con el equipo / Up to date with the team, `ts.share` Compartir ahora / Share now, `ts.repo` Repo del equipo / Team repo.
- [ ] **Step 4: Run** the tests — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): Docs place — team strip, Read, Wikis, Decisions and Interviews tabs`.

---

### Task 7: Settings (General, Tokens, Skills, Plugins, Trust, Kit)

**Files:**
- Create: `src/sections/Settings.jsx`, `src/sections/SettingsTeam.jsx`, `src/Settings.test.jsx`
- Modify: `src/sections/Machine.jsx` (drop the default export; export `GuideCard`, `Setup`, `SessionSettings` (renamed from the inner `Settings`), `Tokens`, `Repos`, `Kit`, `Uninstall`), `src/i18n.js`
- Delete: `src/sections/Team.jsx` (its `Trust`, `Skills`, `SkillsList`, `Plugins`, `word` move to `SettingsTeam.jsx`; `Repo`/`ShareResult`/`FetchNote` went to `TeamStrip.jsx` in Task 6)
- Test: `src/Machine.test.jsx`, `src/Guide.test.jsx` (it imports `Machine` today: switch to `Settings`), the remaining `Team.test.jsx` cases → `src/SettingsTeam.test.jsx`

**Interfaces:**
- Consumes: `Place` (Task 4), `viewOf`, `tokenPrefill` (Task 1).
- Produces: `Settings(props)` default export.

- [ ] **Step 1: Write the failing tests** in `Settings.test.jsx` (fake `srv`: `app/machine` resolves a fixture `m`; the catalog command `trust --json` resolves `{ pending: [{ kind: 'hook', label: 'x' }, { kind: 'mcp', label: 'y' }] }`): at `#/settings` the General tab is current and renders the guide card (`data-tour="mc-guide"`), Setup, the session settings and Repos; at `#/settings/tokens?host=sonar.example.com&kind=sonarqube` the Tokens card is prefilled with that host and kind and a notice `st.from` names the host; at `#/settings/kit` Kit and Uninstall render; the Trust tab label reads `Confianza · 2` once the pending list is read; at `#/settings/skills`, `/plugins`, `/trust` their cards render (`data-tour` `team-skills`, `team-plugins`, `team-trust`).
- [ ] **Step 2: Run** `npx vitest run src/Settings.test.jsx src/Machine.test.jsx src/Guide.test.jsx` — expected: FAIL.
- [ ] **Step 3: Implement** `Settings`: reads `app/machine` once (as `Machine` did) and passes `m` down; runs `trust --json` quietly once (and again when Skills reports a change) for the badge; `<Place section="settings" view badges={{ trust: n }}>` with: `general` → `GuideCard`, `Setup`, `SessionSettings`, `Repos`, `<Commands section="settings" />`; `tokens` → the notice and `<Tokens key host kind />`; `skills` → `Skills`; `plugins` → `Plugins`; `trust` → `Trust`; `kit` → `Kit`, `Uninstall`. i18n (es / en): `st.from` Vienes de Calidad: falta el token de {host}. / You came from Quality: the token for {host} is missing.
- [ ] **Step 4: Run** the tests — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): Settings place — Machine's and Team's cards as tabs`.

---

### Task 8: Quality tabs through the place shell

**Files:**
- Modify: `src/sections/Quality.jsx:22-41,231`, `.camarones/ui/src/health.js:85-87` (`sonarConnectHash`)
- Test: `src/Quality.test.jsx` (drop `QualityViews`), `.camarones/ui/src/health.test.js`

**Interfaces:**
- Consumes: `Place` (Task 4), `viewOf` (Task 1).
- Produces: `sonarConnectHash(host)` → `#/settings/tokens?host=<h>&kind=sonarqube` (or `#/settings/tokens?kind=sonarqube`).

- [ ] **Step 1: Write the failing tests.** `health.test.js`: `sonarConnectHash('https://s.example.com')` → `'#/settings/tokens?host=https%3A%2F%2Fs.example.com&kind=sonarqube'`; `sonarConnectHash('')` → `'#/settings/tokens?kind=sonarqube'`. `Quality.test.jsx`: rendering `Quality` at `#/quality/libs` shows the `Librerías` tab current inside `nav.dk-guide-tabs[data-tour="tabs-quality"]`; the old `QualityViews` test is removed.
- [ ] **Step 2: Run** `npx vitest run src/Quality.test.jsx` and `cd ../../ui && npx vitest run src/health.test.js` — expected: FAIL.
- [ ] **Step 3: Implement.** `Quality` renders `<Place section="quality" view={viewOf(hash, 'quality')} wide={view === 'libs'}>`; `QualityViews` is deleted; `#/machine` → `#/settings`. Change `sonarConnectHash`. Health's rows (including libraries and secrets) stay as in 4.89 in this phase.
- [ ] **Step 4: Run** the tests — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): Quality tabs through the place shell; Sonar connect goes to Settings › Tokens`.

---

### Task 9: Wire the window (`App.jsx`)

**Files:**
- Modify: `src/App.jsx` (imports, `SECTIONS`, brand/rail hrefs, breadcrumbs, chord navigation)
- Test: `src/App.test.jsx`

**Interfaces:**
- Consumes: `Flow`, `Docs`, `Settings`, `Quality` (Tasks 5–8), `crumbs` (Task 4), `sectionOf`, `movedRoute` (Task 1), `chord`, `keyFor` (Task 3).

- [ ] **Step 1: Write the failing tests** in `App.test.jsx`: the sidebar lists, in order, links `#/flow`, `#/board`, `#/quality`, `#/docs`, then `#/settings`, `#/guide`; the first hint is `<kbd class="cu-kbd">g</kbd><kbd class="cu-kbd">f</kbd>`; at `#/docs/decisions/0012` the crumbs contain `<a href="#/docs">Docs</a>`, `<a href="#/docs/decisions">Decisiones</a>` and `<span aria-current="page">ADR 0012</span>`; at `#/flow/plan` the current crumb is `Plan`; the brand links to `#/flow`.
- [ ] **Step 2: Run** `npx vitest run src/App.test.jsx` — expected: FAIL.
- [ ] **Step 3: Implement.** `SECTIONS = { flow: Flow, board: Board, quality: Quality, docs: Docs, settings: Settings, guide: Guide, kitdev: KitDev, start: Start }`; drop the imports of `Summary`, `Plan`, `Interviews`, `Team`, `Decisions`, `Machine`; brand, first crumb and the rail's current project link to `#/flow`; breadcrumbs come from `crumbs({ hash, project: index?.project, t, flags: { kitdev } })`; a chord sets `location.hash = '#/' + r.go`. The `movedRoute` effect already redirects.
- [ ] **Step 4: Run** `npm test` (whole renderer suite) — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): the window shows Flow, Board, Quality, Docs and Settings`.

---

### Task 10: Board › Add menu

**Files:**
- Modify: `src/sections/Board.jsx:18,72` (`Board({ srv, app })`, the Add button), `src/board.js` (new `addChoices`), `src/i18n.js`
- Test: `src/board.test.js`, `src/Board.test.jsx`

**Interfaces:**
- Consumes: `openPortal(app, origin, hash)` (`docs.js:63`).
- Produces: `addChoices(types) -> Array<{ type, where: 'portal' | 'form' }>`.

- [ ] **Step 1: Write the failing tests.** `board.test.js`: `addChoices(['story', 'task', 'bug'])` → `[{ type: 'story', where: 'portal' }, { type: 'task', where: 'form' }, { type: 'bug', where: 'form' }]`; `addChoices([])` → `[]`. `Board.test.jsx`: `BoardView` with `menu` open renders a `role="menu"` whose first item names the story type with the hint `bd.storyPortal`, and the Add button has `aria-haspopup="menu"`.
- [ ] **Step 2: Run** `npx vitest run src/board.test.js src/Board.test.jsx` — expected: FAIL.
- [ ] **Step 3: Implement.** "Add ▾" toggles a menu of `addChoices(board.types)`: `portal` → `openPortal(app, location.origin, '#/stories')`; `form` → `openForm({ type })`. Escape and a click outside close it; focus goes to its first item on open and back to the button on close. "Add a task" in a story is unchanged. i18n (es / en): `bd.add` Añadir ▾ / Add ▾, `bd.storyPortal` Se escribe en el portal, en Historias ↗ / Written in the portal, in Stories ↗, `bd.addForm` Formulario aquí / Form here.
- [ ] **Step 4: Run** the tests — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): Board's Add menu sends stories to the portal's Historias`.

---

### Task 11: Tours and guide markers

**Files:**
- Modify: `src/tour.js` (`TOURS`, new `HOME`, `tourAlias`), `src/sections/Guide.jsx:36-39` (`markerAction` uses `PLACES` and `tourAlias`), `src/i18n.js` (`tour.*` strings, es + en)
- Test: `src/tour.test.js`, `src/Tour.test.jsx`, `src/Guide.test.jsx`

**Interfaces:**
- Consumes: `PLACES`, `LIBS`, `placeOf` (Task 1); the `data-tour` targets of Tasks 4–8 (`tabs-flow`, `tabs-quality`, `tabs-docs`, `tabs-settings`, `docs-team`, existing `summary-*`, `plan-*`, `q-*`, `libs-*`, `docs-*`, `iv-*`, `mc-*`, `team-*`).
- Produces: `tourIds() = ['app', 'flow', 'plan', 'board', 'quality', 'libs', 'docs', 'interviews', 'settings']`; `HOME = { flow: 'flow', plan: 'flow/plan', board: 'board', quality: 'quality', libs: LIBS, docs: 'docs', interviews: 'docs/interviews', settings: 'settings' }`; `tourAlias(id)` mapping `summary`→`flow`, `team`→`docs`, `machine`→`settings`, others unchanged.

- [ ] **Step 1: Write the failing tests.** `tour.test.js`: `tourIds()` equals the list above; every step of tour `id` (not `app`) has `section === HOME[id]` or `section.startsWith(HOME[id] + '/')`; the app tour's `nav-*` targets are exactly `nav-flow`, `nav-board`, `nav-quality`, `nav-docs`, `nav-settings`, `nav-guide`; every step has `.t` and `.b` in both languages; `tourAlias('team')` is `'docs'`. `Tour.test.jsx`: `go:` markers are checked against `PLACES`, `tour:` markers against `tourIds()`. `Guide.test.jsx`: `markerAction('go', 'docs/decisions', …)` returns a link to `#/docs/decisions`; `markerAction('tour', 'machine', …)` returns the `settings` tour.
- [ ] **Step 2: Run** `npx vitest run src/tour.test.js src/Tour.test.jsx src/Guide.test.jsx` — expected: FAIL.
- [ ] **Step 3: Implement.** `TOURS.app`: `rail`, `nav-flow`, `nav-board`, `nav-quality`, `nav-docs`, `nav-settings`, `find`, `portal`, `menu`, `jobs`, `nav-guide`. `flow`: `tabs-flow`, `summary-next`, `summary-doctor`, `summary-stats`. `plan` (at `flow/plan`): today's plan steps. `quality`: unchanged (`q-verdict`, `q-areas`, `q-repos`). `docs`: `docs-team`, `tabs-docs`, `docs-portal`, `docs-c4`, `docs-ask`. `interviews` (at `docs/interviews`): today's steps. `settings`: `tabs-settings`, `mc-guide`, `mc-setup`, `mc-settings`, `mc-repos` at `settings`, `mc-tokens` at `settings/tokens`, `team-trust` at `settings/trust`, `mc-kit`, `mc-uninstall` at `settings/kit`. Rewrite the `tour.<id>.<n>.t/.b` strings for `app`, `flow`, `docs`, `settings` in es and en (one short sentence each, same voice as today; the old `summary`, `team`, `machine` keys go away).
- [ ] **Step 4: Run** the tests — expected: PASS.
- [ ] **Step 5: Commit** `feat(app): tours and guide markers follow the places`.

---

### Task 12: User docs, version and builds

**Files:**
- Modify: `.camarones/templates/docs/guides/app.md`, `.camarones/templates/docs/i18n/es/guides/app.md`, `guides/using.md:68`, `guides/internals.md:356` (and their es twins), `README.md`, `.camarones/lib/tutorial.py` (only passages about the desktop app's sections), `.camarones/TUTORIAL.md` (regenerated), `.camarones/templates/docs/guides/tutorial.md` + es twin (only if they name app sections), `.camarones/lib/common.py:24` (`"kit": "4.90.0"`)
- Rebuild: `.camarones/desktop/renderer-build/`, `.camarones/portal/app-build/` (because `@camaron/ui/health.js` changed)

- [ ] **Step 1: Restructure `app.md` (en, then es)** — "The window" lists the new sidebar; sections become `## Flow` (`go:flow`, `tour:flow`) with `### Summary` and `### Plan` (`go:flow/plan`, `tour:plan`); `## Board` (mention the Add menu); `## Quality` with `### Libraries` (`go:quality/libs`, `tour:libs`); `## Docs` (`go:docs`, `tour:docs`) with the team strip (from the old Team text), `### Read`, `### Wikis` (`go:docs/wikis`), `### Decisions` (`go:docs/decisions`), `### Interviews` (`go:docs/interviews`, `tour:interviews`); `## Settings` (`go:settings`, `tour:settings`) with General, Tokens (`go:settings/tokens`), Skills, Plugins, Trust (old Team text), Kit (old Machine text). `go:team` in `using.md` / `internals.md` becomes `go:docs` (sharing) or `go:settings/skills` (skills), as the sentence is about.
- [ ] **Step 2: Run** `uv run pytest tests/test_guide.py` and `npx vitest run src/Tour.test.jsx` — expected: PASS (markers, links and both languages match).
- [ ] **Step 3: Update `README.md`** (desktop app section and the version badge 4.90.0), `lib/tutorial.py` where it names app sections, regenerate `TUTORIAL.md` from `.camarones/` with `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`, and bump `VERSIONS["kit"]` to `"4.90.0"`.
- [ ] **Step 4: Rebuild** `cd .camarones/desktop/renderer && npm ci && npm run build` and `cd .camarones/portal/app && npm ci && npm run build`.
- [ ] **Step 5: Run the whole suite** — `uv run pytest -n auto`, renderer `npm test`, portal `npm test`, `.camarones/ui` `npx vitest run`, desktop `node --test "test/*.test.cjs"`. Expected: all green; report the counts.
- [ ] **Step 6: End-to-end in the sandbox** — `uv run scripts/sandbox.py open` (or the desktop app from this checkout under Kit dev): open each place and tab; type `#/plan`, `#/decisions/new`, `#/team`, `#/machine?kind=sonarqube` and confirm each lands on its new place; press `g p`, `g a`, `g m`; take a screenshot of Flow, Docs and Settings for the report.
- [ ] **Step 7: Commit** `feat(app): four places and Settings (kit 4.90.0)` with the docs, version and both builds; the body says templates reach only new projects.

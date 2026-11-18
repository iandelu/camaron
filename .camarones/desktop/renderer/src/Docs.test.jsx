import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Docs, { AnswerView, BuildCard, WikiBlock, WikiCard, WikiGrid, WikisUnread } from './sections/Docs.jsx'
import { wikiBlocks } from './docs.js'
import { setLang } from './i18n.js'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
// Every repo of the project is in `repos`; only api and ui have wiki pages yet.
const index = { repos: ['api', 'web', 'ui'], docs: [{ path: 'repos/api/index.md', space: 'wiki' }, { path: 'repos/ui/a.md', space: 'wiki' },
  { path: 'index.md', space: 'docs' }] }
const render = (idx = index) => renderToStaticMarkup(<Docs srv={srv} jobs={null} app={{ openExternal: () => {} }} index={idx} />)

afterEach(() => { delete globalThis.location; setLang('es') })

// Reading is the portal's, in the system browser: buttons that call app.openExternal, never a link the window follows.
test('Docs opens the portal through the browser and offers the C4 build', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render()
  expect(out).not.toMatch(/<a [^>]*href=/)
  for (const label of ['Leer la documentación', 'Revisar borradores', 'Buscar o preguntar']) expect(out).toContain(label)
  expect(out).toContain('Construir el explorador C4')
  expect(out).toMatch(/aria-label="Construir: Construir el explorador C4"/)
})

// One block per repo, with or without a wiki. Nothing is read yet here (the wikis load after the first render), so every
// card is the quiet one: its Generate closed, no state word, no figures and no graph row; View only where the tree knows pages.
test('one wiki block per repo of the project, each quiet until the wikis are read', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render()
  for (const repo of ['api', 'web', 'ui']) {
    expect(out).toContain(`Wiki · ${repo}`)
    expect(out.match(new RegExp(`<button[^>]*aria-label="Generar la wiki: Wiki · ${repo}"[^>]*>Generar la wiki</button>`))[0]).toContain('disabled')
  }
  expect(out.match(/>Generar la wiki</g)).toHaveLength(3)
  expect(out).not.toContain('Elige este repo para tener wiki')       // the repeated hint is gone
  expect(out).not.toContain('Grafo del wiki')                        // no graph row until a read says the graph is missing
  expect(out).toMatch(/aria-label="Ver: Wiki · api"/)
  expect(out).not.toMatch(/aria-label="Ver: Wiki · web"/)
  expect(out.match(/cu-btn--primary/g)).toHaveLength(1 + 3 + 1)   // Leer + one action per card + Preguntar
})

// The wiki blocks sit in their own grid, not in the .dk-stack of Machine's stack input (a 14rem column).
test('the wiki blocks are laid out by the wikis grid, not by .dk-stack', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render()
  expect(out).toContain('class="dk-page wide"')
  expect(out).toContain('class="dk-wikis"')
  expect(out).not.toContain('dk-stack')
})

test('with no repos there is no wiki block; the Ask card is still there', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render({ repos: [], docs: [] })
  expect(out).not.toContain('Generar la wiki')
  expect(out).toContain('Construir el explorador C4')
  expect(out).toContain('Preguntar con IA')
})

test('Ask has a question field and a Preguntar button', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render()
  expect(out).toContain('Preguntar con IA')
  expect(out).toMatch(/<input[^>]*aria-label="Pregunta"/)
  expect(out).toMatch(/>Preguntar<\/button>/)
})

test('the strings exist in English', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  setLang('en')
  const out = render()
  expect(out).toContain('Wiki · api')
  expect(out).toContain('Generate the wiki')
  expect(out).not.toContain('Picks this repo for a wiki')
  expect(out).toContain('Ask with AI')
  expect(out).toMatch(/aria-label="Question"/)
  expect(out).toMatch(/>Ask<\/button>/)
})

// A failed build says so in the person's language, the button becomes Retry, and the repeated buttons are told apart.
test('a failed build offers Retry, localized, and every button names its card', () => {
  const failed = { job: null, error: 'Failed to fetch', running: false, run: () => {} }
  const out = renderToStaticMarkup(<BuildCard title="Grafo del wiki · api" hint="h" build={failed} onBuild={() => {}} onView={() => {}} />)
  expect(out).toContain('No llego al servidor del proyecto.')
  expect(out).not.toContain('Failed to fetch')
  expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--secondary cu-btn--sm" aria-label="Reintentar: Grafo del wiki · api">Reintentar<\/button>/)
  expect(out).toMatch(/aria-label="Ver: Grafo del wiki · api">Ver<\/button>/)
  const fresh = renderToStaticMarkup(<BuildCard title="T" hint="h" build={{ job: null, error: '', running: false }} onBuild={() => {}} onView={() => {}} />)
  expect(fresh).toMatch(/aria-label="Construir: T">Construir<\/button>/)
})

// The answer is plain text with its sources as buttons (the window never follows a link to the portal).
test('an answer shows its text and its sources; "none" says so in the app\'s language', () => {
  const view = { kind: 'answer', text: 'It uses JWT.', by: 'claude (haiku)',
    sources: [{ cite: 'architecture/overview.md#Context', hash: '#/docs/architecture/overview.md::Context' }] }
  const out = renderToStaticMarkup(<AnswerView view={view} onOpen={() => {}} />)
  expect(out).toContain('It uses JWT.')
  expect(out).toContain('claude (haiku)')
  expect(out).toMatch(/aria-label="Ver: architecture\/overview.md#Context">architecture\/overview.md#Context<\/button>/)
  expect(out).not.toMatch(/<a [^>]*href=/)
  const bare = renderToStaticMarkup(<AnswerView view={{ ...view, sources: [] }} onOpen={() => {}} />)
  expect(bare).not.toContain('Fuentes')
  expect(renderToStaticMarkup(<AnswerView view={{ kind: 'none' }} onOpen={() => {}} />)).toContain('No he encontrado')
  setLang('en')
  expect(renderToStaticMarkup(<AnswerView view={{ kind: 'none' }} onOpen={() => {}} />)).toContain('I found nothing')
})

// A repo that cannot be generated says why, in the person's language, and its Generate button is closed: the portal
// offered it only for a cloned repo with a wiki engine (canGenerate). `api` already has pages (its card offers View);
// `db` is the cloned repo with an engine and no pages yet, where Generate is the action.
const wikis = [{ repo: 'api', pages: 3, cloned: true, chosen: true, brief: 'ai', canGenerate: true },
  { repo: 'web', pages: 0, cloned: false, chosen: false, brief: null, canGenerate: false },
  { repo: 'ui', pages: 0, cloned: true, chosen: true, brief: null, canGenerate: false },
  { repo: 'db', pages: 0, cloned: true, chosen: true, brief: null, canGenerate: true }]
const block = (i, props = {}) => renderToStaticMarkup(
  <WikiBlock srv={srv} jobs={null} block={wikiBlocks({ repos: ['api', 'web', 'ui', 'db'] }, wikis)[i]} onView={() => {}} onDone={() => {}} {...props} />)
const generate = (out) => out.match(/<button[^>]*aria-label="Generar la wiki[^"]*"[^>]*>/)[0]

test('Generate is enabled for a cloned repo with an engine, closed with its reason otherwise', () => {
  const ok = block(3)
  expect(generate(ok)).not.toContain('disabled')
  expect(ok).not.toContain('no está clonado')
  const uncloned = block(1)
  expect(generate(uncloned)).toContain('disabled')
  expect(uncloned).toContain('Este repo aún no está clonado')
  expect(uncloned).toContain('Máquina')
  const noEngine = block(2)
  expect(generate(noEngine)).toContain('disabled')
  expect(noEngine).toContain('No hay ningún motor de wiki instalado')
  expect(noEngine).not.toContain('aún no está clonado')
  setLang('en')
  expect(block(1)).toContain('This repo is not cloned yet')
  expect(block(2)).toContain('No wiki engine is installed')
})

test('before the wikis are read Generate is closed without a complaint; once reading failed it says so', () => {
  const unread = wikiBlocks({ repos: ['api'], docs: [] }, null)[0]
  const loading = renderToStaticMarkup(<WikiBlock srv={srv} jobs={null} block={unread} loading onView={() => {}} onDone={() => {}} />)
  expect(generate(loading)).toContain('disabled')
  expect(loading).not.toContain('No he podido leer')
  const failed = renderToStaticMarkup(<WikiBlock srv={srv} jobs={null} block={unread} onView={() => {}} onDone={() => {}} />)
  expect(generate(failed)).toContain('disabled')
  expect(failed).toContain('No he podido leer el estado de las wikis')
})

// While another repo's wiki runs, Generate is closed on this one and says why; a reason of its own goes first.
test("Generate is closed while another repo's wiki runs, and says whose", () => {
  const busy = block(3, { busyWith: 'web' })
  expect(generate(busy)).toContain('disabled')
  expect(busy).toContain('Se está generando la wiki de web: espera a que termine para generar otra.')
  expect(block(1, { busyWith: 'api' })).toContain('Este repo aún no está clonado')
  setLang('en')
  expect(block(3, { busyWith: 'web' })).toContain("The wiki of web is being generated: wait for it to finish to generate another.")
})

test('Docs reads the running wiki from the jobs store and closes Generate on the other repos', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const jobs = { get: () => ({ running: [{ id: '1', kind: 'wiki', repo: 'api', status: 'running' }], recent: [], error: '' }),
    subscribe: () => () => {}, refresh: () => {} }
  const out = renderToStaticMarkup(<Docs srv={srv} jobs={jobs} app={{ openExternal: () => {} }} index={index} />)
  expect(out.match(/Se está generando la wiki de api/g)).toHaveLength(2)            // web and ui, not api itself
})

// When GET wikis fails the section says so once, with a Retry; on a failed re-read the cards keep what they showed.
test('a failed read of the wikis offers Retry, in Spanish and English', () => {
  const first = renderToStaticMarkup(<WikisUnread kept={false} onRetry={() => {}} />)
  expect(first).toContain('No he podido leer el estado de las wikis de este proyecto.')
  expect(first).toMatch(/>Reintentar<\/button>/)
  const again = renderToStaticMarkup(<WikisUnread kept onRetry={() => {}} />)
  expect(again).toContain('No he podido volver a leer el estado de las wikis: lo que ves puede estar desactualizado.')
  expect(again).toMatch(/>Reintentar<\/button>/)
  setLang('en')
  expect(renderToStaticMarkup(<WikisUnread kept onRetry={() => {}} />)).toContain('state again: what you see may be out of date.')
  expect(renderToStaticMarkup(<WikisUnread kept={false} onRetry={() => {}} />)).toMatch(/>Try again<\/button>/)
})

// The wiki card in each of its states. Static markup cannot click, so the buttons are read, not pressed: their label, whether
// they are closed and which one is primary. `now` is epoch seconds, as the server's `at`.
const NOW = 1_700_000_000
const idle = { job: null, error: '', running: false }
const failedRun = { job: { status: 'failed', lines: [] }, error: '', running: false }
const runningRun = { job: { status: 'running', lines: [] }, error: '', running: true }
const doneRun = { job: { status: 'done', lines: [] }, error: '', running: false }
const row = (over = {}) => ({ repo: 'api', pages: 12, at: NOW - 3 * 86400, stale: false, old: false, graph: true, graphStale: false,
  brief: 'ai', cloned: true, chosen: true, canGenerate: true, ...over })
const NONE = { pages: 0, at: 0, brief: null }
const wikiCard = (blk, props = {}) => renderToStaticMarkup(<WikiCard block={blk} gen={idle} graph={idle} now={NOW} {...props} />)
const card = (over = {}, props = {}) => wikiCard(wikiBlocks({ repos: ['api'] }, [row(over)])[0], props)
const primary = (out) => out.match(/<button[^>]*cu-btn--primary[^>]*>.*?<\/button>/)[0]
const STATES = [
  ['none', NONE, {}, 'Generar la wiki'],
  ['stale', { stale: true }, {}, 'Actualizar'],
  ['old', { old: true }, {}, 'Ampliar'],
  ['fresh', {}, {}, 'Ver'],
  ['failed', {}, { gen: failedRun }, 'Reintentar'],
  ['generating', {}, { gen: runningRun }, 'Generando…'],
]

test.each(STATES)('a %s wiki card says its state and has one primary action', (state, over, props, label) => {
  const out = card(over, props)
  expect(out).toContain(`data-wiki-state="${state}"`)
  expect(out).toMatch(new RegExp(`class="[^"]*\\bdk-run dk-wiki is-${state}\\b`))
  expect(out.match(/cu-btn--primary/g)).toHaveLength(1)
  expect(primary(out)).toContain(label)
  expect(out).toMatch(/<svg[^>]*aria-hidden="true"/)               // its icon, always beside its word
})

test('whatever closes a card, it keeps exactly one primary action', () => {
  for (const props of [{ loading: true }, { busyWith: 'web' }, { gen: runningRun, busyWith: 'web' }])
    for (const [, over, extra] of STATES) expect(card(over, { ...extra, ...props }).match(/cu-btn--primary/g)).toHaveLength(1)
  const closed = wikiBlocks({ repos: ['api'] }, [row({ ...NONE, cloned: false, canGenerate: false })])[0]
  expect(wikiCard(closed).match(/cu-btn--primary/g)).toHaveLength(1)
})

test('generating holds a closed primary with the thinking label; a failed run says so in the status line', () => {
  const out = card({}, { gen: runningRun })
  expect(primary(out)).toContain('disabled')
  expect(primary(out)).toContain('aria-busy="true"')
  expect(primary(out)).toContain('<span class="cu-thinking">Generando…</span>')
  expect(primary(out)).toContain('aria-label="Generando…: Wiki · api"')
  expect(out).toContain('Escribiendo las páginas')
  expect(out).not.toContain('12 páginas')                          // no counter that is not live
  expect(card({}, { gen: failedRun })).toContain('La última generación falló')
})

test('the status line has the state word and its figures: pages, when it was written, the brief', () => {
  const out = card()
  expect(out).toContain('Al día')
  expect(out).toContain('12 páginas')
  expect(out).toContain('escrita hace 3 d')
  expect(out).toContain('brief con IA')
  expect(card({ pages: 1 })).toContain('1 página ·')
  expect(card({ pages: 1 })).not.toContain('1 páginas')
  expect(card({ stale: true })).toContain('Desfasada')
  expect(card({ old: true })).toContain('Alcance anterior')
  expect(card({ ...NONE, brief: 'starter' })).toContain('brief inicial')
  expect(card({ ...NONE, brief: 'starter' })).not.toContain('escrita')    // nothing was written yet
})

test('View is a ghost button whenever there are pages and it is not already the primary action', () => {
  const views = (out) => out.match(/aria-label="Ver: Wiki · api"/g)?.length ?? 0
  expect(views(card())).toBe(1)                                    // fresh: View is the primary one, there is no second View
  expect(primary(card())).toContain('Ver')
  for (const over of [{ stale: true }, { old: true }]) {
    expect(views(card(over))).toBe(1)
    expect(card(over)).toMatch(/cu-btn--ghost[^>]*aria-label="Ver: Wiki · api"/)
  }
  expect(card({}, { gen: failedRun })).toMatch(/cu-btn--ghost[^>]*aria-label="Ver: Wiki · api"/)
  expect(card({}, { gen: runningRun })).toMatch(/cu-btn--ghost[^>]*aria-label="Ver: Wiki · api"/)
  expect(views(card(NONE))).toBe(0)                                // nothing to view yet
})

test('the graph row shows with pages and a missing or stale graph, and keeps its job while it has something to say', () => {
  const graphRow = (out) => out.includes('Grafo del wiki · api')
  expect(graphRow(card({ graph: true, graphStale: false }))).toBe(false)
  expect(graphRow(card({ graph: false }))).toBe(true)
  expect(card({ graph: false })).toContain('aria-label="Construir el grafo: Grafo del wiki · api"')
  expect(card({ graph: true, graphStale: true })).toContain('aria-label="Reconstruir el grafo: Grafo del wiki · api"')
  expect(graphRow(card({ ...NONE, graph: false }))).toBe(false)    // no pages, no graph
  expect(graphRow(card({ graph: true, graphStale: false }, { graph: doneRun }))).toBe(true)   // the result of the click stays
  expect(card({ graph: false }, { graph: failedRun })).toContain('aria-label="Reintentar: Grafo del wiki · api"')
})

// `wikiState` calls a row that was never read "fresh" (its info is only defaults): the card says nothing instead.
test('before the wikis are read the card shows no state word and no figures, and its action is closed', () => {
  const loading = card({ stale: true }, { loading: true })
  for (const word of ['Al día', 'Desfasada', 'Alcance anterior', '12 páginas', 'escrita', 'brief con IA']) expect(loading).not.toContain(word)
  expect(loading).toContain('data-wiki-state="unread"')
  expect(primary(loading)).toContain('disabled')
  expect(loading).not.toContain('Grafo del wiki')
  const tree = wikiCard(wikiBlocks({ repos: ['api'], docs: [{ path: 'repos/api/a.md', space: 'wiki' }] }, null)[0])
  expect(tree).not.toContain('Al día')                             // the tree says there are pages, not that they are current
  expect(tree).toContain('data-wiki-state="unread"')
  expect(primary(tree)).toContain('disabled')
  expect(tree).toContain('No he podido leer el estado de las wikis')
  expect(tree).toMatch(/aria-label="Ver: Wiki · api"/)             // the pages can still be opened in the portal
})

test('a blocked card with no pages shows its reason and a closed Generate; with pages it keeps its state and View', () => {
  const uncloned = card({ ...NONE, cloned: false, canGenerate: false })
  expect(uncloned).toContain('data-wiki-state="blocked"')
  expect(uncloned).toContain('Este repo aún no está clonado')
  expect(primary(uncloned)).toContain('Generar la wiki')
  expect(primary(uncloned)).toContain('disabled')
  expect(card({ ...NONE, canGenerate: false })).toContain('No hay ningún motor de wiki instalado')
  const stale = card({ stale: true, canGenerate: false })
  expect(stale).toContain('data-wiki-state="stale"')
  expect(stale).toContain('No hay ningún motor de wiki instalado')
  expect(primary(stale)).toContain('Actualizar')
  expect(primary(stale)).toContain('disabled')
  expect(stale).toMatch(/cu-btn--ghost[^>]*aria-label="Ver: Wiki · api">Ver<\/button>/)
  const fresh = card({ canGenerate: false })
  expect(primary(fresh)).toContain('Ver')                          // viewing pages that exist needs no engine
  expect(primary(fresh)).not.toContain('disabled')
})

// The reason is for the action it closes: a card whose only primary is View (pages, nothing to write) has nothing closed to explain.
test('the reason shows only when the card\'s write action is closed, never beside an open View', () => {
  for (const [over, reason] of [[{ canGenerate: false }, 'No hay ningún motor de wiki instalado'],
    [{ cloned: false, canGenerate: false }, 'Este repo aún no está clonado']]) {
    const fresh = card(over)
    expect(primary(fresh)).toContain('Ver')
    expect(primary(fresh)).not.toContain('disabled')
    expect(fresh).not.toContain(reason)
    const stale = card({ ...over, stale: true })
    expect(primary(stale)).toContain('Actualizar')
    expect(primary(stale)).toContain('disabled')
    expect(stale).toContain(reason)
    const failed = card(over, { gen: failedRun })
    expect(primary(failed)).toContain('disabled')
    expect(failed).toContain(reason)
    expect(card({ ...over, old: true })).toContain(reason)
  }
  expect(card({ ...NONE, canGenerate: false })).toContain('No hay ningún motor de wiki instalado')
})

test("another repo's run closes what writes pages on this card, with the reason, and leaves View alone", () => {
  const stale = card({ stale: true }, { busyWith: 'web' })
  expect(primary(stale)).toContain('disabled')
  expect(stale).toContain('Se está generando la wiki de web')
  const fresh = card({}, { busyWith: 'web' })
  expect(primary(fresh)).not.toContain('disabled')
  expect(fresh).not.toContain('Se está generando la wiki de web')
  expect(primary(card({ stale: true }))).not.toContain('disabled')
})

test('a finished run shows the card as fresh at once, before the wikis are read again, and pops its icon in', () => {
  const out = card(NONE, { gen: doneRun })
  expect(out).toContain('data-wiki-state="fresh"')
  expect(out).toMatch(/class="[^"]*\bis-done\b/)
  expect(primary(out)).toContain('Ver')
  expect(card(NONE)).not.toContain('is-done')
})

test('cards rise in one after another, up to a cap', () => {
  expect(card({}, { index: 0 })).toContain('style="--i:0"')
  expect(card({}, { index: 3 })).toContain('style="--i:3"')
  expect(card({}, { index: 40 })).toContain('style="--i:8"')
})

test('the wiki card speaks English', () => {
  setLang('en')
  expect(primary(card({ stale: true }))).toContain('>Update<')
  expect(primary(card({ old: true }))).toContain('>Expand<')
  expect(primary(card())).toContain('>View<')
  expect(primary(card({}, { gen: failedRun }))).toContain('>Try again<')
  expect(primary(card({}, { gen: runningRun }))).toContain('>Generating…<')
  expect(primary(card(NONE))).toContain('>Generate the wiki<')
  const out = card()
  for (const text of ['Up to date', '12 pages', 'written 3 d ago', 'AI brief']) expect(out).toContain(text)
  expect(card({ pages: 1 })).toContain('1 page ·')
  expect(card({ graph: false })).toContain('aria-label="Build the graph: Wiki graph · api"')
  expect(card({ graph: true, graphStale: true })).toContain('Rebuild the graph')
})

// The section's cards by what GET wikis read (useWikis' state). Rows never read (the first read in flight, or a first read that
// failed: the tree fallback) are only defaults, so those cards are quiet. A failed re-read keeps the last good rows: the cards keep
// their state and actions, and the one notice above says it may be out of date.
const grid = (wikis) => renderToStaticMarkup(
  <WikiGrid srv={srv} jobs={null} index={index} wikis={{ reload: () => {}, ...wikis }} running={[]} open={() => {}} />)
const primaries = (out) => out.match(/<button[^>]*cu-btn--primary[^>]*>/g)

test('while the first read is in flight every card is quiet: no state word, no figures, closed', () => {
  const out = grid({ rows: null, loading: true, failed: false })
  expect(out.match(/data-wiki-state="unread"/g)).toHaveLength(3)
  for (const word of ['Al día', 'Desfasada', 'Alcance anterior', 'Sin páginas todavía', 'páginas ·', 'escrita']) expect(out).not.toContain(word)
  expect(primaries(out).every((b) => b.includes('disabled'))).toBe(true)
  expect(out).not.toContain('No he podido')
})

test('a failed re-read keeps the last good state of each card and its actions, and the notice is said once', () => {
  const rows = [row({ repo: 'api' }), row({ repo: 'web', stale: true })]
  const out = grid({ rows, loading: false, failed: true })
  expect(out).toContain('data-wiki-state="fresh"')
  expect(out).toContain('data-wiki-state="stale"')
  expect(out).not.toContain('data-wiki-state="unread"')
  for (const text of ['Al día', 'Desfasada', '12 páginas']) expect(out).toContain(text)
  expect(out).toMatch(/escrita hace \d+ d/)                                          // the section's own clock, not the test's NOW
  expect(primaries(out)).toHaveLength(2)
  expect(primaries(out).some((b) => b.includes('disabled'))).toBe(false)
  expect(primaries(out).map((b) => b.match(/aria-label="([^:]*):/)[1])).toEqual(['Ver', 'Actualizar'])
  expect(out.match(/No he podido volver a leer el estado de las wikis/g)).toHaveLength(1)
})

test('a first read that failed leaves quiet cards and says it once, above, not in each card', () => {
  const out = grid({ rows: null, loading: false, failed: true })
  expect(out.match(/data-wiki-state="unread"/g)).toHaveLength(3)
  expect(out).not.toContain('Al día')
  expect(primaries(out).every((b) => b.includes('disabled'))).toBe(true)
  expect(out.match(/No he podido leer el estado de las wikis/g)).toHaveLength(1)    // the notice, not a line per card
})

test('the card repeats the unread reason only when nobody said it above', () => {
  const unread = wikiBlocks({ repos: ['api'], docs: [{ path: 'repos/api/a.md', space: 'wiki' }] }, null)[0]
  expect(wikiCard(unread)).toContain('No he podido leer el estado de las wikis')
  expect(wikiCard(unread, { failed: true })).not.toContain('No he podido leer')
  expect(wikiCard(unread, { loading: true })).not.toContain('No he podido leer')
  expect(primary(wikiCard(unread, { failed: true }))).toContain('disabled')
  const kept = wikiBlocks({ repos: ['api'] }, [row({ stale: true })])[0]
  const out = wikiCard(kept, { failed: true })                                       // last good rows: not quiet because a re-read failed
  expect(out).toContain('data-wiki-state="stale"')
  expect(primary(out)).not.toContain('disabled')
  const wired = renderToStaticMarkup(<WikiBlock srv={srv} jobs={null} block={unread} failed onView={() => {}} onDone={() => {}} />)
  expect(wired).not.toContain('No he podido leer')
})

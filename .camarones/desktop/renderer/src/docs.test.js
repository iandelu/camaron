import { expect, test } from 'vitest'
import { answerView, askBody, askError, buildFailed, c4Card, citeHash, docsHealth, openPortal, portalUrl, startBuild, startWiki,
  wikiAction, wikiBlocks, wikiBusyWith, wikiError, wikiRepos, wikiState, wikisRead } from './docs.js'
import { setLang, t } from './i18n.js'

// The portal is the reader, on the project's own server one folder up from /desktop/; the window opens it in the
// system browser (main.cjs's guard sends same-origin addresses outside /desktop/ there).
test('the portal lives at the root of the project server', () => {
  expect(portalUrl('http://127.0.0.1:5123', '#/')).toBe('http://127.0.0.1:5123/#/')
  expect(portalUrl('http://127.0.0.1:5123', '#/review')).toBe('http://127.0.0.1:5123/#/review')
  expect(portalUrl('http://127.0.0.1:5123')).toBe('http://127.0.0.1:5123/#/')
  expect(portalUrl('http://127.0.0.1:5123/', '#/')).toBe('http://127.0.0.1:5123/#/')    // a trailing slash is not doubled
})

// The portal reads a page's space ('wiki' for a repo's OpenWiki, at repos/<repo>/<page>): the repos with at least one
// wiki page are the ones whose graph can be built (app.wiki.wiki_graph is False without pages).
test('the repos with a wiki are the ones with wiki pages, once each, in order', () => {
  const tree = { docs: [
    { path: 'index.md', space: 'docs' },
    { path: 'repos/api/index.md', space: 'wiki' },
    { path: 'repos/api/auth.md', space: 'wiki' },
    { path: 'repos/web/index.md', space: 'docs' },           // a repo's own page in the docs space: not a wiki
    { path: 'repos/ui/a.md', space: 'wiki' },
    { path: 'interview/x.md', space: 'notes' }] }
  expect(wikiRepos(tree)).toEqual(['api', 'ui'])
  expect(wikiRepos({ docs: [] })).toEqual([])
  expect(wikiRepos(null)).toEqual([])
  expect(wikiRepos({})).toEqual([])
})

// What the Docs section does, without a DOM: the blocks it shows, what each button posts and where Ver / Leer… send the window.
// `repos` is every repo of the project (the tree's `repos`, docs.repo_names()); `docs` says which already have a wiki.
const index = { repos: ['api', 'web', 'ui'], docs: [{ path: 'repos/api/a.md', space: 'wiki' }, { path: 'repos/ui/a.md', space: 'wiki' },
  { path: 'repos/web/index.md', space: 'docs' }] }

test('the C4 card builds the explorer and the portal shows it at #/c4', () => {
  expect(c4Card).toEqual({ id: 'c4', repo: '', body: { what: 'c4' }, hash: '#/c4' })
})

// GET wikis (app.wiki.wikis(), what the portal's Wikis view reads): per repo, in the project's
// order, whether it is cloned, chosen, has a brief ('ai' | 'starter' | null) and pages, and
// canGenerate (= cloned and a wiki engine installed).
const wikis = [
  { repo: 'api', pages: 3, cloned: true, chosen: true, brief: 'ai', canGenerate: true },
  { repo: 'web', pages: 0, cloned: false, chosen: false, brief: null, canGenerate: false },
  { repo: 'ui', pages: 2, cloned: true, chosen: true, brief: 'starter', canGenerate: false }]

test("one wiki block per repo of the project, from GET wikis, in the project's order", () => {
  const blocks = wikiBlocks(index, wikis)
  expect(blocks.map((b) => b.repo)).toEqual(['api', 'web', 'ui'])
  expect(blocks.map((b) => b.hasWiki)).toEqual([true, false, true])
  expect(blocks[1]).toEqual({ repo: 'web', hasWiki: false, blocked: 'notCloned', hash: '#/wiki/web',
    body: { repo: 'web', choose: true, starter: true },
    info: { pages: 0, at: 0, stale: false, old: false, graph: false, graphStale: false, brief: null },
    graph: { id: 'wiki:web', repo: 'web', body: { what: 'wiki-graph', repo: 'web' }, hash: '#/wiki/web' } })
  expect(wikiBlocks(index, [])).toEqual([])
})

// The portal offered Generate only where canGenerate: a repo not cloned has nothing to document (and choosing it would
// change the plan for nothing); without an engine the run fails after choosing and writing the brief.
test('Generate is open for a cloned repo with an engine, and says why when it is not', () => {
  expect(wikiBlocks(index, wikis).map((b) => b.blocked)).toEqual([null, 'notCloned', 'noEngine'])
  const both = wikiBlocks(index, [{ repo: 'x', pages: 0, cloned: false, chosen: false, brief: null, canGenerate: false }])
  expect(both[0].blocked).toBe('notCloned')                                  // not cloned wins over no engine
})

// wiki(b): `choose` only matters (and is only required) for a repo that is not chosen and has no pages; `starter` writes a
// brief when there is none. The portal sent each only when needed, so the body does too.
test('the body asks to choose the repo only if it is not chosen, and for a starter brief only if there is no brief', () => {
  const body = (row) => wikiBlocks({ repos: ['r'] }, [{ repo: 'r', pages: 0, cloned: true, chosen: true, brief: null, canGenerate: true, ...row }])[0].body
  expect(body({})).toEqual({ repo: 'r', starter: true })                      // chosen, no brief yet
  expect(body({ chosen: false })).toEqual({ repo: 'r', choose: true, starter: true })
  expect(body({ brief: 'starter' })).toEqual({ repo: 'r' })
  expect(body({ brief: 'ai', chosen: false })).toEqual({ repo: 'r', choose: true })
  expect(body({ pages: 4, chosen: false })).toEqual({ repo: 'r', choose: true })   // has pages: no starter brief
  expect(wikiBlocks(index, wikis).map((b) => b.body)).toEqual([{ repo: 'api' }, { repo: 'web', choose: true, starter: true }, { repo: 'ui' }])
})

// If GET wikis cannot be read the blocks still list every repo (the tree's `repos`), with Generate closed: nothing is
// known about whether it is cloned or has an engine.
test('without the wikis payload the repos of the tree are listed with Generate closed', () => {
  const blocks = wikiBlocks(index, null)
  expect(blocks.map((b) => [b.repo, b.hasWiki, b.blocked])).toEqual([['api', true, 'unread'], ['web', false, 'unread'], ['ui', true, 'unread']])
  expect(wikiBlocks(null, null)).toEqual([])
  expect(wikiBlocks({ docs: [] }, null)).toEqual([])
})

test('Generate posts the body; Build posts the C4 or graph body to build', async () => {
  const posts = []
  const srv = { post: async (path, body) => { posts.push([path, body]); return { id: '7' } } }
  const [api, web] = wikiBlocks(index, wikis)
  await startWiki(srv, api)
  await startWiki(srv, web)
  await startBuild(srv, c4Card)
  await startBuild(srv, web.graph)
  expect(posts).toEqual([['wiki', { repo: 'api' }], ['wiki', { repo: 'web', choose: true, starter: true }],
    ['build', { what: 'c4' }], ['build', { what: 'wiki-graph', repo: 'web' }]])
})

test('the portal opens in the browser with its address', () => {
  const opened = []
  const app = { openExternal: (u) => { opened.push(u) } }
  openPortal(app, 'http://127.0.0.1:5000', '#/')
  openPortal(app, 'http://127.0.0.1:5000', '#/review')
  openPortal(app, 'http://127.0.0.1:5000', '#/search')
  for (const h of [c4Card.hash, ...wikiBlocks(index, wikis).map((b) => b.hash)]) openPortal(app, 'http://127.0.0.1:5000', h)
  expect(opened).toEqual(['http://127.0.0.1:5000/#/', 'http://127.0.0.1:5000/#/review', 'http://127.0.0.1:5000/#/search',
    'http://127.0.0.1:5000/#/c4', 'http://127.0.0.1:5000/#/wiki/api', 'http://127.0.0.1:5000/#/wiki/web', 'http://127.0.0.1:5000/#/wiki/ui'])
  expect(() => openPortal({}, 'http://x', '#/')).not.toThrow()           // a window without the bridge: nothing happens
})

test('a build failed when the POST was rejected or the job ended failed (not when it was stopped)', () => {
  expect(buildFailed({ error: 'Failed to fetch', job: null })).toBe(true)
  expect(buildFailed({ error: '', job: { status: 'failed', lines: [] } })).toBe(true)
  expect(buildFailed({ error: '', job: { status: 'failed', stopped: true, lines: [] } })).toBe(false)
  expect(buildFailed({ error: '', job: { status: 'done', lines: [] } })).toBe(false)
  expect(buildFailed({ error: '', job: null })).toBe(false)
})

// POST ask/answer takes {q}; an empty question is never sent (answers.answer would spend a model call on nothing).
test('the question is trimmed, and an empty one is not sent', () => {
  expect(askBody('  how does auth work?  ')).toEqual({ q: 'how does auth work?' })
  expect(askBody('')).toBeNull()
  expect(askBody('   \n ')).toBeNull()
  expect(askBody(undefined)).toBeNull()
})

// A cite is "<path>" or "<path>#<section>": its page under #/docs/<path>, a section after "::" (portal core.hrefFor).
// A wiki page's path is repos/<repo>/<page> (docs.iter_docs), like a repo's own pages: the portal's router sends
// #/docs/<a wiki page> on to #/wiki/<repo>/<page>, so the app need not tell them apart.
test('a source becomes the portal address of its page', () => {
  expect(citeHash('architecture/overview.md#Context')).toBe('#/docs/architecture/overview.md::Context')
  expect(citeHash('repos/web/index.md')).toBe('#/docs/repos/web/index.md')
  expect(citeHash('repos/api/auth.md#Login')).toBe('#/docs/repos/api/auth.md::Login')
  expect(citeHash('repos/api/deep/x.md')).toBe('#/docs/repos/api/deep/x.md')
  expect(citeHash('repos/api/wiki/x.md')).toBe('#/docs/repos/api/wiki/x.md')     // a folder named wiki is no special case
  expect(citeHash('guides/lang.md#C# and F#')).toBe('#/docs/guides/lang.md::C# and F#')   // only the first # splits
})

// answers.answer: {answer, cited, runner, model, seconds…}; answer is null when the docs had nothing or the model said
// nothing (cited is then empty). The sources are only those the retrieval knew.
test('an answer with sources, one without, and the "nothing to answer" state', () => {
  const full = answerView({ answer: 'It uses JWT.', cited: ['architecture/overview.md#Context', 'repos/api/auth.md'],
    runner: 'claude', model: 'haiku', seconds: 4.2 })
  expect(full).toEqual({ kind: 'answer', text: 'It uses JWT.', by: 'claude (haiku)',
    sources: [{ cite: 'architecture/overview.md#Context', hash: '#/docs/architecture/overview.md::Context' },
      { cite: 'repos/api/auth.md', hash: '#/docs/repos/api/auth.md' }] })
  const bare = answerView({ answer: 'No idea.', cited: [], runner: 'codex', model: null })
  expect(bare).toEqual({ kind: 'answer', text: 'No idea.', by: 'codex', sources: [] })
  expect(answerView({ answer: 'x' }).sources).toEqual([])          // no cited key at all
  expect(answerView({ answer: null, cited: [], runner: 'claude' })).toEqual({ kind: 'none' })
  expect(answerView({ answer: '', cited: [] })).toEqual({ kind: 'none' })
  expect(answerView(null)).toEqual({ kind: 'none' })
})

// answers.answer raises RuntimeError (HTTP 400 {error: text}) in English: the person gets es/en sentences, not that text.
test("the server's \"no AI\" and \"too slow\" refusals are said in the app's language", () => {
  const noAi = { message: 'no AI answer here: no runner for bounded work (or ask.ai is false in workspace.yaml)' }
  const slow = { message: 'no answer within 90 s: claude is slow or waiting for a login; try again or set a faster model with `ask: {model: …}` in workspace.yaml' }
  setLang('es')
  expect(askError(noAi, t)).toBe(t('docs.askNoAi'))
  expect(askError(slow, t)).toBe(t('docs.askSlow'))
  expect(askError({ message: 'Failed to fetch' }, t)).toBe('No llego al servidor del proyecto.')
  expect(askError({ message: 'boom' }, t)).toBe('El servidor lo ha rechazado: boom')
  setLang('en')
  expect(askError(noAi, t)).toBe('There is no AI to answer here: no agent is available, or ask.ai is off in workspace.yaml.')
  expect(askError(slow, t)).toBe(t('docs.askSlow'))
  setLang('es')
})

// One wiki runs at a time on the server (routes/analysis.py wiki(): another repo's start is 409 busy). The jobs store's
// running list says which repo's runs: Generate closes on the others; the repo that runs keeps its own button.
test('a wiki running for one repo closes Generate on the others', () => {
  const running = [{ id: '1', kind: 'wiki', repo: 'api', status: 'running' }, { id: '2', kind: 'c4', status: 'running' }]
  expect(wikiBusyWith(running, 'web')).toBe('api')
  expect(wikiBusyWith(running, 'api')).toBe('')
  expect(wikiBusyWith([{ id: '2', kind: 'c4', status: 'running' }], 'web')).toBe('')
  expect(wikiBusyWith([], 'web')).toBe('')
  expect(wikiBusyWith(undefined, 'web')).toBe('')
})

test('busy from POST wiki has its own sentence, in Spanish and English; anything else as before', () => {
  setLang('es')
  expect(wikiError(new Error('busy'), t)).toBe('Ya se está generando la wiki de otro repo: espera a que termine y vuelve a probar.')
  expect(wikiError(new Error('Failed to fetch'), t)).toBe(t('obErrNetwork'))
  setLang('en')
  expect(wikiError(new Error('busy'), t)).toBe("Another repo's wiki is being generated: wait for it to finish and try again.")
  setLang('es')
})

// GET wikis, read on mount and again after a run: a failed first read leaves no rows (the blocks say they are unread);
// a failed re-read keeps the last good rows. Either way `failed` is set, and the section offers a Retry.
test('a failed read of the wikis keeps the last good rows and says it failed', () => {
  const start = { rows: null, loading: true, failed: false }
  const rows = [{ repo: 'api', pages: 1 }]
  const read = wikisRead(start, { rows })
  expect(read).toEqual({ rows, loading: false, failed: false })
  expect(wikisRead(start, { error: true })).toEqual({ rows: null, loading: false, failed: true })
  expect(wikisRead(read, { error: true })).toEqual({ rows, loading: false, failed: true })
  expect(wikisRead({ rows, loading: false, failed: true }, { rows: [] })).toEqual({ rows: [], loading: false, failed: false })
})

// The GET wikis row's own facts ride on the block (the card reads them): an unread row (the tree fallback) carries the defaults.
test('a block carries its row\'s info, and the defaults when the wikis were not read', () => {
  const row = { repo: 'api', pages: 3, at: 1700000000, stale: true, old: false, graph: true, graphStale: true, brief: 'ai', cloned: true, chosen: true, canGenerate: true }
  expect(wikiBlocks(index, [row])[0].info).toEqual({ pages: 3, at: 1700000000, stale: true, old: false, graph: true, graphStale: true, brief: 'ai' })
  const unread = wikiBlocks(index, null)
  expect(unread.map((b) => b.info)).toEqual(Array(3).fill({ pages: 0, at: 0, stale: false, old: false, graph: false, graphStale: false, brief: null }))
})

// Precedence: generating > failed > none (no pages) > old > stale > fresh.
const blk = (hasWiki, info = {}) => ({ repo: 'r', hasWiki, info: { pages: hasWiki ? 3 : 0, stale: false, old: false, ...info } })

test('a wiki card is in exactly one state, by precedence', () => {
  expect(wikiState(blk(true))).toBe('fresh')
  expect(wikiState(blk(true, { stale: true }))).toBe('stale')
  expect(wikiState(blk(true, { old: true }))).toBe('old')
  expect(wikiState(blk(true, { stale: true, old: true }))).toBe('old')                 // old beats stale
  expect(wikiState(blk(false))).toBe('none')
  expect(wikiState(blk(false, { stale: true, old: true }))).toBe('none')               // no pages beats old and stale
  expect(wikiState(blk(true, { stale: true }), { failed: true })).toBe('failed')
  expect(wikiState(blk(false), { failed: true })).toBe('failed')                       // failed beats none
  expect(wikiState(blk(true, { stale: true }), { running: true })).toBe('generating')
  expect(wikiState(blk(false), { running: true, failed: true })).toBe('generating')    // generating beats failed
  expect(wikiState(blk(true), {})).toBe('fresh')
})

test('the tree fallback block (pages in the tree, no row) is judged by hasWiki', () => {
  const [api, web] = wikiBlocks(index, null)
  expect([wikiState(api), wikiState(web)]).toEqual(['fresh', 'none'])
})

test('each state has one primary action, none while generating', () => {
  expect(wikiAction('none')).toEqual({ kind: 'generate', mode: '', label: 'docs.generate' })
  expect(wikiAction('stale')).toEqual({ kind: 'update', mode: 'update', label: 'docs.update' })
  expect(wikiAction('old')).toEqual({ kind: 'update', mode: 'update', label: 'docs.expand' })
  expect(wikiAction('failed')).toEqual({ kind: 'retry', mode: '', label: 'retry' })
  expect(wikiAction('fresh')).toEqual({ kind: 'view', mode: '', label: 'docs.view' })
  expect(wikiAction('generating')).toEqual({ kind: null })
})

const full = {
  summary: { draft: 2, 'needs-reconfirm': 1, orphans: 3, untranslated: 4, confirmed: 9, total: 12 }, feedback: 5 }
const rows = [{ repo: 'a', pages: 3 }, { repo: 'b', pages: 3, stale: true }, { repo: 'c', pages: 2, old: true }, { repo: 'd', pages: 0 },
  { repo: 'e', pages: 0, stale: true }, { repo: 'f', pages: 1, stale: true, old: true }]
const chips = (c) => c.map((x) => [x.key, x.tone, x.n])

test('the health header counts docs, wikis and C4 from what is already read', () => {
  const got = docsHealth(full, rows, { c4: { exists: true, stale: true, model: true } })
  expect(chips(got)).toEqual([
    ['drafts', 'warn', 2], ['reconfirm', 'warn', 1], ['orphans', 'warn', 3], ['untranslated', 'warn', 4], ['feedback', 'info', 5],
    ['wikiStale', 'warn', 1], ['wikiOld', 'warn', 2], ['wikiNone', 'info', 2], ['wikiFresh', 'ok', 1],
    ['c4Stale', 'warn', null]])
  expect(got.map((x) => x.text)).toEqual(['docs.h.drafts', 'docs.h.reconfirm', 'docs.h.orphans', 'docs.h.untranslated', 'docs.h.feedback',
    'docs.h.wikiStale', 'docs.h.wikiOld', 'docs.h.wikiNone', 'docs.h.wikiFresh', 'docs.h.c4Stale'])
})

test('a wiki row counts in the bucket of the card it will be: no pages, old, stale, fresh', () => {
  const got = docsHealth({}, rows, null)
  expect(chips(got)).toEqual([['wikiStale', 'warn', 1], ['wikiOld', 'warn', 2], ['wikiNone', 'info', 2], ['wikiFresh', 'ok', 1]])
  expect(docsHealth({}, [{ pages: 0, stale: true, old: true }], null).map((x) => x.key)).toEqual(['wikiNone'])   // no pages wins
})

test('the C4 chip is current, stale or not built', () => {
  const c4 = (v) => chips(docsHealth({}, null, { c4: v }))
  expect(c4({ exists: true, stale: false, model: true })).toEqual([['c4Fresh', 'ok', null]])
  expect(c4({ exists: true, stale: true, model: true })).toEqual([['c4Stale', 'warn', null]])
  expect(c4({ exists: false, stale: false, model: false })).toEqual([['c4None', 'info', null]])
  expect(c4({ exists: false, stale: true, model: true })).toEqual([['c4None', 'info', null]])   // nothing built: not stale
})

test('an unread source gives no chip, never a zero', () => {
  expect(chips(docsHealth(full, null, null)).map(([k]) => k)).toEqual(['drafts', 'reconfirm', 'orphans', 'untranslated', 'feedback'])
  expect(docsHealth({}, null, null)).toEqual([])
  expect(docsHealth(null, null, null)).toEqual([])
  expect(docsHealth({}, null, {})).toEqual([])                                         // viewers without c4: nothing to say
})

test('an all-clear index shows only the good news of what was read', () => {
  const clear = { summary: { draft: 0, 'needs-reconfirm': 0, orphans: 0, untranslated: 0 }, feedback: 0 }
  const got = docsHealth(clear, [{ pages: 4 }], { c4: { exists: true, stale: false, model: true } })
  expect(chips(got)).toEqual([['wikiFresh', 'ok', 1], ['c4Fresh', 'ok', null]])
  expect(docsHealth(clear, [], null)).toEqual([])                                      // an array with no rows: no bucket, no chip
})

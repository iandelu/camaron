import { expect, test, vi } from 'vitest'
import { actOnMiss, answerView, askError, buildFailed, c4Card, citeHash, docsHealth, lastMiss, missAction, missesOf, openPortal, portalUrl, readMisses,
  readViewers, seeksStale, STALE_WIKIS, startBuild, startWiki, stripState, viewersRead, wikiAction, wikiBlocks, wikiBusyWith, wikiError, wikiRepos, wikiRequest, wikiRunning, wikiRuns,
  wikiRunsEnded, wikiState, wikisRead } from './docs.js'
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

// Update is the same POST wiki with `mode`; a state whose action has no mode sends the block's body untouched.
test('the wiki request is the block body plus the action\'s mode, only when it has one', () => {
  const [api, web] = wikiBlocks(index, wikis)
  expect(wikiRequest(api, wikiAction('stale'))).toEqual({ repo: 'api', mode: 'update' })
  expect(wikiRequest(api, wikiAction('old'))).toEqual({ repo: 'api', mode: 'update' })
  expect(wikiRequest(api, wikiAction('failed'))).toEqual({ repo: 'api' })
  expect(wikiRequest(web, wikiAction('none'))).toEqual({ repo: 'web', choose: true, starter: true })
  expect(wikiRequest(api, {})).toEqual({ repo: 'api' })
  expect(wikiRequest(api)).toEqual({ repo: 'api' })
  expect(api.body).toEqual({ repo: 'api' })                                            // the block is not mutated
})

test('startWiki posts the request of the action it is given', async () => {
  const posts = []
  const srv = { post: async (path, body) => { posts.push([path, body]); return { id: '9' } } }
  const [api] = wikiBlocks(index, wikis)
  await startWiki(srv, api, wikiAction('stale'))
  expect(posts).toEqual([['wiki', { repo: 'api', mode: 'update' }]])
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

// routes/chat.py refuses a turn sent while another runs (409 busy): a plain sentence, never the server's English.
test('a turn refused because another still runs is said in the app\'s language', () => {
  const busy = { message: 'busy: a chat turn is still running', status: 409 }
  setLang('es')
  expect(askError(busy, t)).toBe('Todavía estoy respondiendo a la pregunta anterior: espera a que termine.')
  expect(askError(busy.message, t)).toBe(t('docs.chat.busy'))
  setLang('en')
  expect(askError(busy, t)).toBe('I am still answering the previous question: wait for it to finish.')
  setLang('es')
})

// lib/chat.py turn(): a runner that was asked and gave nothing usable fails the turn naming who (`runner` or `runner:model`).
test('a runner that gave no answer is named in a sentence of the app\'s language', () => {
  const none = 'claude:haiku gave no answer: is it signed in, and does it have that model?'
  setLang('es')
  expect(askError({ message: none }, t)).toBe('claude:haiku no ha contestado: ¿ha iniciado sesión y tiene ese modelo?')
  expect(askError(none, t)).toBe('claude:haiku no ha contestado: ¿ha iniciado sesión y tiene ese modelo?')
  expect(askError('gemini gave no answer: is it signed in, and does it have that model?', t)).toMatch(/^gemini no ha contestado/)
  setLang('en')
  expect(askError({ message: none }, t)).toBe('claude:haiku gave no answer: is it signed in, and does it have that model?')
  setLang('es')
  expect(askError({ message: 'it gave no answer' }, t)).toBe('El servidor lo ha rechazado: it gave no answer')
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

// A chat turn that found nothing is written to the misses (lib/usage.py) as it ends: the card reads them again each time a new one
// lands in the conversation, keyed on that reply's id (0 while there is none).
test('the newest chat reply that found nothing, as the misses card\'s cue to read again', () => {
  const q = (id) => ({ id, role: 'user', text: 'q' })
  const none = (id) => ({ id, role: 'assistant', text: '', result: { answer: null, cited: [] } })
  const said = (id) => ({ id, role: 'assistant', text: 'yes', result: { answer: 'yes', cited: [] } })
  const failed = (id) => ({ id, role: 'assistant', text: '', error: 'boom' })
  expect(lastMiss([])).toBe(0)
  expect(lastMiss([q(1)])).toBe(0)
  expect(lastMiss([q(1), said(2)])).toBe(0)
  expect(lastMiss([q(1), failed(2)])).toBe(0)
  expect(lastMiss([q(1), none(2)])).toBe(2)
  expect(lastMiss([q(1), none(2), q(3), said(4)])).toBe(2)
  expect(lastMiss([q(1), none(2), q(3), said(4), q(5), none(6)])).toBe(6)
  expect(lastMiss(undefined)).toBe(0)
})

// A run started before Docs was left is not the card's own useJob any more: the jobs store still lists it.
test('the jobs store says whether a repo\'s own wiki is running, and which repos\' are', () => {
  const running = [{ id: '1', kind: 'wiki', repo: 'api', status: 'running' }, { id: '2', kind: 'c4', status: 'running' },
    { id: '3', kind: 'wiki', repo: 'web', status: 'done' }, { id: '4', kind: 'cmd', repo: 'ui', status: 'running' }]
  expect(wikiRunning(running, 'api')).toBe(true)
  expect(['web', 'ui', 'db'].map((r) => wikiRunning(running, r))).toEqual([false, false, false])
  expect(wikiRunning(undefined, 'api')).toBe(false)
  expect(wikiRuns(running)).toEqual(['api'])
  expect(wikiRuns(undefined)).toEqual([])
})

// When a run leaves the running list the wikis are read again, so the card and the header catch up.
test('the wiki runs that ended between two reads of the running list', () => {
  expect(wikiRunsEnded(['api'], [])).toEqual(['api'])
  expect(wikiRunsEnded(['api', 'web'], ['web'])).toEqual(['api'])
  expect(wikiRunsEnded([], ['api'])).toEqual([])
  expect(wikiRunsEnded(['api'], ['api'])).toEqual([])
  expect(wikiRunsEnded([], [])).toEqual([])
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

// GET viewers, read on mount and again after the C4 build: the answer goes to `set`, a failed read gives null (the header then
// says nothing of the C4), and nothing is set once the section is gone (`isAlive`).
const viewersAnswer = { c4: { exists: true, stale: false, model: true } }
const fakeSrv = (get) => ({ get: vi.fn(get) })

test('a read of the viewers hands the answer over; a failed one hands over null', async () => {
  const set = vi.fn()
  const srv = fakeSrv(() => Promise.resolve(viewersAnswer))
  await readViewers(srv, () => true, set)
  expect(srv.get).toHaveBeenCalledWith('viewers')
  expect(set.mock.calls).toEqual([[viewersAnswer]])
  const failed = vi.fn()
  await readViewers(fakeSrv(() => Promise.reject(new Error('Failed to fetch'))), () => true, failed)
  expect(failed.mock.calls).toEqual([[null]])
})

test('a read that lands after the section is gone sets nothing, whichever way it ends', async () => {
  const set = vi.fn()
  await readViewers(fakeSrv(() => Promise.resolve(viewersAnswer)), () => false, set)
  await readViewers(fakeSrv(() => Promise.reject(new Error('x'))), () => false, set)
  expect(set).not.toHaveBeenCalled()
  let alive = true
  let land
  const late = readViewers(fakeSrv(() => new Promise((resolve) => { land = resolve })), () => alive, set)   // gone while the read is in flight
  alive = false
  land(viewersAnswer)
  await late
  expect(set).not.toHaveBeenCalled()
})

// The reload after a build keeps what was read until the new answer lands, and a failed reload keeps it too: a chip never
// disappears because the read behind it did. `readViewers` still says null on a failure; this decides what to keep.
test('a failed reload of the viewers keeps the last answer; a new answer replaces it', () => {
  const stale = { c4: { exists: true, stale: true, model: true } }
  expect(viewersRead(null, viewersAnswer)).toBe(viewersAnswer)
  expect(viewersRead(stale, viewersAnswer)).toBe(viewersAnswer)
  expect(viewersRead(stale, null)).toBe(stale)
  expect(viewersRead(null, null)).toBeNull()                                  // a failed first read: still nothing to say
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

test('the C4 chip is current, stale, not built yet, or has no model to build', () => {
  const c4 = (v) => chips(docsHealth({}, null, { c4: v }))
  expect(c4({ exists: true, stale: false, model: true })).toEqual([['c4Fresh', 'ok', null]])
  expect(c4({ exists: true, stale: true, model: true })).toEqual([['c4Stale', 'warn', null]])
  expect(c4({ exists: false, stale: false, model: true })).toEqual([['c4None', 'info', null]])      // there is a model: it can be built
  expect(c4({ exists: false, stale: false, model: false })).toEqual([['c4NoModel', 'info', null]])  // nothing to build yet
  expect(c4({ exists: false, stale: true, model: true })).toEqual([['c4None', 'info', null]])   // nothing built: not stale
  expect(c4({ exists: false })).toEqual([['c4None', 'info', null]])                           // an answer without `model` keeps the old chip
  expect(c4({ exists: true, stale: false, model: false })).toEqual([['c4Fresh', 'ok', null]])   // a built explorer outranks the model flag
})

// The chip-to-card scroll relies on it: a repo counts under the state its card shows (wikiState on the block of the same row).
test('the wiki chips count what the cards show', () => {
  const states = wikiBlocks(index, rows).map((b) => wikiState(b))
  expect(states).toEqual(['fresh', 'stale', 'old', 'none', 'none', 'old'])        // e: no pages + stale = none; f: stale + old = old
  const count = (s) => states.filter((x) => x === s).length
  const chipN = Object.fromEntries(docsHealth({}, rows, null).map((x) => [x.key, x.n]))
  expect(chipN).toEqual({ wikiNone: count('none'), wikiStale: count('stale'), wikiOld: count('old'), wikiFresh: count('fresh') })
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

// The questions the docs could not answer: GET misses ({misses}) on mount, POST kpis/miss to add one to the open questions
// or forget it (the server answers the new {misses}). A rejection is said as the server said it.
const missRows = [{ q: 'how are refunds made', n: 3, last: '2026-11-17' }, { q: 'who owns billing', n: 1, last: '2026-11-16' }]

test('a question is added to the open questions or dismissed with kpis/miss', async () => {
  const srv = { post: vi.fn(() => Promise.resolve({ misses: [] })) }
  expect(await missAction(srv, 'who owns billing', 'question')).toEqual({ misses: [] })
  expect(srv.post).toHaveBeenLastCalledWith('kpis/miss', { q: 'who owns billing', action: 'question' })
  await missAction(srv, 'who owns billing', 'dismiss')
  expect(srv.post).toHaveBeenLastCalledWith('kpis/miss', { q: 'who owns billing', action: 'dismiss' })
})

test('the list is what an answer carries as `misses`; anything else is no list', () => {
  expect(missesOf({ misses: missRows })).toBe(missRows)
  expect(missesOf({ misses: [] })).toEqual([])
  for (const bad of [null, undefined, {}, { misses: null }, { misses: 'x' }, [], 'x']) expect(missesOf(bad)).toBeNull()
})

test('a read of the misses hands over the list; a failed or malformed one hands over null', async () => {
  const set = vi.fn()
  const srv = fakeSrv(() => Promise.resolve({ misses: missRows }))
  await readMisses(srv, () => true, set)
  expect(srv.get).toHaveBeenCalledWith('misses')
  expect(set.mock.calls).toEqual([[missRows]])
  const failed = vi.fn()
  await readMisses(fakeSrv(() => Promise.reject(new Error('Failed to fetch'))), () => true, failed)
  await readMisses(fakeSrv(() => Promise.resolve({ error: 'x' })), () => true, failed)
  expect(failed.mock.calls).toEqual([[null], [null]])
})

test('a read of the misses that lands after the card is gone sets nothing', async () => {
  const set = vi.fn()
  await readMisses(fakeSrv(() => Promise.resolve({ misses: missRows })), () => false, set)
  await readMisses(fakeSrv(() => Promise.reject(new Error('x'))), () => false, set)
  expect(set).not.toHaveBeenCalled()
})

test('an action on a question gives the server\'s new list, or the rejection in the server\'s words, and never rejects', async () => {
  const say = vi.fn((e) => `said: ${e.message}`)
  const ok = { post: vi.fn(() => Promise.resolve({ misses: [missRows[1]] })) }
  expect(await actOnMiss(ok, 'how are refunds made', 'dismiss', say)).toEqual({ misses: [missRows[1]] })
  expect(ok.post).toHaveBeenCalledWith('kpis/miss', { q: 'how are refunds made', action: 'dismiss' })
  const refused = { post: vi.fn(() => Promise.reject(new Error('not in the list: who owns billing'))) }
  expect(await actOnMiss(refused, 'who owns billing', 'question', say)).toEqual({ error: 'said: not in the list: who owns billing' })
  expect(say).toHaveBeenCalledTimes(1)
  expect(await actOnMiss({ post: () => Promise.resolve({}) }, 'x', 'dismiss', say)).toEqual({ misses: null })      // no list: the card keeps its own
})

test('the team strip says where the team repo stands, one state at a time', () => {
  expect(stripState(null)).toEqual({ key: 'strip.reading', tone: 'none' })
  expect(stripState({ error: 'x' })).toEqual({ key: 'strip.failed', tone: 'warn' })
  expect(stripState({ remote: '' })).toEqual({ key: 'strip.never', tone: 'none' })
  expect(stripState({ remote: 'r', behind: 2, ahead: 0, pending: [] })).toEqual({ key: 'strip.behind', vars: { n: 2 }, tone: 'warn' })
  expect(stripState({ remote: 'r', behind: 0, ahead: 1, pending: ['a'] })).toEqual({ key: 'strip.ahead', vars: { n: 2 }, tone: 'warn' })
  expect(stripState({ remote: 'r', behind: 0, ahead: 0, pending: [] })).toEqual({ key: 'strip.upToDate', tone: 'ok' })
})

// GET sync's `changes` leaves out the files the kit rewrites on every read (docs/.status.json): they are never yours to
// upload. An older server sends only `pending`.
test('one change either way is said in the singular', () => {
  expect(stripState({ remote: 'r', behind: 1, ahead: 0, pending: [] })).toEqual({ key: 'strip.behind.one', vars: { n: 1 }, tone: 'warn' })
  expect(stripState({ remote: 'r', behind: 0, ahead: 0, changes: ['docs/a.md'] })).toEqual({ key: 'strip.ahead.one', vars: { n: 1 }, tone: 'warn' })
  expect(t('strip.ahead.one', { n: 1 })).toBe('1 cambio por subir')
})

test('the team strip counts only real changes as yours to upload, never the files the kit rewrites', () => {
  expect(stripState({ remote: 'r', behind: 0, ahead: 0, pending: ['docs/.status.json'], changes: [] })).toEqual({ key: 'strip.upToDate', tone: 'ok' })
  expect(stripState({ remote: 'r', behind: 0, ahead: 1, pending: ['docs/.status.json', 'docs/a.md'], changes: ['docs/a.md'] }))
    .toEqual({ key: 'strip.ahead', vars: { n: 2 }, tone: 'warn' })
  expect(t('strip.ahead', { n: 2 })).toBe('2 cambios por subir')
  setLang('en')
  expect(t('strip.ahead', { n: 2 })).toBe('2 changes to upload')
  setLang('es')
})

// The health header lives on Read and the wiki cards on Wikis: the stale-wikis chip opens the Wikis tab with this address, and only
// that tab's address asking for `show=stale` makes the tab look for its first stale card.
test('the address that asks the Wikis tab for its first stale card', () => {
  expect(STALE_WIKIS).toBe('#/docs/wikis?show=stale')
  expect(seeksStale(STALE_WIKIS)).toBe(true)
  expect(seeksStale('#/docs/wikis?repo=api&show=stale')).toBe(true)
  for (const h of ['#/docs/wikis', '#/docs?show=stale', '#/docs/wikis?show=fresh', '#/docs/wikisx?show=stale', '', undefined, null]) {
    expect(seeksStale(h), String(h)).toBe(false)
  }
})

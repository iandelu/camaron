import { errorLine } from './onboarding.js'

// The portal (the reader) from the app: it is served by the same project server, one folder up from /desktop/, and
// a project window opens it in the system browser. Pure.

// An address of the portal: origin is this window's (location.origin), hash the portal's route ('#/', '#/review'…).
export const portalUrl = (origin, hash = '#/') => `${String(origin).replace(/\/+$/, '')}/${hash || '#/'}`

// The repos that have an OpenWiki, as the portal reads them from the tree (GET tree):
// their pages are in the wiki space, at wikis/<repo>/<page> (docs.iter_docs). Only
// those have a graph to build (app.wiki.wiki_graph needs pages). Once each, in order.
export function wikiRepos(tree) {
  const out = []
  for (const d of tree?.docs || []) {
    if (d.space !== 'wiki') continue
    const repo = String(d.path).split('/')[1]
    if (repo && !out.includes(repo)) out.push(repo)
  }
  return out
}

// The C4 explorer's card: `body` is what POST build takes (app-token-gated; the portal has no app token), `hash` where the
// portal shows the result.
export const c4Card = { id: 'c4', repo: '', body: { what: 'c4' }, hash: '#/c4' }

// One block per repo of the project, from GET wikis (app.wiki.wikis(): every repo, in the project's order, with whether
// it is cloned and chosen, its brief ('ai' | 'starter' | null), its pages and canGenerate = cloned and a wiki engine
// installed). `blocked` says why Generate is closed: 'notCloned', 'noEngine', or 'unread' when wikis could not be read
// (then the tree's `repos` still list every repo, with what the tree knows of their pages).
// `body` is what POST wiki takes (routes/analysis.py wiki(b)): `choose` only for a repo not yet chosen (the server adds
// it to the ones with a wiki), `starter` only when there is no brief and no pages (a starter brief is written without
// AI), as the portal sent them. `graph` is the wiki-graph build, which needs pages (`hasWiki`).
export const wikiBlocks = (tree, wikis) => {
  const block = (repo, hasWiki, blocked, { chosen = false, brief = null, pages = 0, at = 0, stale = false, old = false, graph = false,
    graphStale = false } = {}) => ({ repo, hasWiki, blocked, hash: `#/wiki/${repo}`,
    body: { repo, ...(chosen ? {} : { choose: true }), ...(brief || pages ? {} : { starter: true }) },
    info: { pages, at, stale, old, graph, graphStale, brief },
    graph: { id: `wiki:${repo}`, repo, body: { what: 'wiki-graph', repo }, hash: `#/wiki/${repo}` } })
  if (Array.isArray(wikis)) {
    return wikis.map((w) => block(w.repo, w.pages > 0, w.canGenerate ? null : w.cloned ? 'noEngine' : 'notCloned', w))
  }
  const withWiki = wikiRepos(tree)
  return (tree?.repos || []).map((repo) => block(repo, withWiki.includes(repo), 'unread'))
}

// A wiki card's state, one at a time: a run in progress, a run that failed, no pages yet, written under an older scope
// (`old`), the code moved since (`stale`), or fresh. `hasWiki` (not info.pages) decides "no pages": the tree fallback has no row.
export const wikiState = (block, { running = false, failed = false } = {}) => {
  if (running) return 'generating'
  if (failed) return 'failed'
  if (!block.hasWiki) return 'none'
  if (block.info?.old) return 'old'
  if (block.info?.stale) return 'stale'
  return 'fresh'
}

// The one primary action of each state: what POST wiki takes as `mode` ('' leaves it out) and the i18n key of its label
// (`retry` is the shared one). A run in progress has none.
const WIKI_ACTIONS = {
  none: { kind: 'generate', mode: '', label: 'docs.generate' },
  stale: { kind: 'update', mode: 'update', label: 'docs.update' },
  old: { kind: 'update', mode: 'update', label: 'docs.expand' },
  failed: { kind: 'retry', mode: '', label: 'retry' },
  fresh: { kind: 'view', mode: '', label: 'docs.view' },
}
export const wikiAction = (state) => WIKI_ACTIONS[state] || { kind: null }

// The header's chips from what the section already read: GET index (`summary`, `feedback`), GET wikis rows and GET viewers.
// Counted chips are omitted at 0; an unread source (null) gives none, never a zero. Each wiki falls in the one bucket of its
// card (no pages, old, stale, fresh), so the four add up to the repos. `n` is null for the C4 chips: they are a state; one
// not built says whether there is a model to build (`c4None`) or not yet (`c4NoModel`).
export function docsHealth(index, wikis, viewers) {
  const chip = (key, tone, n = null) => ({ key, tone, n, text: `docs.h.${key}` })
  const out = []
  const counted = (key, tone, n) => { if (n > 0) out.push(chip(key, tone, n)) }
  const sum = index?.summary || {}
  counted('drafts', 'warn', sum.draft || 0)
  counted('reconfirm', 'warn', sum['needs-reconfirm'] || 0)
  counted('orphans', 'warn', sum.orphans || 0)
  counted('untranslated', 'warn', sum.untranslated || 0)
  counted('feedback', 'info', index?.feedback || 0)
  if (Array.isArray(wikis)) {
    const bucket = (w) => (w.pages > 0 ? (w.old ? 'old' : w.stale ? 'stale' : 'fresh') : 'none')
    const n = { none: 0, old: 0, stale: 0, fresh: 0 }
    for (const w of wikis) n[bucket(w)]++
    counted('wikiStale', 'warn', n.stale)
    counted('wikiOld', 'warn', n.old)
    counted('wikiNone', 'info', n.none)
    counted('wikiFresh', 'ok', n.fresh)
  }
  const c4 = viewers?.c4
  if (c4) out.push(c4.exists ? (c4.stale ? chip('c4Stale', 'warn') : chip('c4Fresh', 'ok')) : chip(c4.model === false ? 'c4NoModel' : 'c4None', 'info'))
  return out
}

// GET wikis read again ({rows} or {error}): a failure keeps the last good rows (none after a failed first read) and
// sets `failed`, for which the section offers a Retry.
export const wikisRead = (prev, got) => (got.error
  ? { rows: prev.rows, loading: false, failed: true }
  : { rows: got.rows, loading: false, failed: false })

// A GET the section reads on its own: `pick` is what it keeps of the answer, which goes to `set`; null when the read failed,
// and nothing once the section is gone (`isAlive`). Resolves when it has landed.
const readInto = (name, pick = (got) => got) => (srv, isAlive, set) => srv.get(name).then(
  (got) => { if (isAlive()) set(pick(got)) },
  () => { if (isAlive()) set(null) })

// GET viewers (what the C4 explorer and the graphs are), read on mount and again after the C4 build.
export const readViewers = readInto('viewers')

// What the section keeps of a read: a failed one (null) leaves the last answer, so a chip does not vanish when a reload fails.
export const viewersRead = (prev, got) => got ?? prev

// The questions nobody could answer (lib/usage.py misses(): {q, n, last}, this machine only). GET misses and POST kpis/miss both
// answer {misses}; `missesOf` is the list in an answer, null when it carries none (a card with no list shows nothing).
export const missesOf = (got) => (Array.isArray(got?.misses) ? got.misses : null)
export const readMisses = readInto('misses', missesOf)

// POST kpis/miss: `question` adds the question to the open questions of the next interview, `dismiss` forgets it; either way the
// server answers the new list.
export const missAction = (srv, q, action) => srv.post('kpis/miss', { q, action })

// An action as the card keeps it, never rejecting: the server's new list (null if the answer had none: the card keeps its own),
// or the rejection said by `say` (the server's own words).
export const actOnMiss = (srv, q, action, say) => missAction(srv, q, action).then(
  (got) => ({ misses: missesOf(got) }),
  (e) => ({ error: say(e) }))

// What POST wiki takes for a card's action: the block's body, plus the action's `mode` when it has one (Update).
export const wikiRequest = (block, action = {}) => ({ ...block.body, ...(action.mode ? { mode: action.mode } : {}) })

export const startBuild = (srv, card) => srv.post('build', card.body)
export const startWiki = (srv, block, action) => srv.post('wiki', wikiRequest(block, action))

// One wiki runs at a time (routes/analysis.py wiki(): another repo's start is refused with 409 busy). From the jobs
// store's running list: the repo whose wiki runs, when it is not `repo` ('' otherwise), so Generate closes on the
// others.
export const wikiBusyWith = (running, repo) =>
  (running || []).find((j) => j.kind === 'wiki' && j.status === 'running' && j.repo && j.repo !== repo)?.repo || ''

// The repos whose wiki runs, from the same list: a run started before Docs was left is no card's useJob any more, so its card
// reads it here (`wikiRunning`), and the section reads the wikis again once a run leaves the list (`wikiRunsEnded`: the repos in
// `prev` not in `now`).
export const wikiRuns = (running) => (running || []).filter((j) => j.kind === 'wiki' && j.status === 'running' && j.repo).map((j) => j.repo)
export const wikiRunning = (running, repo) => wikiRuns(running).includes(repo)
export const wikiRunsEnded = (prev, now) => prev.filter((repo) => !now.includes(repo))

// POST wiki refused with busy (another repo's wiki started meanwhile) has its own sentence; anything else as errorLine.
export const wikiError = (e, t) => (String(e?.message ?? e ?? '') === 'busy' ? t('docs.wikiBusyAny') : errorLine(e, t))

// The portal in the system browser (the window never navigates to it); a window without the bridge does nothing.
export const openPortal = (app, origin, hash = '#/') => app.openExternal?.(portalUrl(origin, hash))

// A useJob state that ended badly: the POST was rejected, or the job failed (a stopped one is the person's doing).
export const buildFailed = (b) => !!b.error || (b.job?.status === 'failed' && !b.job.stopped)

// Ask's AI answer (POST ask/answer, lib/answers.py): the question as the server takes it; null for an empty one.
export const askBody = (q) => {
  const text = String(q ?? '').trim()
  return text ? { q: text } : null
}

// A source ("<path>" or "<path>#<section>") as the portal's address of that page: #/docs/<path>, a section after "::"
// (portal core.hrefFor). A wiki page's path is wikis/<repo>/<page>; the portal's router sends #/docs/<a wiki page> on
// to #/wiki/<repo>/<page>, so it is not told apart here.
export function citeHash(cite) {
  const [path, ...rest] = String(cite).split('#')            // only the first # splits: a section may contain one
  const anchor = rest.join('#')
  return `#/docs/${path}${anchor ? `::${anchor}` : ''}`
}

// What the answer card shows: the text with who wrote it and its sources, or "none" when the docs had nothing to
// answer from or the model said nothing (answer is null then).
export function answerView(r) {
  if (!r?.answer) return { kind: 'none' }
  const sources = (Array.isArray(r.cited) ? r.cited : []).map((cite) => ({ cite, hash: citeHash(cite) }))
  return { kind: 'answer', text: r.answer, by: r.runner ? (r.model ? `${r.runner} (${r.model})` : r.runner) : '', sources }
}

// The server refuses in English (lib/answers.py raises RuntimeError): the refusals a person can act on get their own
// sentence (the chat's runner that gave nothing, lib/chat.py turn(), keeps whom it names; a turn sent while another runs,
// routes/chat.py's 409 busy); anything else goes through the wizard's errorLine.
export function askError(e, t) {
  const msg = String(e?.message ?? e ?? '')
  if (/^no AI answer here/.test(msg)) return t('docs.askNoAi')
  if (/^no answer within/.test(msg)) return t('docs.askSlow')
  if (/^busy/.test(msg)) return t('docs.chat.busy')
  const none = /^(\S+) gave no answer:/.exec(msg)
  if (none) return t('docs.chat.gaveNothing', { who: none[1] })
  return errorLine(e, t)
}

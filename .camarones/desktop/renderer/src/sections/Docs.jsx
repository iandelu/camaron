import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Thinking } from '@camaron/ui'
import { buildFailed, c4Card, docsHealth, openPortal, readViewers, startBuild, startWiki, viewersRead, wikiAction,
  wikiBlocks, wikiBusyWith, wikiError, wikiRunning, wikiRuns, wikiRunsEnded, wikiState, wikisRead } from '../docs.js'
import { useJob, useStore } from '../hooks.js'
import { ago } from '../jobs.js'
import { errorLine } from '../onboarding.js'
import { JobOutput, Page } from '../parts.jsx'
import { t } from '../i18n.js'
import { AskEntry, DocsChat } from './DocsChat.jsx'
import { DocsHealth } from './DocsHealth.jsx'
import { DocsIcon } from './DocsIcons.jsx'
import { DocsMisses } from './DocsMisses.jsx'

export { AnswerView } from './DocsChat.jsx'

// Reading is the portal's, on this same server one folder up: these buttons open it in the system browser (never an
// href the window would follow). The portal has no app token (only the board's), so what it shows but cannot run is
// run here: the C4 explorer, each repo's wiki (generate it, build its graph) and the docs chat, on the window's chat
// store, in a panel beside the page. One wiki runs at a time: while one runs (the jobs store), Generate is closed on
// the other repos. The models are read on mount, so the picker is ready when the panel opens; closing it gives the
// focus back to what opened it.
const NONE = { running: [] }
const NO_JOBS = { get: () => NONE, subscribe: () => () => {} }
const QUIET = { messages: [], running: false, runners: null, choice: null, ai: true, loadError: '' }
const NO_CHAT = { ...NO_JOBS, get: () => QUIET, load: () => {}, send: () => {}, pick: () => {}, clear: () => {} }
export default function Docs({ srv, jobs, chat, app, index }) {
  const open = (hash) => openPortal(app, location.origin, hash)
  const wikis = useWikis(srv)
  const { viewers, reload: reloadViewers } = useViewers(srv)
  const { running } = useStore(jobs || NO_JOBS)
  const runs = wikiRuns(running)
  const seenRuns = useRef(runs)
  useEffect(() => {                                 // a run that ended, whoever started it: its card and the header catch up
    if (wikiRunsEnded(seenRuns.current, runs).length) wikis.reload()
    seenRuns.current = runs
  }, [runs.join('\n')])
  const talk = chat || NO_CHAT
  const [chatting, setChatting] = useState(false)
  const opener = useRef(null)
  useEffect(() => { talk.load() }, [])
  const ask = () => { opener.current = document.activeElement; setChatting(true) }
  const close = () => { setChatting(false); opener.current?.focus() }
  const drafts = index?.summary?.draft || 0
  return (
    <div className={chatting ? 'dk-docs with-chat' : 'dk-docs'}>
      <Page title={t('nav.docs')} wide>
        <DocsHealth chips={docsHealth(index, wikis.rows, viewers)} loading={wikis.loading} />
        <div className="row" data-tour="docs-portal">
          <Button variant="primary" onClick={() => open('#/')}><DocsIcon name="read" />{t('docs.read')}</Button>
          <Button onClick={() => open('#/review')}><DocsIcon name="review" />{drafts > 0 ? `${t('docs.review')} · ${drafts}` : t('docs.review')}</Button>
          <Button variant="ghost" onClick={() => open('#/search')}><DocsIcon name="search" />{t('docs.search')}</Button>
        </div>
        <div data-tour="docs-c4"><Build srv={srv} jobs={jobs} card={c4Card} title={t('docs.c4')} hint={t('docs.c4Hint')} onView={() => open(c4Card.hash)}
          onDone={reloadViewers} /></div>
        <WikiGrid srv={srv} jobs={jobs} index={index} wikis={wikis} running={running} open={open} />
        <DocsMisses srv={srv} />
        <AskEntry chat={talk} onAsk={ask} />
      </Page>
      {chatting ? <DocsChat chat={talk} onClose={close} onOpen={open} /> : null}
    </div>
  )
}

// The wiki cards and, once a read failed, the one notice above them (the cards do not repeat it). `wikis` is useWikis' state.
export function WikiGrid({ srv, jobs, index, wikis: { rows, loading, failed, reload }, running, open }) {
  return (
    <>
      {failed ? <WikisUnread kept={!!rows} onRetry={reload} /> : null}
      <div className="dk-wikis" data-tour="docs-wikis">
        {wikiBlocks(index, rows).map((b, i) => (
          <WikiBlock key={b.repo} srv={srv} jobs={jobs} block={b} index={i} loading={loading} failed={failed} busyWith={wikiBusyWith(running, b.repo)}
            runningHere={wikiRunning(running, b.repo)} onView={() => open(b.hash)} onDone={reload} />))}
      </div>
    </>
  )
}

// Each repo's wiki state (GET wikis, read-only: cloned, chosen, brief, pages, whether it can be generated), read once and
// again after a run or a Retry; rows null while loading or when the first read failed (the blocks then keep Generate
// closed). A failed re-read keeps the last good rows (wikisRead); `failed` brings the Retry.
function useWikis(srv) {
  const [state, setState] = useState({ rows: null, loading: true, failed: false })
  const alive = useRef(true)
  const reload = () => srv.get('wikis').then((rows) => { if (alive.current) setState((s) => wikisRead(s, { rows })) },
    () => { if (alive.current) setState((s) => wikisRead(s, { error: true })) })
  useEffect(() => {
    alive.current = true
    reload()
    return () => { alive.current = false }
  }, [])
  return { ...state, reload }
}

// GET viewers, read once and again after the C4 build (`reload`); null until read and when the first read failed, so the header
// says nothing of the C4 rather than a zero. A failed reload keeps the last answer (viewersRead).
function useViewers(srv) {
  const [viewers, setViewers] = useState(null)
  const alive = useRef(true)
  const reload = () => readViewers(srv, () => alive.current, (got) => setViewers((prev) => viewersRead(prev, got)))
  useEffect(() => {
    alive.current = true
    reload()
    return () => { alive.current = false }
  }, [])
  return { viewers, reload }
}

// GET wikis failed: said once, with a Retry. `kept`: the cards still show the last good read.
export function WikisUnread({ kept, onRetry }) {
  return <Aviso tone="warn" title={t(kept ? 'docs.wikiStale' : 'docs.wikiUnread')}
    action={<Button size="sm" onClick={onRetry}>{t('retry')}</Button>} />
}

// A build job of the project server (POST build, token-gated) followed to its end; `onDone` only when it ended `done`, so what
// the section read about the result (the header's C4 chip) is read again.
export function Build({ srv, jobs, card, onDone, ...rest }) {
  const build = useJob(srv, jobs, () => startBuild(srv, card))
  const run = async () => { if ((await build.run())?.status === 'done') onDone?.() }
  return <BuildCard build={build} onBuild={run} {...rest} />
}

// A job's state with a rejection said in the person's language (the POST failed before there was a job).
const shownJob = (build, say = errorLine) => (build.error ? { ...build, error: say({ message: build.error }, t) } : build)

// The card itself: Build runs the job (Retry once it failed, with the reason in the person's language), View opens the
// result in the portal. The buttons repeat on every card, so each says whose it is.
export function BuildCard({ title, hint, build, onBuild, onView }) {
  const go = buildFailed(build) ? t('retry') : t('docs.build')
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{title}</span><span className="dk-grow"></span>
        <Button size="sm" disabled={build.running} aria-label={`${go}: ${title}`} onClick={onBuild}>{go}</Button>
        <Button size="sm" variant="ghost" aria-label={`${t('docs.view')}: ${title}`} onClick={onView}>{t('docs.view')}</Button></div>
      <p className="muted small">{hint}</p>
      <JobOutput c={shownJob(build)} />
    </Card>
  )
}

// One block per repo: its card runs POST wiki (Generate chooses the repo and writes the starter brief, Update asks for mode
// `update`) and the graph build, and opens the wiki in the portal. Wiring only: what the card shows is WikiCard's.
export function WikiBlock({ srv, jobs, block, loading = false, failed = false, busyWith = '', runningHere = false, index = 0, onView, onDone }) {
  const gen = useJob(srv, jobs, async (action) => startWiki(srv, block, action))
  const graph = useJob(srv, jobs, () => startBuild(srv, block.graph))
  const run = async (action) => { if ((await gen.run(action))?.status === 'done') onDone?.() }
  const build = async () => { if ((await graph.run())?.status === 'done') onDone?.() }
  return <WikiCard block={block} gen={gen} graph={graph} loading={loading} failed={failed} busyWith={busyWith} runningHere={runningHere} index={index}
    now={Date.now() / 1000} onGenerate={run} onUpdate={run} onGraph={build} onView={onView} />
}

// Why Generate is closed: a repo that is not cloned or without a wiki engine (the portal's canGenerate), or wikis not read.
const WHY = { notCloned: 'docs.notCloned', noEngine: 'docs.noEngine', unread: 'docs.wikiUnread' }

// The status line's figures, from the row; what the row does not know is left out, never shown as a zero.
const figures = ({ pages, at, brief }, now) => [
  pages > 0 && t(pages === 1 ? 'docs.w.pages.one' : 'docs.w.pages.many', { n: pages }),
  pages > 0 && at > 0 && t('docs.w.written', { when: ago(at, now, t) }),
  brief && t(`docs.w.brief.${brief}`),
].filter(Boolean)

// One repo's wiki as a card: its state (icon and word), one primary action, and View beside it once there are pages. `gen` and
// `graph` are useJob states; `now` is epoch seconds, as the rows' `at`. Before the wikis are read (`loading` the first read, or the
// tree fallback's `blocked: 'unread'`) its row is only defaults, so it says nothing about freshness and closes its action. A
// failed re-read (`failed`) keeps the last good rows, so it does not quiet the card; it only spares the card the unread reason,
// said once above. A reason of its own (not cloned, no engine) or another repo's run (busyWith) closes what writes pages, never View.
// `runningHere`: this repo's run as the jobs store lists it (one started before Docs was left is no longer `gen`'s).
export function WikiCard({ block, gen, graph, loading = false, failed = false, busyWith = '', runningHere = false, index = 0, now, onGenerate, onUpdate,
  onGraph, onView }) {
  const title = t('docs.wikiBlock', { repo: block.repo })
  const graphTitle = t('docs.wiki', { repo: block.repo })
  const pages = block.hasWiki || gen.job?.status === 'done'
  const own = wikiState({ ...block, hasWiki: pages }, { running: gen.running || runningHere, failed: buildFailed(gen) })
  const unread = (loading || block.blocked === 'unread') && own !== 'generating'
  const state = unread ? 'unread' : own === 'none' && block.blocked ? 'blocked' : own
  const action = wikiAction(unread || state === 'blocked' ? 'none' : state)
  const writes = !!action.kind && action.kind !== 'view'
  const why = (block.blocked && writes && !(block.blocked === 'unread' && (loading || failed)) ? t(WHY[block.blocked]) : '')
    || (busyWith && writes ? t('docs.wikiBusy', { repo: busyWith }) : '')
  const label = action.label && t(action.label)
  const line = unread || state === 'generating' ? [] : figures(block.info, now)
  const showGraph = pages && !unread && (!block.info.graph || block.info.graphStale || !!graph.job || !!graph.error)
  const again = buildFailed(graph) ? t('retry') : t(block.info.graph ? 'docs.graphRebuild' : 'docs.graphBuild')
  const go = () => (action.kind === 'view' ? onView() : action.kind === 'update' ? onUpdate(action) : onGenerate(action))
  return (
    <Card className={`dk-run dk-wiki is-${state}${gen.job?.status === 'done' ? ' is-done' : ''}`} data-wiki-state={state}
      style={{ '--i': Math.min(index, 8) }}>
      <div className="row dk-wiki-head"><DocsIcon name={unread ? 'wikis' : state} /><span className="eyebrow dk-wiki-name">{title}</span></div>
      <p className="dk-wiki-status small">
        {unread ? null : <strong className="dk-wiki-word">{t(`docs.w.${state}`)}</strong>}
        {line.length ? <span className="muted">{` · ${line.join(' · ')}`}</span> : null}
      </p>
      {why ? <p className="muted small">{why}</p> : null}
      <div className="row">
        {state === 'generating'
          ? <Button size="sm" variant="primary" disabled aria-busy="true" aria-label={`${t('docs.generating')}: ${title}`}>
            <Thinking timer>{t('docs.generating')}</Thinking></Button>
          : <Button size="sm" variant="primary" disabled={unread || (writes && (!!block.blocked || !!busyWith))}
            aria-label={`${label}: ${title}`} onClick={go}>{label}</Button>}
        {pages && action.kind !== 'view'
          ? <Button size="sm" variant="ghost" aria-label={`${t('docs.view')}: ${title}`} onClick={onView}>{t('docs.view')}</Button> : null}
      </div>
      <JobOutput c={shownJob(gen, wikiError)} />
      {showGraph ? (
        <>
          <div className="row"><span className="muted small">{graphTitle}</span><span className="dk-grow"></span>
            <Button size="sm" disabled={graph.running} aria-label={`${again}: ${graphTitle}`} onClick={onGraph}>{again}</Button></div>
          <p className="muted small">{t('docs.wikiHint')}</p>
          <JobOutput c={shownJob(graph)} />
        </>
      ) : null}
    </Card>
  )
}

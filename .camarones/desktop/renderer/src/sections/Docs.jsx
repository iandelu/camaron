import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Thinking } from '@camaron/ui'
import { answerView, askBody, askError, buildFailed, c4Card, openPortal, startBuild, startWiki, wikiAction, wikiBlocks,
  wikiBusyWith, wikiError, wikiState, wikisRead } from '../docs.js'
import { useJob, useStore } from '../hooks.js'
import { ago } from '../jobs.js'
import { errorLine } from '../onboarding.js'
import { JobOutput, Page } from '../parts.jsx'
import { t } from '../i18n.js'
import { DocsIcon } from './DocsIcons.jsx'

// Reading is the portal's, on this same server one folder up: these buttons open it in the system browser (never an
// href the window would follow). The portal has no app token (only the board's), so what it shows but cannot run is
// run here: the C4 explorer, each repo's wiki (generate it, build its graph) and Ask's AI answer. One wiki runs at a
// time: while one runs (the jobs store), Generate is closed on the other repos.
const NONE = { running: [] }
const NO_JOBS = { get: () => NONE, subscribe: () => () => {} }
export default function Docs({ srv, jobs, app, index }) {
  const open = (hash) => openPortal(app, location.origin, hash)
  const wikis = useWikis(srv)
  const { running } = useStore(jobs || NO_JOBS)
  return (
    <Page title={t('nav.docs')} wide>
      <div className="row" data-tour="docs-portal">
        <Button variant="primary" onClick={() => open('#/')}>{t('docs.read')}</Button>
        <Button onClick={() => open('#/review')}>{t('docs.review')}</Button>
        <Button variant="ghost" onClick={() => open('#/search')}>{t('docs.search')}</Button>
      </div>
      <div data-tour="docs-c4"><Build srv={srv} jobs={jobs} card={c4Card} title={t('docs.c4')} hint={t('docs.c4Hint')} onView={() => open(c4Card.hash)} /></div>
      <WikiGrid srv={srv} jobs={jobs} index={index} wikis={wikis} running={running} open={open} />
      <Ask srv={srv} open={open} />
    </Page>
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
            onView={() => open(b.hash)} onDone={reload} />))}
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

// GET wikis failed: said once, with a Retry. `kept`: the cards still show the last good read.
export function WikisUnread({ kept, onRetry }) {
  return <Aviso tone="warn" title={t(kept ? 'docs.wikiStale' : 'docs.wikiUnread')}
    action={<Button size="sm" onClick={onRetry}>{t('retry')}</Button>} />
}

// A build job of the project server (POST build, token-gated) followed to its end.
function Build({ srv, jobs, card, ...rest }) {
  const build = useJob(srv, jobs, () => startBuild(srv, card))
  return <BuildCard build={build} onBuild={() => build.run()} {...rest} />
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
export function WikiBlock({ srv, jobs, block, loading = false, failed = false, busyWith = '', index = 0, onView, onDone }) {
  const gen = useJob(srv, jobs, async (action) => startWiki(srv, block, action))
  const graph = useJob(srv, jobs, () => startBuild(srv, block.graph))
  const run = async (action) => { if ((await gen.run(action))?.status === 'done') onDone?.() }
  const build = async () => { if ((await graph.run())?.status === 'done') onDone?.() }
  return <WikiCard block={block} gen={gen} graph={graph} loading={loading} failed={failed} busyWith={busyWith} index={index} now={Date.now() / 1000}
    onGenerate={run} onUpdate={run} onGraph={build} onView={onView} />
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
export function WikiCard({ block, gen, graph, loading = false, failed = false, busyWith = '', index = 0, now, onGenerate, onUpdate, onGraph, onView }) {
  const title = t('docs.wikiBlock', { repo: block.repo })
  const graphTitle = t('docs.wiki', { repo: block.repo })
  const pages = block.hasWiki || gen.job?.status === 'done'
  const own = wikiState({ ...block, hasWiki: pages }, { running: gen.running, failed: buildFailed(gen) })
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

// Ask's AI answer: POST ask/answer waits for the model (up to 90 s), so it is a request of its own, not a job. An
// empty question is not sent.
function Ask({ srv, open }) {
  const [q, setQ] = useState('')
  const [state, setState] = useState({ busy: false, view: null, error: '' })
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])
  async function submit(e) {
    e.preventDefault()
    const body = askBody(q)
    if (!body || state.busy) return
    setState({ busy: true, view: null, error: '' })
    try {
      const view = answerView(await srv.post('ask/answer', body))
      if (alive.current) setState({ busy: false, view, error: '' })
    } catch (err) {
      if (alive.current) setState({ busy: false, view: null, error: askError(err, t) })
    }
  }
  return (
    <Card className="dk-run" data-tour="docs-ask">
      <span className="eyebrow">{t('docs.ask')}</span>
      <p className="muted small">{t('docs.askHint')}</p>
      <form className="row" onSubmit={submit}>
        <input className="cu-input dk-grow" value={q} placeholder={t('docs.askPh')} aria-label={t('docs.askLabel')} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="primary" size="sm" disabled={state.busy || !q.trim()}>{t('docs.askGo')}</Button>
      </form>
      {state.busy ? <p className="muted small" role="status">{t('docs.asking')}</p> : null}
      {state.error ? <Aviso tone="error" title={state.error} /> : null}
      {state.view ? <AnswerView view={state.view} onOpen={open} /> : null}
    </Card>
  )
}

// The answer as text, who wrote it, and its sources as buttons that open the page in the portal.
export function AnswerView({ view, onOpen }) {
  if (view.kind === 'none') return <p className="muted">{t('docs.askNone')}</p>
  return (
    <div className="dk-out">
      <p className="dk-answer">{view.text}</p>
      {view.by ? <p className="muted small">{t('docs.by', { who: view.by })}</p> : null}
      {view.sources.length ? (
        <div className="row">
          <span className="muted small">{t('docs.sources')}</span>
          {view.sources.map((s) => (
            <Button key={s.cite} size="sm" variant="ghost" aria-label={`${t('docs.view')}: ${s.cite}`} onClick={() => onOpen(s.hash)}>{s.cite}</Button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

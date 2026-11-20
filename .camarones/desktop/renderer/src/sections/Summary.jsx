import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Skeleton, catchUpSay, reposSay } from '@camaron/ui'
import { action, doctorNote } from '../summary.js'
import { openSession, sessionNote } from '../plan.js'
import { useAgents, useStore } from '../hooks.js'
import { firstRunPending } from '../nav.js'
import { AgentPicker, Failed, Page } from '../parts.jsx'
import { TerminalButton } from './TeamStrip.jsx'
import { useTour } from '../Tour.jsx'
import RepoCards from './RepoCards.jsx'
import { lang, t } from '../i18n.js'

// The project's Summary: one next step (lib/plan.next_step, the wizard's own rule) with the one button that takes
// it, and where the plan, the review and the jobs stand. It looks again when a job ends: the plan may have moved.
// While the first run is unfinished (GET app/onboard/state), a notice leads back to the wizard; a failed read shows none.
export default function Summary({ srv, jobs }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [firstRun, setFirstRun] = useState(false)
  const [catchUp, setCatchUp] = useState(null)
  const [remote, setRemote] = useState('')
  const [launch, setLaunch] = useState({ busy: false, note: '', error: '' })
  const a = useAgents(srv)
  const { running } = useStore(jobs)
  const load = () => {
    srv.get('sync').then((x) => { setCatchUp(x?.catch_up ?? null); setRemote(x?.remote || '') }, () => {})
    return srv.get('app/summary', { lang: lang() }).then((d) => { setData(d); setError('') }, (e) => setError(e.message))
  }
  useEffect(() => {
    load()
    srv.get('app/onboard/state').then((s) => setFirstRun(firstRunPending(s)), () => setFirstRun(false))
  }, [])
  const was = useRef(running.length)
  useEffect(() => {
    if (running.length < was.current) load()
    was.current = running.length
  }, [running.length])

  const title = t('nav.summary')
  if (error) return <Page title={title}><Failed title={t('summary.failed')} detail={error} onRetry={() => { setError(''); load() }} /></Page>
  if (!data) return <Page title={title}><Skeleton lines={5} /></Page>
  const { step, plan, review } = data
  const next = action(step, data)
  const doc = doctorNote(data.doctor)
  const start = async () => {
    setLaunch({ busy: true, note: '', error: '' })
    try {
      const n = sessionNote(await openSession(srv, { unit: next.unit, agent: a.agent, lang: lang(), mode: next.mode }), a.label(a.agent))
      setLaunch({ busy: false, note: t(n.key, n.vars), error: '' })
      load()
    } catch (e) {
      setLaunch({ busy: false, note: '', error: e.message })
    }
  }
  const heading = step.unit ? step.unit.title : step.kind === 'review'
    ? (step.count === 1 ? t('next.reviewTitle1') : t('next.reviewTitle', { n: step.count })) : t('next.doneTitle')
  return (
    <Page title={title}>
      {firstRun ? <FirstRunNotice /> : <TourOffer srv={srv} />}
      <CatchUpNote srv={srv} catchUp={catchUp} remote={remote} />
      <Card className="dk-next" data-tour="summary-next">
        <span className="eyebrow">{t(step.kind === 'resume' ? 'next.eyebrowResume' : 'next.eyebrow')}</span>
        <h2 className="dk-next-title">{heading}</h2>
        {step.unit && <code className="muted small">{step.unit.id}</code>}
        {next.kind === 'agent' && a.agents && !a.agents.length
          ? <Aviso tone="warn" title={t('next.noAgent')}><Button href="#/settings">{t('next.machine')}</Button></Aviso>
          : (
            <div className="row">
              {next.kind === 'agent' && <AgentPicker a={a} />}
              {next.kind === 'agent'
                ? <Button variant="primary" disabled={!a.agent || launch.busy} onClick={start}>{t(next.label, { agent: a.label(a.agent) })}</Button>
                : <Button variant="primary" href={next.href}>{t(next.label)}</Button>}
              {next.href !== '#/flow/plan' && <Button variant="ghost" href="#/flow/plan">{t('next.plan')}</Button>}
            </div>
          )}
        {launch.note && <p className="muted small" role="status">{launch.note}</p>}
        {launch.error && <Aviso tone="error" title={t('next.failed')} detail={launch.error} />}
      </Card>
      {doc ? (<div data-tour="summary-doctor">
        <Aviso tone="warn" title={t('sum.doctor')}>
          <span className="row"><span className="small">{[doc.names.join(', '), doc.drift ? t('sum.drift', { n: doc.drift }) : ''].filter(Boolean).join(' · ')}</span>
            <Button size="sm" href="#/quality">{t('sum.doctorGo')}</Button></span>
        </Aviso></div>
      ) : null}
      <div className="dk-stats" data-tour="summary-stats">
        <Card className="dk-stat">
          <span className="eyebrow">{t('stat.plan')}</span>
          <b className="t-impact dk-stat-n">{plan.done}/{plan.total}</b>
          <progress className="dk-progress" value={plan.done} max={plan.total || 1} aria-label={t('stat.plan')} />
        </Card>
        <Card className="dk-stat">
          <span className="eyebrow">{t('stat.review')}</span>
          {review ? <a className="t-impact dk-stat-n" href="../#/review">{review}</a> : <b className="t-impact dk-stat-n">0</b>}
        </Card>
        <Card className="dk-stat">
          <span className="eyebrow">{t('stat.jobs')}</span>
          <b className="t-impact dk-stat-n">{running.length}</b>
        </Card>
      </div>
      <div data-tour="summary-repos"><RepoCards srv={srv} jobs={jobs} /></div>
    </Page>
  )
}

// What the window's catch-up with the team left: a clash or no route to the repo warns (the files, a terminal to
// resolve it, the team strip in Docs), a pull that brought changes is a quiet line, up to date says nothing. Then the
// team's repos: a folder in the way warns, a repo not on this machine yet points at preparing it.
export function CatchUpNote({ srv, catchUp, remote = '' }) {
  const said = catchUpSay(catchUp, remote)
  const repos = reposSay(catchUp)
  if (!said && !repos.length) return null
  return (
    <>
      {said ? pullNote(srv, said) : null}
      {repos.map((r) => (
        <Aviso key={r.key} tone={r.tone} title={t(r.key, r.vars)}
          action={r.setup ? <Button size="sm" href="#/settings">{t('next.machine')}</Button> : undefined} />
      ))}
    </>
  )
}

function pullNote(srv, said) {
  const title = t(said.key, said.vars)
  if (said.tone !== 'warn') return <p className="muted small" role="status">{title}</p>
  return (
    <Aviso tone="warn" title={title} detail={said.detail} action={<span className="row">
      {said.terminal ? <TerminalButton srv={srv} /> : null}
      {said.token ? <Button size="sm" variant="ghost" href={`#/settings/tokens?host=${encodeURIComponent(said.token)}`}>{t('sy.token', { host: said.token })}</Button> : null}
      <Button size="sm" href="#/docs">{t('strip.repo')}</Button></span>} />
  )
}

// The way back to the first-run wizard, for whoever left it for another section before finishing.
export function FirstRunNotice() {
  return <Aviso tone="info" title={t('sum.firstRun')} action={<Button size="sm" href="#/start">{t('sum.firstRunGo')}</Button>} />
}

// Once per machine, after the first run: the tour of the app, or not now. Either button keeps it away. The machine keeps
// the flag (app/info tour_offered): the window's origin, and so its storage, changes with every launch.
export function TourOffer({ srv, offered: known }) {
  const tour = useTour()
  const [offered, setOffered] = useState(known ?? null)
  useEffect(() => { if (known === undefined) srv.get('app/info').then((i) => setOffered(!!i.tour_offered), () => setOffered(true)) }, [])
  if (offered !== false) return null
  const done = () => { setOffered(true); srv.post('app/tour-offered', {}).catch(() => {}) }
  return (
    <Aviso tone="info" title={t('tour.offer')} action={<span className="row">
      <Button size="sm" variant="primary" onClick={() => { done(); tour.start('app') }}>{t('tour.take')}</Button>
      <Button size="sm" variant="ghost" onClick={done}>{t('tour.notNow')}</Button></span>} />
  )
}

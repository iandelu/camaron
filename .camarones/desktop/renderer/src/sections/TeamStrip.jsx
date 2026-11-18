import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Skeleton, fetchSay, shareOk, shareSay } from '@camaron/ui'
import { useCmd } from '../hooks.js'
import { Failed, JobOutput } from '../parts.jsx'
import { stripState } from '../docs.js'
import { ago } from '../jobs.js'
import { seconds } from '../quality.js'
import { t } from '../i18n.js'

// The team's repo (remote) and sharing (app.share.sync_status / app.share.share): sharing is the team action —
// checkpoint, bring in the team's work, push; a clash is undone and reported, never forced.
export function Repo({ srv, jobs, onChanged }) {
  const [s, setS] = useState(null)
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const c = useCmd(srv, jobs)
  const load = (fetch) => srv.get(`sync${fetch ? '?fetch=1' : ''}`)
    .then((x) => { setS(x); setUrl(x.remote || ''); setError('') }, (e) => setError(e.message))
  useEffect(() => { load(false) }, [])
  const cmd = async (name, args) => { await c.run(name, args); await load(false); onChanged?.() }
  async function share() {
    setBusy('share')
    setResult(null)
    try { const r = await srv.post('sync/share', {}); setResult(r.result); setS(r.sync); onChanged?.() } catch (e) { setResult({ status: 'error', detail: e.message }) } finally { setBusy('') }
  }
  async function check() { setBusy('check'); try { await load(true); onChanged?.() } finally { setBusy('') } }
  const clean = url.trim()
  return (
    <Card className="dk-run" data-tour="team-repo">
      <span className="eyebrow">{t('tm.repo')}</span>
      <div className="row">
        <input className="cu-input dk-grow" value={url} placeholder="git@github.com:equipo/cam-docs.git" aria-label={t('tm.repo')}
               onChange={(e) => setUrl(e.target.value)} />
        <Button size="sm" disabled={c.running || !clean || clean === s?.remote || clean.startsWith('-')}
                onClick={() => cmd('remote', { url: clean })}>{t('tm.save')}</Button>
      </div>
      {error ? <Failed title={t('tm.failed')} detail={error} onRetry={() => { setError(''); load(false) }} />
        : !s ? <Skeleton lines={2} /> : !s.remote ? <p className="muted small">{t('tm.noRemote')}</p> : (<>
        <div className="dk-stats dk-stats-sm">
          <div><span className="eyebrow">{t('tm.ahead')}</span><b className="dk-stat-sm">{s.ahead ?? '—'}</b></div>
          <div><span className="eyebrow">{t('tm.behind')}</span><b className="dk-stat-sm">{s.behind ?? '—'}</b></div>
          <div><span className="eyebrow">{t('tm.pending')}</span><b className="dk-stat-sm">{s.pending.length}</b></div>
        </div>
        <div className="row">
          <Button size="sm" variant="primary" disabled={!!busy} onClick={share}>{t('tm.share')}</Button>
          <Button size="sm" variant="ghost" disabled={!!busy} onClick={check}>{t('tm.check')}</Button>
          <label className="dk-check"><input type="checkbox" checked={!!s.auto} disabled={c.running}
            onChange={() => cmd('share', { auto: s.auto ? 'off' : 'on' })} />{t('tm.auto')}</label>
        </div>
      </>)}
      <FetchNote fetched={s?.fetched} remote={s?.remote} />
      <ShareResult result={result} remote={s?.remote} />
      <JobOutput c={c} />
    </Card>
  )
}

// A share's outcome. A failure git explained (no route to the host, no token…) says so in words, git's line beneath,
// and a refused token links to the Tokens card for that host.
export function ShareResult({ result, remote }) {
  if (!result) return null
  const said = shareSay(result, remote)
  const m = t(said.key, said.vars)
  const title = m === said.key ? result.status : m
  if (shareOk(result)) return <p className="small" role="status">{title}</p>
  const token = said.token
    ? <Button size="sm" variant="ghost" href={`#/settings/tokens?host=${encodeURIComponent(said.token)}`}>{t('sy.token', { host: said.token })}</Button>
    : null
  return <Aviso tone="error" title={title} detail={said.detail} action={token} />
}

export function FetchNote({ fetched, remote }) {
  const said = fetchSay(fetched, remote)
  if (!said) return null
  return <Aviso tone="warn" title={t('tm.fetchFailed')} detail={said.detail}>{said.key ? t(said.key, said.vars) : null}</Aviso>
}

// Docs' head: where the team repo stands in one sentence (GET sync, read once), when it was last shared, Share now, and
// the repo card folded below. The strip reads; the repo card, as before, saves the remote and switches auto-share.
export function TeamStripView({ sync, result, busy, onShare, onRetry, srv, jobs, onChanged, repoKey = 0, now = Date.now() }) {
  const st = stripState(sync)
  const last = sync?.remote ? seconds(sync.last_share) : null
  return (
    <div className="dk-run" data-tour="docs-team">
      {sync?.error ? <Aviso tone="warn" title={t(st.key)} action={<Button size="sm" onClick={onRetry}>{t('retry')}</Button>} /> : (
        <div className="row">
          <span className={'cu-chip' + (st.tone === 'none' ? '' : ` cu-chip--${st.tone}`)} role="status">{t(st.key, st.vars)}</span>
          {last ? <span className="muted small">{t('strip.last', { when: ago(last, now / 1000, t) })}</span> : null}
          <span className="dk-grow"></span>
          {sync?.remote ? <Button size="sm" variant="primary" disabled={!!busy} onClick={onShare}>{t('ts.share')}</Button> : null}
        </div>)}
      <ShareResult result={result} remote={sync?.remote} />
      <details className="dk-fold">
        <summary>{t('ts.repo')}</summary>
        <div className="dk-fold-body"><Repo key={repoKey} srv={srv} jobs={jobs} onChanged={onChanged} /></div>
      </details>
    </div>
  )
}

export default function TeamStrip({ srv, jobs }) {
  const [sync, setSync] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const [repoKey, setRepoKey] = useState(0)          // remounts the repo card so it re-reads after the strip's own share or retry
  const alive = useRef(true)
  const load = () => srv.get('sync').then((x) => { if (alive.current) setSync(x) }, (e) => { if (alive.current) setSync({ error: e.message }) })
  useEffect(() => {
    alive.current = true
    load()
    return () => { alive.current = false }
  }, [])
  async function share() {
    setBusy('share')
    setResult(null)
    try {
      const r = await srv.post('sync/share', {})
      if (!alive.current) return
      setResult(r.result)
      setSync(r.sync)
      setRepoKey((n) => n + 1)
    } catch (e) { if (alive.current) setResult({ status: 'error', detail: e.message }) } finally { if (alive.current) setBusy('') }
  }
  const retry = () => { setSync(null); setRepoKey((n) => n + 1); load() }
  return <TeamStripView sync={sync} result={result} busy={busy} onShare={share} onRetry={retry} srv={srv} jobs={jobs} onChanged={load} repoKey={repoKey} />
}

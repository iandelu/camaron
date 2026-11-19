import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Skeleton, fetchSay, lastSync, pullOk, pullSay, pushOk, pushSay, shareOk, shareSay, syncPrimary } from '@camaron/ui'
import { useCmd } from '../hooks.js'
import { Failed, JobOutput } from '../parts.jsx'
import { stripState } from '../docs.js'
import { ago } from '../jobs.js'
import { t } from '../i18n.js'

// The team's repo (remote): bring in, upload, or both in one go (sync/pull, sync/push, sync/share); the one that fits
// where it stands is the primary. A clash is undone and reported, never forced.
const SAY = { pull: pullSay, push: pushSay, share: shareSay }
const OK = { pull: pullOk, push: pushOk, share: shareOk }
const BUSY = { pull: 'tm.pulling', push: 'tm.pushing', share: 'tm.working' }
const tokenHref = (host) => `#/settings/tokens?host=${encodeURIComponent(host)}`

export async function runSync(srv, kind) {
  const r = await srv.post(`sync/${kind}`, {})
  return { result: r.result, sync: r.sync }
}

const when = (iso, now) => {
  const at = Date.parse(iso || '')
  return Number.isNaN(at) ? t('tm.never') : ago(at / 1000, now / 1000, t)
}

// "n to bring in · m to upload · last time …", and the unsaved work only when there is some (`changes` leaves out the
// files the kit rewrites); the last time is the newer of an upload and a bring-in that left this machine in step.
export function syncLine(s, now = Date.now()) {
  const line = t('tm.line', { behind: s.behind ?? '—', ahead: s.ahead ?? '—', when: when(lastSync(s), now) })
  return s.changes?.length ? `${line} · ${t('tm.unsaved', { n: s.changes.length })}` : line
}

// Check (a look at the remote) only where it is offered: the repo card.
export function SyncActions({ s, busy, onRun, onCheck }) {
  const primary = syncPrimary(s)
  const btn = (kind, label) => (
    <Button size="sm" variant={primary === kind ? 'primary' : undefined} disabled={!!busy} onClick={() => onRun(kind)}>
      {busy === kind ? t(BUSY[kind]) : t(label)}</Button>)
  return (<>
    {btn('pull', 'tm.pull')}
    {btn('push', 'tm.push')}
    {btn('share', 'tm.sync')}
    {onCheck ? <Button size="sm" variant="ghost" disabled={!!busy} onClick={onCheck}>{t('tm.check')}</Button> : null}
  </>)
}

export function TerminalButton({ srv }) {
  return <Button size="sm" variant="ghost" onClick={() => srv.post('app/terminal', {}).catch(() => {})}>{t('tm.terminal')}</Button>
}

// What a step left: done is a quiet line; work in git for a terminal (a clash, changes kept in git's stash, a rebase left
// half way) warns with Open a terminal here; a refused token links to Settings › Tokens; an autopilot run only waits.
export function SyncResult({ kind, result, remote, srv }) {
  if (kind === 'share') return <ShareResult result={result} remote={remote} srv={srv} />
  if (!result) return null
  const step = kind === 'pull' ? result.pull ?? (result.status === 'busy' ? null : result) : result
  if (!step) return <p className="small" role="status">{t('sy.pull.busy')}</p>
  const said = SAY[kind](step, remote)
  const m = t(said.key, said.vars)
  const title = m === said.key ? step.status : m
  if (OK[kind](step) || said.tone === 'info') return <p className="small" role="status">{title}</p>
  const action = said.token
    ? <Button size="sm" variant="ghost" href={tokenHref(said.token)}>{t('sy.token', { host: said.token })}</Button>
    : said.terminal ? <TerminalButton srv={srv} /> : null
  return <Aviso tone={said.terminal ? 'warn' : 'error'} title={title} detail={said.detail} action={action} />
}

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
  async function sync(kind) {
    setBusy(kind)
    setResult(null)
    try { const r = await runSync(srv, kind); setResult({ kind, result: r.result }); setS(r.sync); onChanged?.() } catch (e) { setResult({ kind, result: { status: 'error', detail: e.message } }) } finally { setBusy('') }
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
        <p className="small">{syncLine(s)}</p>
        <div className="row">
          <SyncActions s={s} busy={busy} onRun={sync} onCheck={check} />
          <label className="dk-check"><input type="checkbox" checked={!!s.auto} disabled={c.running}
            onChange={() => cmd('share', { auto: s.auto ? 'off' : 'on' })} />{t('tm.auto')}</label>
        </div>
      </>)}
      <FetchNote fetched={s?.fetched} remote={s?.remote} />
      {result ? <SyncResult kind={result.kind} result={result.result} remote={s?.remote} srv={srv} /> : null}
      <JobOutput c={c} />
    </Card>
  )
}

// A share's outcome. A failure git explained (no route to the host, no token…) says so in words, git's line beneath,
// and a refused token links to the Tokens card for that host; a clash offers a terminal to resolve it.
export function ShareResult({ result, remote, srv }) {
  if (!result) return null
  const said = shareSay(result, remote)
  const m = t(said.key, said.vars)
  const title = m === said.key ? result.status : m
  if (shareOk(result)) return <p className="small" role="status">{title}</p>
  const token = said.token
    ? <Button size="sm" variant="ghost" href={tokenHref(said.token)}>{t('sy.token', { host: said.token })}</Button>
    : result.status === 'conflict' && srv ? <TerminalButton srv={srv} /> : null
  return <Aviso tone="error" title={title} detail={said.detail} action={token} />
}

export function FetchNote({ fetched, remote }) {
  const said = fetchSay(fetched, remote)
  if (!said) return null
  return <Aviso tone="warn" title={t('tm.fetchFailed')} detail={said.detail}>{said.key ? t(said.key, said.vars) : null}</Aviso>
}

// Docs' head: where the team repo stands in one sentence (GET sync, read once), how far apart you are and when this
// machine was last in step, Bring in · Upload · Sync with the team, and the repo card folded below. The repo card, as
// before, saves the remote, checks the remote and switches upload on save.
export function TeamStripView({ sync, result, busy, onRun, onRetry, srv, jobs, onChanged, repoKey = 0, now = Date.now() }) {
  const st = stripState(sync)
  return (
    <div className="dk-run" data-tour="docs-team">
      {sync?.error ? <Aviso tone="warn" title={t(st.key)} action={<Button size="sm" onClick={onRetry}>{t('retry')}</Button>} /> : (
        <div className="row">
          <span className={'cu-chip' + (st.tone === 'none' ? '' : ` cu-chip--${st.tone}`)} role="status">{t(st.key, st.vars)}</span>
          {sync?.remote ? <span className="muted small">{syncLine(sync, now)}</span> : null}
          <span className="dk-grow"></span>
          {sync?.remote ? <SyncActions s={sync} busy={busy} onRun={onRun} /> : null}
        </div>)}
      {result ? <SyncResult kind={result.kind} result={result.result} remote={sync?.remote} srv={srv} /> : null}
      <details className="dk-fold">
        <summary>{t('strip.repo')}</summary>
        <div className="dk-fold-body"><Repo key={repoKey} srv={srv} jobs={jobs} onChanged={onChanged} /></div>
      </details>
    </div>
  )
}

export default function TeamStrip({ srv, jobs }) {
  const [sync, setSync] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const [repoKey, setRepoKey] = useState(0)          // remounts the repo card so it re-reads after the strip's own step or retry
  const alive = useRef(true)
  const load = () => srv.get('sync').then((x) => { if (alive.current) setSync(x) }, (e) => { if (alive.current) setSync({ error: e.message }) })
  useEffect(() => {
    alive.current = true
    load()
    return () => { alive.current = false }
  }, [])
  async function run(kind) {
    setBusy(kind)
    setResult(null)
    try {
      const r = await runSync(srv, kind)
      if (!alive.current) return
      setResult({ kind, result: r.result })
      setSync(r.sync)
      setRepoKey((n) => n + 1)
    } catch (e) { if (alive.current) setResult({ kind, result: { status: 'error', detail: e.message } }) } finally { if (alive.current) setBusy('') }
  }
  const retry = () => { setSync(null); setRepoKey((n) => n + 1); load() }
  return <TeamStripView sync={sync} result={result} busy={busy} onRun={run} onRetry={retry} srv={srv} jobs={jobs} onChanged={load} repoKey={repoKey} />
}

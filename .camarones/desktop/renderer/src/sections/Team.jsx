import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Skeleton, fetchSay, pullOk, pullSay, pushOk, pushSay, shareOk, shareSay, syncPrimary } from '@camaron/ui'
import { useCmd } from '../hooks.js'
import { Failed, JobOutput, Page } from '../parts.jsx'
import Commands from './Commands.jsx'
import { ago } from '../jobs.js'
import { lang, t } from '../i18n.js'
import { skillsView, switchArgs } from '../skills.js'

// The team by task: the team's cam-docs repo and syncing with it (where it stands, bring in, upload), the agent config and
// hooks that came with it and this machine has not approved, the agents' skills and the plugins. The board and CI are
// the portal's.
// A kind or a state the CLI names in English (trust, plugins), in the user's words; an unknown one as it comes.
const word = (family, v) => { const k = `${family}.${v}`; const w = t(k); return w === k ? v : w }

export default function Team({ srv, jobs }) {
  const [tick, setTick] = useState(0)          // a pack added below arrives in the Trust card to approve
  return (
    <Page title={t('nav.team')}>
      <Repo srv={srv} jobs={jobs} />
      <Trust srv={srv} jobs={jobs} tick={tick} />
      <Skills srv={srv} jobs={jobs} onChange={() => setTick((n) => n + 1)} />
      <Plugins srv={srv} jobs={jobs} />
      <div className="row">
        <Button size="sm" variant="ghost" href="../#/kanban">{t('tm.board')}</Button>
        <Button size="sm" variant="ghost" href="../#/ci">{t('tm.ci')}</Button>
      </div>
      <Commands srv={srv} jobs={jobs} section="team" />
    </Page>
  )
}

// The team's repo (remote): bring in, upload, or both in one go (sync/pull, sync/push, sync/share); the one that fits
// where it stands is the primary. A clash is undone and reported, never forced.
const SAY = { pull: pullSay, push: pushSay, share: shareSay }
const OK = { pull: pullOk, push: pushOk, share: shareOk }
const BUSY = { pull: 'tm.pulling', push: 'tm.pushing', share: 'tm.working' }

export async function runSync(srv, kind) {
  const r = await srv.post(`sync/${kind}`, {})
  return { result: r.result, sync: r.sync }
}

const when = (iso) => {
  const at = Date.parse(iso || '')
  return Number.isNaN(at) ? t('tm.never') : ago(at / 1000, Date.now() / 1000, t)
}

export function SyncActions({ s, busy, onRun, onCheck }) {
  const primary = syncPrimary(s)
  const btn = (kind, label) => (
    <Button size="sm" variant={primary === kind ? 'primary' : undefined} disabled={!!busy} onClick={() => onRun(kind)}>
      {busy === kind ? t(BUSY[kind]) : t(label)}</Button>)
  return (<>
    {btn('pull', 'tm.pull')}
    {btn('push', 'tm.push')}
    {btn('share', 'tm.sync')}
    <Button size="sm" variant="ghost" disabled={!!busy} onClick={onCheck}>{t('tm.check')}</Button>
  </>)
}

export function TerminalButton({ srv }) {
  return <Button size="sm" variant="ghost" onClick={() => srv.post('app/terminal', {}).catch(() => {})}>{t('tm.terminal')}</Button>
}

export function SyncResult({ kind, result, remote, srv }) {
  if (kind === 'share') return <ShareResult result={result} remote={remote} srv={srv} />
  if (!result) return null
  const step = kind === 'pull' ? result.pull : result
  if (kind === 'pull' && !step) return <p className="small" role="status">{t('sy.pull.busy')}</p>
  const said = SAY[kind](step, remote)
  const m = t(said.key, said.vars)
  const title = m === said.key ? step.status : m
  if (OK[kind](step)) return <p className="small" role="status">{title}</p>
  const action = said.token
    ? <Button size="sm" variant="ghost" href={`#/machine?host=${encodeURIComponent(said.token)}`}>{t('sy.token', { host: said.token })}</Button>
    : step.status === 'conflict' ? <TerminalButton srv={srv} /> : null
  return <Aviso tone={step.status === 'conflict' ? 'warn' : 'error'} title={title} detail={said.detail} action={action} />
}
function Repo({ srv, jobs }) {
  const [s, setS] = useState(null)
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const c = useCmd(srv, jobs)
  const load = (fetch) => srv.get(`sync${fetch ? '?fetch=1' : ''}`)
    .then((x) => { setS(x); setUrl(x.remote || ''); setError('') }, (e) => setError(e.message))
  useEffect(() => { load(false) }, [])
  const cmd = async (name, args) => { await c.run(name, args); load(false) }
  async function sync(kind) {
    setBusy(kind)
    setResult(null)
    try { const r = await runSync(srv, kind); setResult({ kind, result: r.result }); setS(r.sync) } catch (e) { setResult({ kind, result: { status: 'error', detail: e.message } }) } finally { setBusy('') }
  }
  async function check() { setBusy('check'); try { await load(true) } finally { setBusy('') } }
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
        <p className="small">{t('tm.line', { behind: s.behind ?? '—', ahead: s.ahead ?? '—', when: when(s.last_share) })}</p>
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
// and a refused token links to the Tokens card for that host.
export function ShareResult({ result, remote, srv }) {
  if (!result) return null
  const said = shareSay(result, remote)
  const m = t(said.key, said.vars)
  const title = m === said.key ? result.status : m
  if (shareOk(result)) return <p className="small" role="status">{title}</p>
  const token = said.token
    ? <Button size="sm" variant="ghost" href={`#/machine?host=${encodeURIComponent(said.token)}`}>{t('sy.token', { host: said.token })}</Button>
    : result.status === 'conflict' && srv ? <TerminalButton srv={srv} /> : null
  return <Aviso tone="error" title={title} detail={said.detail} action={token} />
}

export function FetchNote({ fetched, remote }) {
  const said = fetchSay(fetched, remote)
  if (!said) return null
  return <Aviso tone="warn" title={t('tm.fetchFailed')} detail={said.detail}>{said.key ? t(said.key, said.vars) : null}</Aviso>
}

// What came with the team's repo (agent config, plugins) and this machine has not approved: nothing of it loads
// until it is. Approving runs `trust --yes` after a dialog that lists it. (The method hooks' switch is Quality's.)
function Trust({ srv, jobs, tick = 0 }) {
  const list = useCmd(srv, jobs, { quiet: true })
  const act = useCmd(srv, jobs)
  const dialog = useRef(null)
  const load = () => { list.run('trust', { json: true }) }
  useEffect(() => { load() }, [tick])
  const rows = list.job?.result?.pending
  const then = async (p) => { await p; load() }
  return (
    <Card className="dk-run" data-tour="team-trust">
      <span className="eyebrow">{t('tm.trust')}</span>
      {rows ? (rows.length ? (<>
        <ul className="dk-units">{rows.map((r) => (
          <li key={r.kind + r.label} className="dk-unit"><div className="dk-unit-main"><b>{r.label}</b>
            <span className="muted small">{word('tk', r.kind)}{r.detail ? ` · ${r.detail}` : ''}</span></div>
            <span className="cu-chip cu-chip--warn">{word('ts', r.status)}</span></li>))}</ul>
        <div className="row"><Button size="sm" variant="primary" disabled={act.running} onClick={() => dialog.current.showModal()}>
          {t('tm.approve', { n: rows.length })}</Button></div>
        <dialog ref={dialog} className="dk-dialog">
          <h2>{t('tm.approveTitle')}</h2>
          <p>{t('tm.approveText')}</p>
          <ul>{rows.map((r) => <li key={r.kind + r.label}><code>{r.label}</code></li>)}</ul>
          <div className="row">
            <Button variant="ghost" onClick={() => dialog.current.close()}>{t('cancel')}</Button>
            <Button variant="primary" onClick={() => { dialog.current.close(); then(act.run('trust', {}, true)) }}>{t('tm.approveGo')}</Button>
          </div>
        </dialog>
      </>) : <p className="small">{t('tm.trusted')}</p>) : <JobOutput c={list} />}
      <JobOutput c={act} />
    </Card>
  )
}

// The agents' skills (`skills list --json`): each with its icon and two switches — the project's, for the whole team
// (workspace.yaml), and this machine's, for you only (a Claude Code deny rule in the git-ignored settings.local.json).
// Below, the kit's optional packs: adding one copies it into the team's skills, so the Trust card asks to approve it.
function Skills({ srv, jobs, onChange }) {
  const list = useCmd(srv, jobs, { quiet: true })
  const act = useCmd(srv, jobs)
  const load = () => list.run('skills', { action: 'list', json: true })
  useEffect(() => { load() }, [])
  const then = async (p) => { await p; load(); onChange?.() }
  const data = list.job?.result
  return (
    <Card className="dk-run" data-tour="team-skills">
      <span className="eyebrow">{t('tm.skills')}</span>
      <p className="muted small">{t('tm.skillsLead')}</p>
      {data?.skills ? <SkillsList data={data} busy={act.running}
        onSwitch={(row, scope) => then(act.run('skills', switchArgs(row, scope)))}
        onAdd={(pack) => then(act.run('skills', { action: 'add', args: [pack.name] }))} /> : <JobOutput c={list} />}
      <JobOutput c={act} />
    </Card>
  )
}

export function SkillsList({ data, busy = false, onSwitch = () => {}, onAdd = () => {} }) {
  const { rows, packs } = skillsView(data, lang())
  return (<>
    <ul className="dk-units">{rows.map((r) => (
      <li key={r.name} className="dk-unit">
        <span className="dk-skill-icon" aria-hidden="true">{r.icon}</span>
        <div className="dk-unit-main"><b>{r.name}</b>
          <span className="muted small">{t(r.origin, { pack: r.pack })}{r.description ? ` · ${r.description}` : ''}</span></div>
        <div className="row dk-unit-acts">
          {r.waiting ? <span className="cu-chip cu-chip--warn">{t('tm.skWaiting')}</span> : null}
          <label className="dk-check"><input type="checkbox" checked={r.project} disabled={busy}
            onChange={() => onSwitch(r, 'project')} />{t('tm.skProject')}</label>
          <label className="dk-check" title={t('tm.skMachineHint')}><input type="checkbox" checked={r.machine} disabled={busy}
            onChange={() => onSwitch(r, 'machine')} />{t('tm.skMachine')}</label>
        </div>
      </li>))}</ul>
    {packs.length ? (<>
      <span className="eyebrow">{t('tm.skAvailable')}</span>
      <ul className="dk-units">{packs.map((p) => (
        <li key={p.name} className="dk-unit">
          <span className="dk-skill-icon" aria-hidden="true">{p.icon}</span>
          <div className="dk-unit-main"><b>{p.title}</b>
            <span className="muted small">{p.summary} · {p.license} · {p.skills.join(', ')}</span></div>
          <div className="row dk-unit-acts">
            {p.runsCode ? <span className="cu-chip cu-chip--warn">{t('tm.runsCode')}</span> : null}
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAdd(p)}>{t('tm.skAdd')}</Button>
          </div>
        </li>))}</ul>
    </>) : null}
  </>)
}

// The plugins: the kit's own (installed with Camarón, nothing downloaded) and the team's (folders in the team repo's
// .camarones/plugins/, they arrive when you pull it). On or off is this machine's choice only; a team plugin that
// runs code or steers an agent is approved first (the card above), one that sends the docs out is off until enabled.
const PLUGIN_STATE = { active: ['ok', 'tm.active'], 'off on this machine': [undefined, 'tm.off'], invalid: ['bad', 'tm.invalid'] }
function Plugins({ srv, jobs }) {
  const list = useCmd(srv, jobs, { quiet: true })
  const act = useCmd(srv, jobs)
  useEffect(() => { list.run('plugins', { json: true }) }, [])
  const rows = list.job?.result
  const toggle = async (p) => { await act.run('plugins', { action: p.status === 'active' ? 'disable' : 'enable', target: p.name }); list.run('plugins', { json: true }) }
  if (Array.isArray(rows) && !rows.length) return null
  return (
    <Card className="dk-run" data-tour="team-plugins">
      <span className="eyebrow">{t('tm.plugins')}</span>
      <p className="muted small">{t('tm.pluginsLead')}</p>
      {Array.isArray(rows) ? (
        <ul className="dk-units">{rows.map((p) => {
          // a kit plugin that sends the docs out (Confluence, Notion) is simply off until enabled here
          const [state, label] = PLUGIN_STATE[p.status] || (p.source === 'kit' ? [undefined, 'tm.off'] : ['warn', 'tm.needsOk'])
          return (
            <li key={p.name} className="dk-unit">
              <div className="dk-unit-main"><b>{p.name} <span className="muted small">{p.version}</span></b>
                <span className="muted small">{t(p.source === 'kit' ? 'tm.fromKit' : 'tm.fromTeam')} · {(p.provides || []).map((k) => word('pk', k)).join(', ')}</span>
                {p.errors?.length ? <span className="small">{p.errors.join(' · ')}</span> : null}</div>
              <div className="row dk-unit-acts">
                {p.runs_code ? <span className="cu-chip cu-chip--warn">{t('tm.runsCode')}</span> : null}
                {p.sends_data ? <span className="cu-chip cu-chip--warn">{t('tm.sendsData')}</span> : null}
                <span className={'cu-chip' + (state ? ` cu-chip--${state}` : '')}>{t(label)}</span>
                {p.status !== 'invalid' ? <Button size="sm" variant="ghost" disabled={act.running} onClick={() => toggle(p)}>{p.status === 'active' ? t('tm.disable') : t('tm.enable')}</Button> : null}
              </div>
            </li>
          )
        })}</ul>
      ) : <JobOutput c={list} />}
      <JobOutput c={act} />
    </Card>
  )
}

import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test, vi } from 'vitest'
import { Button } from '@camaron/ui'
import Docs from './sections/Docs.jsx'
import { FetchNote, Repo, ShareResult, SyncActions, SyncResult, TeamStripView, TerminalButton, runSync, syncLine } from './sections/TeamStrip.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))

const REMOTE = 'https://gitlab-central.example.space/team/docs.git'
const fatal = "fatal: unable to access 'https://gitlab-central.example.space/team/docs.git/': Could not resolve host: gitlab-central.example.space"
const share = (result) => renderToStaticMarkup(<ShareResult result={result} remote={REMOTE} />)

test('a share that cannot resolve the host says which one and to check the VPN, with git\'s line underneath', () => {
  const out = share({ status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal })
  expect(out).toContain('No llego a gitlab-central.example.space: revisa la conexión, la VPN o el proxy.')
  expect(out).toContain('cu-aviso-detail')
  expect(out).toContain('Could not resolve host')
  expect(out).not.toContain('ha respondido')
  setLang('en')
  expect(share({ status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal }))
    .toContain('I can&#x27;t reach gitlab-central.example.space: check the connection, VPN or proxy.')
})

test('refused credentials link to saving a token for that host in Settings › Tokens', () => {
  const out = share({ status: 'error', reason: 'no-token', host: 'git.acme', detail: 'fatal: Authentication failed' })
  expect(out).toContain('git.acme pide iniciar sesión')
  expect(out).toContain('href="#/settings/tokens?host=git.acme"')
  expect(out).toContain('Guardar un token para git.acme')
  expect(share({ status: 'error', reason: 'network', host: 'git.acme', detail: '' })).not.toContain('#/settings')
})

test('a reason git did not explain, and a success, read as before', () => {
  expect(share({ status: 'error', reason: 'unknown', detail: 'fatal: odd' })).toContain('El repo del equipo ha respondido: fatal: odd')
  const ok = share({ status: 'pushed', detail: 'main' })
  expect(ok).toContain('role="status"')
  expect(ok).toContain('Compartido')
  expect(share(null)).toBe('')
})

test('a failed check for news says why; one that went well says nothing', () => {
  const out = renderToStaticMarkup(<FetchNote fetched={{ ok: false, reason: 'network', host: 'gitlab-central.example.space', detail: fatal }} remote={REMOTE} />)
  expect(out).toContain('No he podido mirar el repo del equipo')
  expect(out).toContain('revisa la conexión, la VPN o el proxy')
  expect(out).toContain('Could not resolve host')
  expect(out).not.toContain('>network<')
  expect(renderToStaticMarkup(<FetchNote fetched={{ ok: true, reason: '' }} remote={REMOTE} />)).toBe('')
})


const noop = () => {}
const strip = (props) => renderToStaticMarkup(<TeamStripView sync={null} result={null} busy="" onRun={noop} onRetry={noop} srv={{}} jobs={null} {...props} />)

test('the strip says it could not read the team repo and offers Retry, without the jokes', () => {
  const out = strip({ sync: { error: 'offline' } })
  expect(out).toContain('No he podido leer cómo va el repo del equipo')
  expect(out).toMatch(/>Reintentar<\/button>/)
  expect(out).toContain('data-tour="docs-team"')
  setLang('en')
  expect(strip({ sync: { error: 'offline' } })).toContain('I could not read the team repo&#x27;s state')
})

test('the strip shows its state, the three team actions when there is a remote, and the repo card inside a details', () => {
  const behind = strip({ sync: { remote: 'git@h:t/d.git', behind: 3, ahead: 0, pending: [], fetched: null } })
  expect(behind).toContain('3 cambios del equipo por traer')
  expect(behind).toMatch(/>Traer cambios<[\s\S]*>Subir cambios<[\s\S]*>Sincronizar</)
  expect(behind).not.toContain('Compartir ahora')
  expect(behind).toMatch(/<details[\s\S]*Repo del equipo[\s\S]*git@github.com:equipo\/cam-docs.git/)
  expect(strip({ sync: { remote: '' } })).toContain('Aún no se comparte con un equipo')
  expect(strip({ sync: { remote: '' } })).not.toContain('Traer cambios')
  expect(strip({ sync: null })).toContain('Leyendo…')
  expect(strip({ sync: { remote: 'r', behind: 0, ahead: 0, pending: [] } })).toContain('Al día con el equipo')
})

test('Docs keeps its tabs and the portal buttons when the team repo cannot be read', () => {
  globalThis.location = { hash: '#/docs' }
  try {
    const srv = { get: () => Promise.reject(new Error('offline')), post: () => new Promise(() => {}) }
    const out = renderToStaticMarkup(<Docs srv={srv} jobs={null} app={{ openExternal: noop }} index={{ repos: [], docs: [] }} />)
    expect(out).toContain('data-tour="docs-team"')
    expect(out).toContain('Leer la documentación')
    expect(out).toMatch(/aria-current="page"[^>]*>Leer</)
  } finally { delete globalThis.location }
})

// GET sync carries last_sync (lib/app/share.py: the newer of the last upload and a good bring-in, ISO with its offset):
// the strip says how far apart you are and how long ago this machine was last in step, in words.
test('the strip says how far apart you are and when this machine was last in step with the team', () => {
  const now = Date.parse('2026-11-18T10:05:00+01:00')
  const sync = { remote: 'git@h:t/d.git', behind: 2, ahead: 1, pending: ['docs/.status.json'], changes: [], last_share: null,
    last_sync: '2026-11-18T10:00:00+01:00' }
  expect(strip({ sync, now })).toContain('2 por traer · 1 por subir · última vez hace 5 min')
  expect(strip({ sync: { ...sync, last_sync: '2026-11-16T09:00:00+01:00' }, now })).toContain('última vez hace 2 d')
  expect(strip({ sync: { ...sync, last_sync: null }, now })).toContain('última vez nunca')
  expect(strip({ sync: { ...sync, last_sync: 'not a date' }, now })).toContain('última vez nunca')
  expect(strip({ sync, now })).not.toContain('sin guardar')
  expect(strip({ sync: { ...sync, changes: ['docs/a.md'] }, now })).toContain('· 1 sin guardar')
  expect(strip({ sync: { remote: '' }, now })).not.toContain('última vez')
  expect(strip({ sync: { error: 'offline' }, now })).not.toContain('última vez')
  setLang('en')
  expect(strip({ sync, now })).toContain('2 to bring in · 1 to upload · last time 5 min ago')
})

test('the strip\'s actions ask for their own step, the useful one primary; a step running says what it is doing', () => {
  const calls = []
  const sync = { remote: 'r', behind: 0, ahead: 0, pending: ['docs/.status.json'], changes: ['docs/a.md'] }
  const row = TeamStripView({ sync, result: null, busy: '', onRun: (k) => calls.push(k), onRetry: noop, srv: {}, jobs: null })
  const [acts] = find(row, (n) => n.type === SyncActions)
  const bs = buttons(SyncActions(acts.props))
  expect(bs.map((b) => b.props.children)).toEqual(['Traer cambios', 'Subir cambios', 'Sincronizar'])
  expect(bs.filter((b) => b.props.variant === 'primary').map((b) => b.props.children)).toEqual(['Subir cambios'])
  bs.forEach((b) => b.props.onClick())
  expect(calls).toEqual(['pull', 'push', 'share'])
  expect(strip({ sync, busy: 'pull' })).toContain('>Trayendo…<')
  expect(strip({ sync: { ...sync, changes: [] } })).not.toContain('cu-btn--primary')
})

test('what the strip\'s step left shows under it: a clash names the files and opens a terminal', () => {
  const result = { kind: 'pull', result: { status: 'done', pull: { status: 'conflict', commits: 0, files: ['docs/a.md'] } } }
  const out = strip({ sync: { remote: 'r', behind: 1, ahead: 0, pending: [] }, result })
  expect(out).toContain('docs/a.md')
  expect(out).toContain('Abrir una terminal aquí')
  expect(strip({ sync: { remote: 'r', behind: 0, ahead: 0, pending: [] }, result: { kind: 'push', result: { status: 'pushed', detail: 'main' } } }))
    .toContain('role="status"')
})

test('the strip remounts the repo card when its key changes, and hands it onChanged', () => {
  const find = (n, type) => (!n || typeof n !== 'object' ? null : n.type === type ? n
    : [].concat(n.props?.children ?? []).map((c) => find(c, type)).find(Boolean) ?? null)
  const el = (repoKey) => find(TeamStripView({ sync: null, result: null, busy: '', onRun: noop, onRetry: noop, srv: {}, jobs: null, onChanged: noop, repoKey }), Repo)
  expect(el(0).key).toBe('0')
  expect(el(1).key).toBe('1')
  expect(el(1).props.onChanged).toBe(noop)
})

const find = (node, pred, out = []) => {
  if (!node || typeof node !== 'object') return out
  if (Array.isArray(node)) { node.forEach((n) => find(n, pred, out)); return out }
  if (pred(node)) out.push(node)
  return find(node.props?.children, pred, out)
}
const buttons = (el) => find(el, (n) => n.type === Button)

test('behind the team, bringing in is the primary button and clicking it asks for a pull; the card adds Check', () => {
  const calls = []
  const s = { remote: 'x', ahead: 0, behind: 2, pending: [] }
  const bs = buttons(SyncActions({ s, busy: '', onRun: (k) => calls.push(k), onCheck: () => {} }))
  const primary = bs.filter((b) => b.props.variant === 'primary')
  expect(primary).toHaveLength(1)
  expect(primary[0].props.children).toBe('Traer cambios')
  primary[0].props.onClick()
  expect(calls).toEqual(['pull'])
  expect(bs.map((b) => b.props.children)).toEqual(['Traer cambios', 'Subir cambios', 'Sincronizar', 'Comprobar'])
  expect(buttons(SyncActions({ s, busy: '', onRun: () => {} })).map((b) => b.props.children)).toEqual(['Traer cambios', 'Subir cambios', 'Sincronizar'])
  setLang('en')
  expect(buttons(SyncActions({ s, busy: '', onRun: () => {}, onCheck: () => {} })).map((b) => b.props.children)[2]).toBe('Sync with the team')
})

test('running a pull posts sync/pull and words the run\'s pull; a busy run says another job has the docs', async () => {
  const post = vi.fn().mockResolvedValue({ result: { status: 'done', pull: { status: 'pulled', commits: 2, files: [] } }, sync: { behind: 0 } })
  const r = await runSync({ post }, 'pull')
  expect(post).toHaveBeenCalledWith('sync/pull', {})
  expect(r.sync).toEqual({ behind: 0 })
  const ok = renderToStaticMarkup(<SyncResult kind="pull" result={r.result} remote={REMOTE} srv={{}} />)
  expect(ok).toContain('He traído 2 cambios del equipo.')
  const busy = renderToStaticMarkup(<SyncResult kind="pull" result={{ status: 'busy', pull: null }} remote={REMOTE} srv={{}} />)
  expect(busy).toContain('Otro trabajo está usando estos docs')
})

test('a push posts sync/push; a pull conflict names the files and offers a terminal', async () => {
  const post = vi.fn().mockResolvedValue({ result: { status: 'pushed' }, sync: {} })
  await runSync({ post }, 'push')
  expect(post).toHaveBeenCalledWith('sync/push', {})
  const result = { status: 'done', pull: { status: 'conflict', commits: 0, files: ['docs/a.md'] } }
  const el = SyncResult({ kind: 'pull', result, remote: REMOTE, srv: { post } })
  expect(renderToStaticMarkup(el)).toContain('docs/a.md')
  const term = el.props.action
  expect(term.type).toBe(TerminalButton)
  term.type(term.props).props.onClick()
  expect(post).toHaveBeenLastCalledWith('app/terminal', {})
})

test('a step refused for its credentials links to saving a token for that host in Settings › Tokens', () => {
  const out = renderToStaticMarkup(<SyncResult kind="push" result={{ status: 'error', reason: 'no-token', host: 'git.acme', detail: 'fatal: Authentication failed' }}
    remote={REMOTE} srv={{}} />)
  expect(out).toContain('href="#/settings/tokens?host=git.acme"')
  expect(out).not.toContain('#/machine')
})

test('a pull request that fails shows the error, not the busy line; only a busy run says another job has the docs', () => {
  const failed = renderToStaticMarkup(<SyncResult kind="pull" result={{ status: 'error', detail: 'sync/pull: 500' }} remote={REMOTE} srv={{}} />)
  expect(failed).toContain('El repo del equipo ha respondido: sync/pull: 500')
  expect(failed).not.toContain('Otro trabajo')
})

test('a pull whose unsaved changes went to the stash warns and offers a terminal', () => {
  const post = vi.fn().mockResolvedValue({ opened: true })
  const result = { status: 'done', pull: { status: 'stashed', commits: 1, files: ['docs/a.md'] } }
  const el = SyncResult({ kind: 'pull', result, remote: REMOTE, srv: { post } })
  const out = renderToStaticMarkup(el)
  expect(out).toContain('He traído los cambios del equipo, pero tus cambios sin guardar chocaban con ellos')
  expect(out).toContain('cu-aviso--warn')
  expect(el.props.action.type).toBe(TerminalButton)
})

test('the status line counts unsaved work only when there is some, never the files the kit rewrites', () => {
  const s = { behind: 1, ahead: 2, pending: ['docs/.status.json'], changes: [], last_share: null }
  expect(syncLine(s)).toBe('1 por traer · 2 por subir · última vez nunca')
  expect(syncLine({ ...s, pending: ['docs/.status.json', 'docs/a.md'], changes: ['docs/a.md'] }))
    .toBe('1 por traer · 2 por subir · última vez nunca · 1 sin guardar')
  setLang('en')
  expect(syncLine({ ...s, changes: ['docs/a.md', 'docs/b.md'] })).toBe('1 to bring in · 2 to upload · last time never · 2 unsaved')
})

test('a pull held by a rebase left half way offers a terminal; one held by an autopilot run only waits', () => {
  const git = SyncResult({ kind: 'pull', result: { status: 'done', pull: { status: 'busy', detail: 'git' } }, remote: REMOTE, srv: {} })
  expect(renderToStaticMarkup(git)).toContain('Hay un rebase o un merge a medias en cam-docs')
  expect(renderToStaticMarkup(git)).toContain('cu-aviso--warn')
  expect(git.props.action.type).toBe(TerminalButton)
  const run = renderToStaticMarkup(<SyncResult kind="pull" result={{ status: 'done', pull: { status: 'busy', detail: 'run' } }} remote={REMOTE} srv={{}} />)
  expect(run).toContain('role="status"')
  expect(run).toContain('trae los cambios del equipo cuando termine')
  expect(run).not.toContain('cu-aviso')
})

test('the status line\'s last time counts a bring-in, not only an upload', () => {
  const s = { behind: 0, ahead: 0, changes: [], last_share: null }
  expect(syncLine({ ...s, last_sync: null })).toContain('última vez nunca')
  expect(syncLine({ ...s, last_sync: new Date().toISOString() })).not.toContain('nunca')
})

test('a share that clashes offers a terminal to resolve it', () => {
  const el = ShareResult({ result: { status: 'conflict', detail: 'docs/a.md' }, remote: REMOTE, srv: {} })
  expect(el.props.action.type).toBe(TerminalButton)
  expect(ShareResult({ result: { status: 'conflict', detail: 'docs/a.md' }, remote: REMOTE }).props.action).toBeNull()
})

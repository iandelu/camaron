import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test, vi } from 'vitest'
import { Button } from '@camaron/ui'
import { FetchNote, ShareResult, SkillsList, SyncActions, SyncResult, TerminalButton, runSync, syncLine } from './sections/Team.jsx'
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

test('refused credentials link to saving a token for that host in Machine', () => {
  const out = share({ status: 'error', reason: 'no-token', host: 'git.acme', detail: 'fatal: Authentication failed' })
  expect(out).toContain('git.acme pide iniciar sesión')
  expect(out).toContain('href="#/machine?host=git.acme"')
  expect(out).toContain('Guardar un token para git.acme')
  expect(share({ status: 'error', reason: 'network', host: 'git.acme', detail: '' })).not.toContain('#/machine')
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

const SKILLS = {
  skills: [
    { name: 'cam-task', origin: 'kit', icon: '🧭', description: 'Start here', project: 'on', machine: 'on', needs_trust: false, pack: null },
    { name: 'ponytail', origin: 'team-only', icon: '🪮', description: 'Lazy', project: 'on', machine: 'off', needs_trust: true, pack: 'ponytail' },
  ],
  available: [{ name: 'impeccable', title: 'Impeccable', icon: '🎨', summary: { en: 'Frontend design', es: 'Diseño frontend' },
    license: 'Apache-2.0', runs_code: true, skills: ['impeccable'] }],
}

test('the skills card shows each skill with its icon, both switches and the packs one can add', () => {
  const out = renderToStaticMarkup(<SkillsList data={SKILLS} />)
  expect(out).toContain('🧭')
  expect(out).toContain('<b>cam-task</b>')
  expect(out).toContain('del kit · Start here')
  expect(out).toContain('pack ponytail · Lazy')
  expect(out).toContain('espera aprobación')
  expect((out.match(/type="checkbox" checked=""/g) || []).length).toBe(3)       // ponytail is off on this machine only
  expect(out).toContain('Solo en Claude Code')
  expect(out).toContain('Packs opcionales')
  expect(out).toContain('Diseño frontend · Apache-2.0 · impeccable')
  expect(out).toContain('ejecuta código')
  expect(out).toContain('Añadir')
  setLang('en')
  const en = renderToStaticMarkup(<SkillsList data={SKILLS} />)
  expect(en).toContain('Frontend design')
  expect(en).toContain('awaits approval')
})

const find = (node, pred, out = []) => {
  if (!node || typeof node !== 'object') return out
  if (Array.isArray(node)) { node.forEach((n) => find(n, pred, out)); return out }
  if (pred(node)) out.push(node)
  return find(node.props?.children, pred, out)
}
const buttons = (el) => find(el, (n) => n.type === Button)

test('behind the team, bringing in is the primary button and clicking it asks for a pull', () => {
  const calls = []
  const s = { remote: 'x', ahead: 0, behind: 2, pending: [] }
  const bs = buttons(SyncActions({ s, busy: '', onRun: (k) => calls.push(k), onCheck: () => {} }))
  const primary = bs.filter((b) => b.props.variant === 'primary')
  expect(primary).toHaveLength(1)
  expect(primary[0].props.children).toBe('Traer cambios')
  primary[0].props.onClick()
  expect(calls).toEqual(['pull'])
  expect(bs.map((b) => b.props.children)).toEqual(['Traer cambios', 'Subir cambios', 'Sincronizar', 'Comprobar'])
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

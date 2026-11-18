import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Docs from './sections/Docs.jsx'
import { FetchNote, Repo, ShareResult, TeamStripView } from './sections/TeamStrip.jsx'
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
const strip = (props) => renderToStaticMarkup(<TeamStripView sync={null} result={null} busy="" onShare={noop} onRetry={noop} srv={{}} jobs={null} {...props} />)

test('the strip says it could not read the team repo and offers Retry, without the jokes', () => {
  const out = strip({ sync: { error: 'offline' } })
  expect(out).toContain('No he podido leer cómo va el repo del equipo')
  expect(out).toMatch(/>Reintentar<\/button>/)
  expect(out).toContain('data-tour="docs-team"')
  setLang('en')
  expect(strip({ sync: { error: 'offline' } })).toContain('I could not read the team repo&#x27;s state')
})

test('the strip shows its state, Share now when there is a remote, and the repo card inside a details', () => {
  const behind = strip({ sync: { remote: 'git@h:t/d.git', behind: 3, ahead: 0, pending: [], fetched: null } })
  expect(behind).toContain('3 cambios del equipo por traer')
  expect(behind).toContain('>Compartir ahora<')
  expect(behind).toMatch(/<details[\s\S]*Repo del equipo[\s\S]*git@github.com:equipo\/cam-docs.git/)
  expect(strip({ sync: { remote: '' } })).toContain('Aún no se comparte con un equipo')
  expect(strip({ sync: { remote: '' } })).not.toContain('>Compartir ahora<')
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

// GET sync carries the last share (lib/app/share.py, ISO with its offset): the strip says how long ago, in words.
test('the strip says when this project last shared, and nothing before the first share', () => {
  const now = Date.parse('2026-11-18T10:05:00+01:00')
  const sync = { remote: 'git@h:t/d.git', behind: 0, ahead: 0, pending: [], last_share: '2026-11-18T10:00:00+01:00' }
  expect(strip({ sync, now })).toContain('Última vez compartido: hace 5 min')
  expect(strip({ sync: { ...sync, last_share: '2026-11-16T09:00:00+01:00' }, now })).toContain('Última vez compartido: hace 2 d')
  expect(strip({ sync: { ...sync, last_share: null }, now })).not.toContain('Última vez')
  expect(strip({ sync: { ...sync, last_share: 'not a date' }, now })).not.toContain('Última vez')
  expect(strip({ sync: { error: 'offline' }, now })).not.toContain('Última vez')
  setLang('en')
  expect(strip({ sync, now })).toContain('Last shared 5 min ago')
})

test('the strip remounts the repo card when its key changes, and hands it onChanged', () => {
  const find = (n, type) => (!n || typeof n !== 'object' ? null : n.type === type ? n
    : [].concat(n.props?.children ?? []).map((c) => find(c, type)).find(Boolean) ?? null)
  const el = (repoKey) => find(TeamStripView({ sync: null, result: null, busy: '', onShare: noop, onRetry: noop, srv: {}, jobs: null, onChanged: noop, repoKey }), Repo)
  expect(el(0).key).toBe('0')
  expect(el(1).key).toBe('1')
  expect(el(1).props.onChanged).toBe(noop)
})

import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { FetchLine, ShareLine, busyLabel } from './Sync.jsx'
import { STRINGS } from './i18n.js'
import { I18N } from './i18n/portal.js'

const as = (l) => { globalThis.localStorage = { getItem: () => l } }
afterEach(() => { delete globalThis.localStorage })

const REMOTE = 'https://gitlab-central.example.space/team/docs.git'
const fatal = "fatal: unable to access 'https://gitlab-central.example.space/team/docs.git/': Could not resolve host: gitlab-central.example.space"
const line = (result) => renderToStaticMarkup(<ShareLine result={result} remote={REMOTE} />)

test('a share that cannot resolve the host says which one and to check the VPN, with git\'s line underneath', () => {
  as('es')
  const out = line({ status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal })
  expect(out).toContain('No llego a gitlab-central.example.space: revisa la conexión, la VPN o el proxy.')
  expect(out).toContain('Could not resolve host')
  expect(out).not.toContain('ha respondido')
  as('en')
  expect(line({ status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal }))
    .toContain('I can&#x27;t reach gitlab-central.example.space: check the connection, VPN or proxy.')
})

test('refused credentials send to the desktop app for a token; the portal saves none', () => {
  as('en')
  const out = line({ status: 'error', reason: 'auth', host: 'git.acme', detail: 'fatal: Authentication failed' })
  expect(out).toContain('git.acme rejected your credentials')
  expect(out).toContain('Save a token for git.acme in the desktop app (Machine › Tokens).')
})

test('a reason git did not explain, and a success, read as before', () => {
  as('en')
  expect(line({ status: 'error', reason: 'unknown', detail: 'fatal: odd' })).toContain('The team&#x27;s repo answered: fatal: odd')
  const ok = line({ status: 'pushed', detail: 'main' })
  expect(ok).toContain('class="ok"')
  expect(ok).toContain('Shared')
})

test('a failed check for news says why instead of a bare code', () => {
  as('en')
  const out = renderToStaticMarkup(<FetchLine fetched={{ ok: false, reason: 'network', host: 'gitlab-central.example.space', detail: fatal }} remote={REMOTE} />)
  expect(out).toContain('I can&#x27;t reach gitlab-central.example.space: check the connection, VPN or proxy.')
  expect(out).toContain('Could not resolve host')
  expect(out).not.toContain('I could not reach the team')
  expect(out).not.toMatch(/: network</)
  const odd = renderToStaticMarkup(<FetchLine fetched={{ ok: false, reason: 'unknown', detail: 'fatal: odd' }} remote={REMOTE} />)
  expect(odd).toContain('I could not reach the team&#x27;s repo:')
  expect(odd).toContain('fatal: odd')
  expect(renderToStaticMarkup(<FetchLine fetched={{ ok: true, reason: '' }} remote={REMOTE} />)).toBe('')
})

test('a pull and a push each read with their own sentences', () => {
  as('en')
  const out = renderToStaticMarkup(<ShareLine action="pull" result={{ status: 'conflict', files: ['docs/a.md'], commits: 0 }} remote={REMOTE} />)
  expect(out).toContain('clash with yours in docs/a.md')
  expect(renderToStaticMarkup(<ShareLine action="push" result={{ status: 'pushed' }} remote={REMOTE} />)).toContain('role="status"')
})

test('a pull whose unsaved changes went to the stash says where they are', () => {
  as('es')
  expect(renderToStaticMarkup(<ShareLine action="pull" result={{ status: 'stashed', files: ['docs/a.md'], commits: 1 }} remote={REMOTE} />))
    .toContain('están a salvo en el stash de git (`git stash list`)')
  as('en')
  expect(renderToStaticMarkup(<ShareLine action="pull" result={{ status: 'stashed', files: ['docs/a.md'], commits: 1 }} remote={REMOTE} />))
    .toContain('they are safe in git&#x27;s stash (`git stash list`)')
})

test('a busy pull says what holds the docs', () => {
  as('en')
  const git = renderToStaticMarkup(<ShareLine action="pull" result={{ status: 'busy', detail: 'git' }} remote={REMOTE} />)
  expect(git).toContain('A rebase or merge is unfinished in cam-docs: finish or abort it in a terminal.')
  const run = renderToStaticMarkup(<ShareLine action="pull" result={{ status: 'busy', detail: 'run' }} remote={REMOTE} />)
  expect(run).toContain('An autopilot run is using the docs: bring in the team&#x27;s changes once it ends.')
  expect(run).toContain('role="status"')
  as('es')
  expect(renderToStaticMarkup(<ShareLine action="pull" result={{ status: 'busy', detail: 'run' }} remote={REMOTE} />))
    .toContain('Hay una ejecución del autopiloto usando los docs: trae los cambios del equipo cuando termine.')
})

test('each team action says what it is doing while it runs', () => {
  as('en')
  expect(['pull', 'push', 'share'].map(busyLabel)).toEqual(['Bringing in…', 'Uploading…', 'Working with the team…'])
  as('es')
  expect(['pull', 'push', 'share'].map(busyLabel)).toEqual(['Trayendo…', 'Subiendo…', 'Trabajando con el equipo…'])
})

// Spec §6.4: the UI never uses the bare English word "sync" for the team's docs (the CLI's `sync` is the code repos).
test('no bare sync in the portal\'s English strings, and the view says what it does', () => {
  const bare = [...Object.values(STRINGS.en), ...Object.values(I18N.en)]
    .filter((v) => typeof v === 'string' && /\bsync(ing|ed)?\b/i.test(v) && !/\b(sync with the team|team sync)\b/i.test(v))
  expect(bare).toEqual([])
  expect(I18N.en['view.sync']).toBe('Team sync')
  expect(I18N.en['viewd.sync']).toBe('Bring in the team\'s changes and upload yours')
  expect(I18N.es['viewd.sync']).toBe('Trae los cambios del equipo y sube los tuyos')
})

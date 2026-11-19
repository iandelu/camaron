import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import SonarView, { SonarTable } from './sections/SonarView.jsx'
import { setLang } from './i18n.js'

afterEach(() => { setLang('es'); delete globalThis.location })

const snapshot = {
  at: '2026-11-18T11:00:00Z',
  repos: {
    api: { cloned: true, sonar: { used: true, link: 'https://sonar.example.com/dashboard?id=api',
      server: { gate: 'OK', coverage: 78, bugs: 3, vulnerabilities: 0, debt_minutes: 540, at: '2026-11-18T11:00:00Z' } } },
    web: { cloned: true, sonar: { used: false, connect: true, host: 'https://sonar.example.com' }, coverage: { percent: 64, source: 'report', at: '2026-11-15' },
      vulns: { high: 1, medium: 4 } },
    bad: { error: 'boom' },
  },
  docs: { stale: [{ path: 'a.md', repos: ['web'] }], suspect: [] },
  inventory: { scanned: true },
}
const now = Date.parse('2026-11-18T12:00:00Z')
const draw = (p = {}) => renderToStaticMarkup(<SonarTable snapshot={snapshot} repo="" source="" open="" onRepo={() => {}} onSource={() => {}} onOpen={() => {}}
  onRefresh={() => {}} refreshing={false} now={now} {...p} />)

test('while the snapshot loads it shows a skeleton', () => {
  globalThis.location = { hash: '#/quality/sonar' }
  const out = renderToStaticMarkup(<SonarView srv={{ get: () => new Promise(() => {}) }} jobs={null} />)
  expect(out).toContain('cu-skel')
})

test('the table has its columns and opens SonarQube for a sonar-backed repo', () => {
  const out = draw()
  for (const h of ['Repo', 'Fuente', 'Puerta', 'Cobertura', 'Bugs', 'Vulnerab. código', 'Deuda']) expect(out).toContain(`>${h}</th>`)
  expect(out).toMatch(/<a[^>]*href="https:\/\/sonar\.example\.com\/dashboard\?id=api"[^>]*>Abrir en SonarQube ↗/)
  expect(out).toMatch(/<td><a href="#\/flow\/repo\/api"><b>api<\/b><\/a><\/td><td>(<span[^>]*>)?SonarQube/)
  expect(out).toMatch(/href="https:\/\/sonar\.example\.com\/dashboard\?id=api"[^>]*target="_blank"[^>]*rel="noreferrer"/)
  expect(out).toContain('href="#/flow/repo/api"')
  expect(out).toContain('Leído hace 1 h')
})

test('the source filter counts and says which is pressed', () => {
  const out = draw({ source: 'sonar' })
  expect(out).toMatch(/aria-pressed="true"[^>]*>SonarQube · 1</)
  expect(out).toMatch(/aria-pressed="false"[^>]*>Estimado · 1</)
})

test('the estimate panel opens under its row with the figures and the way to connect', () => {
  const out = draw({ open: 'web' })
  expect(out).toContain('aria-expanded="true"')
  expect(out).toContain('64 %')
  expect(out).toContain('href="#/quality/libs?repo=web"')
  expect(out).toContain('href="#/docs/wikis?repo=web"')
  expect(out).toContain('no se puede saber')
  expect(out).toMatch(/href="#\/settings\/tokens\?host=https%3A%2F%2Fsonar\.example\.com&amp;kind=sonarqube"[^>]*>Conectar SonarQube/)
  expect(draw()).not.toContain('Conectar SonarQube')
})

test('a repo filter keeps only its row; an unread row says why', () => {
  const out = draw({ repo: 'web' })
  expect(out).toContain('#/flow/repo/web')
  expect(out).not.toContain('#/flow/repo/api')
  const all = draw()
  expect(all).toContain('Sin leer')
  expect(all).toContain('boom')
})

test('an unreadable Sonar block shows its reason, no estimate toggle, and is counted in neither source', () => {
  const s = { ...snapshot, repos: { ...snapshot.repos, gone: { cloned: true, sonar: { error: 'token no válido' } } } }
  const out = draw({ snapshot: s })
  expect(out).toContain('Sin leer')
  expect(out).toContain('Token no válido')
  expect(out).toMatch(/aria-pressed="false"[^>]*>Estimado · 1</)
  expect(out.match(/Ver estimación/g)).toHaveLength(1)
})

test('figures kept from an earlier read show why the last read failed', () => {
  const s = structuredClone(snapshot)
  s.repos.api.sonar.error = 'token no válido'
  expect(draw({ snapshot: s })).toContain('Token no válido')
})

test('a repos block that could not be read says so with its message and draws no fake row', () => {
  const out = draw({ snapshot: { at: snapshot.at, repos: { error: 'no pude leer workspace.yaml' } } })
  expect(out).toContain('Sin leer')
  expect(out).toContain('no pude leer workspace.yaml')
  expect(out).not.toContain('#/flow/repo/error')
  expect(out).not.toContain('<tbody>')
})

test('with no snapshot it says so and points to Health', () => {
  const out = draw({ snapshot: null })
  expect(out).toContain('Aún no hay foto de salud del proyecto.')
  expect(out).toContain('href="#/quality"')
})

test('the source column names the source as a chip; the estimate toggle sits in the last column', () => {
  const rows = draw().match(/<tr>[\s\S]*?<\/tr>/g)
  const web = rows.find((r) => r.includes('#/flow/repo/web'))
  const cells = web.match(/<td>[\s\S]*?<\/td>/g)
  expect(cells[1]).toMatch(/cu-chip--info[^>]*>Estimado</)
  expect(cells[1]).not.toContain('Ver estimación')
  expect(cells.at(-1)).toContain('Ver estimación')
  const api = rows.find((r) => r.includes('#/flow/repo/api')).match(/<td>[\s\S]*?<\/td>/g)
  expect(api[1]).not.toContain('Abrir en SonarQube')
  expect(api.at(-1)).toContain('Abrir en SonarQube ↗')
})

test('the estimate does not claim zero vulnerabilities when no scan ever ran', () => {
  const s = { ...snapshot, inventory: { scanned: false } }
  const out = draw({ snapshot: s, open: 'web' })
  expect(out).toContain('Aún no se han buscado vulnerabilidades.')
  expect(out).toContain('href="#/quality/libs?repo=web"')
  expect(out).not.toContain('0 altas')
  expect(draw({ open: 'web' })).toContain('1 altas')
})

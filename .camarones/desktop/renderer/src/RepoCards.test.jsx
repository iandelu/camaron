import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import RepoCards, { RepoCardsView } from './sections/RepoCards.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))

const NOW = Date.parse('2026-11-19T12:00:00Z')
const mk = (name, o = {}) => ({ name, cloned: true, state: 'ok', stack: [{ role: 'language', label: 'Java 17' }, { role: 'framework', label: 'Spring Boot' }],
  sonar: { source: 'sonar', gate: 'OK', coverage: 78, coverageSource: 'sonar' }, libs: { vulns: {}, scanned: true },
  wiki: { pages: 42, at: '2026-11-17T12:00:00Z', unit: null }, docs: { total: 4, stale: 0, suspect: 0 }, ...o })
const data = { at: '2026-11-19T11:55:00Z', repos: [mk('api'), mk('web', { state: 'warn' }), mk('db', { cloned: false, state: null, sonar: null, wiki: null, docs: null })] }
const render = (d = data) => renderToStaticMarkup(<RepoCardsView data={d} now={NOW} />)

test('one link per repo to its page, with its state word, stack and the four facts', () => {
  const out = render()
  for (const n of ['api', 'web', 'db']) expect(out).toContain(`href="#/flow/repo/${n}"`)
  expect(out.match(/<a [^>]*href="#\/flow\/repo\//g)).toHaveLength(3)
  expect(out).toContain('Sano')
  expect(out).toContain('Revisar')
  expect(out).toContain('Sin estado')
  expect(out).toContain('Java 17 · Spring Boot')
  expect(out).toContain('<svg')
  for (const w of ['SonarQube', 'Librerías', 'Wiki', 'Docs']) expect(out).toContain(`<dt>${w}</dt>`)
  expect(out).toContain('Aprobado · 78 %')
  expect(out).toContain('42 páginas · hace 2 d')
  expect(out.match(/Abrir repo →/g)).toHaveLength(3)
})

test('the header counts the repos with the health age and links to Health', () => {
  const out = render()
  expect(out).toContain('3 repos · salud hace 5 min')
  expect(out).toMatch(/<a [^>]*href="#\/quality"[^>]*>Ver la salud completa<\/a>/)
})

test('with no health snapshot the header says so beside the link', () => {
  const out = render({ ...data, at: null })
  expect(out).toContain('aún no hay foto de salud')
  expect(out).not.toContain('salud hace')
  expect(out).toContain('Ver la salud completa')
})

test('an estimated card says Estimado before its coverage; a Sonar-backed one does not', () => {
  const est = render({ ...data, repos: [mk('api', { sonar: { source: 'estimated', coverage: 64, coverageSource: 'report' } })] })
  expect(est).toMatch(/cu-chip--info">Estimado<\/span> 64 % · informe/)
  expect(render()).not.toContain('Estimado')
})

test('one repo reads "1 repo", with or without health', () => {
  expect(render({ ...data, repos: [mk('api')] })).toContain('1 repo · salud hace 5 min')
  expect(render({ at: null, repos: [mk('api')] })).toContain('1 repo · aún no hay foto de salud')
  expect(render({ ...data, at: null })).toContain('3 repos · aún no hay foto de salud')
})

test('while it loads, a skeleton', () => {
  const srv = { get: () => new Promise(() => {}) }
  const jobs = { get: () => ({ running: [] }), subscribe: () => () => {} }
  expect(renderToStaticMarkup(<RepoCards srv={srv} jobs={jobs} />)).toContain('cu-skel')
})

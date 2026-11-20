import { expect, test } from 'vitest'
import { activityBars, docsParts, libsRows, repoCard, ROLES, sonarTile, tileLinks, workParts } from './repo.js'
import { t } from './i18n.js'

test('each tile links to its window filtered to the repo', () => {
  expect(tileLinks('api')).toEqual({ sonar: '#/quality/sonar?repo=api', libs: '#/quality/libs?repo=api',
    wikis: '#/docs/wikis?repo=api', board: '#/board?repo=api', decisions: '#/docs/decisions?repo=api' })
})

test('the sonar tile keeps its source and the coverage trend', () => {
  expect(sonarTile({ source: 'sonar', coverage: 78, gate: 'OK' }, [{ coverage: 70 }, { coverage: 78 }]))
    .toEqual({ source: 'sonar', coverage: 78, delta: 8, points: [70, 78], gate: 'OK' })
  expect(sonarTile({ source: 'estimated', coverage: null, gate: null }, [{ coverage: 64 }]).delta).toBeNull()
  expect(sonarTile(null, []).source).toBeNull()
  expect(sonarTile({ source: 'sonar', coverage: 1, gate: null }, [{ coverage: 70.1 }, { coverage: 70.4 }]).delta).toBe(0.3)
})

test('activity bars carry a tip per week and the months where one starts', () => {
  const weeks = [{ start: '2026-08-31', n: 2 }, { start: '2026-09-07', n: 1 },
    ...Array.from({ length: 10 }, (_, i) => ({ start: new Date(Date.UTC(2026, 9, 5 + i * 7)).toISOString().slice(0, 10), n: 0 }))]
  const bars = activityBars({ weeks, total: 3, people: 1, last: null }, 'es')
  expect(bars.values.slice(0, 2)).toEqual([2, 1])
  expect(bars.tips[0]).toBe('31 ago · 2 commits')
  expect(bars.tips[1]).toBe('7 sept · 1 commit')
  expect(bars.months[0]).toBe('ago')
  expect(activityBars(null, 'es')).toBeNull()
})

test('an advisory with no severity gets its own row, and any other severity folds into it', () => {
  expect(libsRows({ vulns: { unknown: 1 } }).at(-1)).toEqual({ key: 'unknown', n: 1, tone: null })
  expect(libsRows({ vulns: { high: 1, unknown: 1, weird: 2 } }).map((r) => r.n)).toEqual([0, 1, 0, 0, 3])
  expect(libsRows({ vulns: { low: 2 } }).map((r) => r.key)).toEqual(['critical', 'high', 'medium', 'low'])
})

test('libraries, docs and work fold into their rows', () => {
  expect(libsRows({ vulns: { high: 1, medium: 1, moderate: 2 } }).map((r) => r.n)).toEqual([0, 1, 3, 0])
  expect(libsRows({ vulns: {} }).map((r) => r.tone)).toEqual(['bad', 'bad', 'warn', null])
  expect(docsParts({ fresh: 3, suspect: 2, stale: 1 })).toEqual([
    { key: 'fresh', n: 3, tone: 'ok' }, { key: 'suspect', n: 2, tone: 'warn' }, { key: 'stale', n: 1, tone: 'bad' }])
  const columns = [{ status: 'Backlog', n: 1 }, { status: 'Ready', n: 1 }, { status: 'In Progress', n: 1 },
    { status: 'In Review', n: 0 }, { status: 'Done', n: 2 }, { status: 'Blocked', n: 1 }]
  expect(workParts({ columns, total: 6 }).map((p) => p.n)).toEqual([2, 1, 0, 2, 1])
  expect(workParts({ columns, total: 6 })[4]).toEqual({ key: 'blocked', n: 1, tone: 'warn' })
  expect(ROLES).toEqual(['language', 'framework', 'build', 'data', 'container', 'ci'])
})

const NOW = Date.parse('2026-11-19T12:00:00Z')
const row = (o = {}) => ({ name: 'api', cloned: true, state: 'ok', stack: [{ role: 'language', label: 'Java 17' }], sonar: null,
  libs: { vulns: {}, scanned: true }, wiki: null, docs: null, ...o })
const card = (o) => repoCard(row(o), t, NOW)

test('a card reads Sonar from the server or from the estimate, and says so', () => {
  const ok = card({ sonar: { source: 'sonar', gate: 'OK', coverage: 78, coverageSource: 'sonar' } }).sonar
  expect(ok).toMatchObject({ kind: 'sonar', gateState: 'ok' })
  expect(ok.text).toContain('Aprobado')
  expect(ok.text).toContain('78 %')
  expect(card({ sonar: { source: 'estimated', coverage: 64, coverageSource: 'report' } }).sonar)
    .toMatchObject({ kind: 'estimated', text: '64 % · informe' })
  expect(card({ sonar: { source: 'estimated', coverage: null } }).sonar.text).toBe('sin cobertura')
  expect(card({ sonar: null }).sonar).toMatchObject({ kind: 'none', text: '—' })
})

test('a card counts vulnerabilities and says when nothing was checked', () => {
  expect(card({ libs: { vulns: { high: 1, medium: 1 }, scanned: true } }).libs).toEqual({ text: '2 vulnerabilidades', tone: 'bad' })
  expect(card({ libs: { vulns: { medium: 1 }, scanned: true } }).libs).toEqual({ text: '1 vulnerabilidad', tone: 'warn' })
  expect(card({ libs: { vulns: {}, scanned: true } }).libs.text).toBe('Sin vulnerabilidades')
  expect(card({ libs: { vulns: {}, scanned: false } }).libs.text).toBe('Sin revisar')
})

test('a card says what the wiki and the docs stand at', () => {
  expect(card({ wiki: { pages: 42, at: '2026-11-17T12:00:00Z' } }).wiki).toBe('42 páginas · hace 2 d')
  expect(card({ wiki: { pages: 0 } }).wiki).toBe('Sin generar')
  expect(card({ wiki: null }).wiki).toBe('Sin generar')
  expect(card({ wiki: { pages: 3, at: null, unit: 'doing' } }).wiki).toBe('Generándose…')
  expect(card({ docs: { total: 9, stale: 3, suspect: 0 } }).docs).toEqual({ text: '3 desactualizadas', tone: 'warn' })
  expect(card({ docs: { total: 9, stale: 1, suspect: 0 } }).docs.text).toBe('1 desactualizada')
  expect(card({ docs: { total: 9, stale: 3, suspect: 2 } }).docs).toEqual({ text: '3 desactualizadas', tone: 'warn' })
  expect(card({ docs: { total: 9, stale: 0, suspect: 2 } }).docs).toEqual({ text: '2 por revisar', tone: 'warn' })
  expect(card({ docs: { total: 9, stale: 0, suspect: 1 } }).docs.text).toBe('1 por revisar')
  expect(card({ docs: { total: 4, stale: 0, suspect: 0 } }).docs.text).toBe('Al día')
  expect(card({ docs: { total: 0 } }).docs.text).toBe('Sin páginas')
})

test('a repo not cloned here claims no Sonar or library state, whatever the server sent', () => {
  const c = card({ cloned: false, sonar: null, libs: { vulns: {}, scanned: true } })
  expect(c.libs).toEqual({ text: 'No está clonado aquí', tone: null })
  expect(c.sonar).toEqual({ kind: 'none', text: 'No está clonado aquí', gateState: null })
})

test('a card links to the repo page; a repo not cloned has no state', () => {
  expect(card().href).toBe('#/flow/repo/api')
  expect(card({ cloned: false, state: 'ok' }).state).toBe('Sin estado')
  expect(card({ state: 'ok' }).state).toBe('Sano')
})

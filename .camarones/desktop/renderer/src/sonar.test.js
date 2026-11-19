import { expect, test } from 'vitest'
import { uiText } from '@camaron/ui'
import { estimate, filterSonar, sonarRows, sourceCounts } from './sonar.js'

const t = (k) => uiText(k, 'es')
const now = Date.parse('2026-11-18T12:00:00Z')
const snap = {
  repos: {
    api: { cloned: true, sonar: { used: true, link: 'https://sonar.example.com/dashboard?id=api',
      server: { gate: 'OK', coverage: 78, bugs: 3, vulnerabilities: 0, debt_minutes: 540, at: '2026-11-18T11:00:00Z' } } },
    web: { cloned: true, coverage: { percent: 64, source: 'report', at: '2026-11-15' }, vulns: { high: 1, medium: 4 } },
    worker: { cloned: false },
    bad: { error: 'boom' },
  },
  docs: { stale: [{ path: 'a.md', repos: ['web'] }, { path: 'b.md', repos: ['web', 'api'] }, { path: 'c.md', repos: ['api'] }], suspect: [] },
}

test('the source of each repo: sonar when the server was read, estimated otherwise, none when not cloned or unread', () => {
  expect(sonarRows(snap, t, now).map((r) => [r.name, r.source])).toEqual([['api', 'sonar'], ['web', 'estimated'], ['worker', null], ['bad', null]])
})

test('a sonar-backed row carries the server figures as strings', () => {
  const api = sonarRows(snap, t, now)[0]
  expect(api).toMatchObject({ gate: t('hb.gate.OK'), gateState: 'ok', coverage: '78 %', bugs: '3', vulns: '0', debt: '1 d 1 h', link: 'https://sonar.example.com/dashboard?id=api' })
  const bad = structuredClone(snap)
  bad.repos.api.sonar.link = 'javascript:alert(1)'
  expect(sonarRows(bad, t, now)[0].link).toBeNull()
})

test('an estimated row has the report coverage and dashes elsewhere', () => {
  const web = sonarRows(snap, t, now)[1]
  expect(web).toMatchObject({ gate: '—', coverage: '64 %', bugs: '—' })
  expect(web.coverageNote).toContain(t('hb.source.report'))
})

test('a failed block is unread with its reason', () => {
  expect(sonarRows(snap, t, now)[3]).toMatchObject({ unread: true, error: 'boom' })
})

test('the estimate of a repo, from what the kit knows without a server', () => {
  expect(estimate(snap, 'web')).toEqual({ coverage: { percent: 64, at: '2026-11-15' }, vulns: { total: 5, high: 1 }, stale: 2, suspect: 0, host: '' })
  expect(estimate(null, 'web').coverage).toBeNull()
})

test('filters and counts', () => {
  const rows = sonarRows(snap, t, now)
  expect(filterSonar(rows, { repo: 'web' }).map((r) => r.name)).toEqual(['web'])
  expect(filterSonar(rows, { source: 'sonar' }).map((r) => r.name)).toEqual(['api'])
  expect(sourceCounts(rows)).toEqual({ sonar: 1, estimated: 1 })
  expect(sonarRows(null, t, now)).toEqual([])
})

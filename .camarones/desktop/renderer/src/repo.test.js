import { expect, test } from 'vitest'
import { activityBars, docsParts, libsRows, ROLES, sonarTile, tileLinks, workParts } from './repo.js'

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

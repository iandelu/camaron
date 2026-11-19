import { S } from './i18n.js'
import { withRepo } from './nav.js'

export const ROLES = ['language', 'framework', 'build', 'data', 'container', 'ci']

export const tileLinks = (name) => ({
  sonar: withRepo('quality/sonar', name), libs: withRepo('quality/libs', name), wikis: withRepo('docs/wikis', name),
  board: withRepo('board', name), decisions: withRepo('docs/decisions', name),
})

export const sonarTile = (sonar, trend = []) => {
  const points = trend.map((p) => p.coverage)
  const delta = points.length >= 2 ? Math.round((points[points.length - 1] - points[0]) * 10) / 10 : null
  return { source: sonar?.source ?? null, coverage: sonar?.coverage ?? null, delta, points, gate: sonar?.gate ?? null }
}

const word = (l, k) => (S[l] ?? S.es)[k] ?? S.es[k] ?? k

export const activityBars = (activity, l) => {
  if (!activity) return null
  const day = new Intl.DateTimeFormat(l, { day: 'numeric', month: 'short', timeZone: 'UTC' })
  const month = new Intl.DateTimeFormat(l, { month: 'short', timeZone: 'UTC' })
  const starts = activity.weeks.map((w) => new Date(`${w.start}T00:00:00Z`))
  return {
    values: activity.weeks.map((w) => w.n),
    tips: activity.weeks.map((w, i) => `${day.format(starts[i])} · ${w.n} ${word(l, w.n === 1 ? 'rp.commit' : 'rp.commits')}`),
    months: starts.flatMap((d, i) => (i === 0 || d.getUTCMonth() !== starts[i - 1].getUTCMonth() ? [month.format(d)] : [])),
  }
}

export const libsRows = (libs) => {
  const v = libs?.vulns || {}
  return [
    { key: 'critical', n: v.critical || 0, tone: 'bad' },
    { key: 'high', n: v.high || 0, tone: 'bad' },
    { key: 'medium', n: (v.medium || 0) + (v.moderate || 0), tone: 'warn' },
    { key: 'low', n: v.low || 0, tone: null },
  ]
}

export const docsParts = (docs) => [
  { key: 'fresh', n: docs?.fresh || 0, tone: 'ok' },
  { key: 'suspect', n: docs?.suspect || 0, tone: 'warn' },
  { key: 'stale', n: docs?.stale || 0, tone: 'bad' },
]

export const workParts = (work) => {
  const n = (...names) => (work?.columns || []).filter((c) => names.includes(c.status)).reduce((s, c) => s + c.n, 0)
  return [
    { key: 'todo', n: n('Backlog', 'Ready'), ordinal: 1 },
    { key: 'doing', n: n('In Progress'), ordinal: 2 },
    { key: 'review', n: n('In Review'), ordinal: 3 },
    { key: 'done', n: n('Done'), ordinal: 4 },
    { key: 'blocked', n: n('Blocked'), tone: 'warn' },
  ]
}

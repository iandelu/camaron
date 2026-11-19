import { fmtAgo, gateState, gateWord, sourceWord, stateWord, uiText } from '@camaron/ui'
import { S, lang } from './i18n.js'
import { repoHref, withRepo } from './nav.js'

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

const pct = (n) => `${new Intl.NumberFormat(lang(), { maximumFractionDigits: 1 }).format(n)} %`

// One repo's card on Flow › Summary: four short facts, each a word plus (where colour means state) a tone. `t` is the
// renderer's; the kit's own words (gate, state, ago) come from the kit.
export function repoCard(row, t, now) {
  const kit = (k) => uiText(k, lang())
  const known = (n) => typeof n === 'number'
  let sonar = { kind: 'none', text: '—', gateState: null }
  if (row.sonar) {
    const { source, gate, coverage, coverageSource } = row.sonar
    if (source === 'sonar') {
      const parts = [gate ? gateWord(gate, kit) : '', known(coverage) ? pct(coverage) : ''].filter((p) => p && p !== '—')
      sonar = { kind: 'sonar', text: parts.join(' · ') || '—', gateState: gateState(gate) }
    } else {
      const from = coverageSource ? (coverageSource === 'report' ? t('rc.report') : sourceWord(coverageSource, kit)) : ''
      sonar = { kind: 'estimated', gateState: null, text: known(coverage) ? [pct(coverage), from].filter(Boolean).join(' · ') : t('rc.noCoverage') }
    }
  }
  const vulns = Object.values(row.libs?.vulns || {}).reduce((s, n) => s + n, 0)
  const severe = (row.libs?.vulns?.critical || 0) + (row.libs?.vulns?.high || 0)
  const libs = !row.libs?.scanned ? { text: t('rc.unscanned'), tone: null }
    : vulns ? { text: vulns === 1 ? t('rc.vuln') : t('rc.vulns', { n: vulns }), tone: severe ? 'bad' : 'warn' }
      : { text: t('rc.clean'), tone: 'ok' }
  const wiki = row.wiki?.unit === 'doing' ? t('rc.wikiRunning')
    : row.wiki?.pages ? t('rc.wikiPages', { n: row.wiki.pages, ago: fmtAgo(row.wiki.at, now, kit) }) : t('rc.wikiNone')
  const stale = (row.docs?.stale || 0) + (row.docs?.suspect || 0)
  const docs = !row.docs?.total ? { text: t('rc.noPages'), tone: null }
    : stale ? { text: stale === 1 ? t('rc.stale1') : t('rc.stale', { n: stale }), tone: 'warn' } : { text: t('rc.fresh'), tone: 'ok' }
  return {
    name: row.name, href: repoHref(row.name), state: stateWord('code', row.cloned ? row.state : null, kit), stateTone: row.cloned ? row.state : null,
    stack: (row.stack || []).filter((p) => ROLES.includes(p.role)).map((p) => p.label).join(' · '),
    sonar, libs, wiki, docs,
  }
}

import { fmtAgo, fmtDebt, gateState, gateWord, safeUrl, sonarGone, sonarReason, sourceWord } from '@camaron/ui/health.js'

const DASH = '—'
const object = (x) => !!x && typeof x === 'object' && !Array.isArray(x)
const num = (n) => typeof n === 'number' && Number.isFinite(n)
const figure = (n) => (num(n) ? String(n) : DASH)
const percent = (n) => (num(n) ? `${n} %` : DASH)
const list = (x) => (Array.isArray(x) ? x : [])

const serverOf = (repo) => (object(repo?.sonar?.server) ? repo.sonar.server : null)

// The snapshot's coverage is already server-first (a server with no coverage metric falls back to the repo's report).
const coverageOf = (repo, t) => (object(repo.coverage) && num(repo.coverage.percent)
  ? { coverage: percent(repo.coverage.percent),
      coverageNote: [sourceWord(repo.coverage.source, t), typeof repo.coverage.at === 'string' ? repo.coverage.at.slice(0, 10) : ''].filter(Boolean).join(' · ') }
  : null)

// The message of a repos block that could not be read at all (`{error}` in place of the repos), else ''.
export const reposError = (snapshot) => (object(snapshot?.repos) && typeof snapshot.repos.error === 'string' ? snapshot.repos.error : '')

export function sonarSource(block) {
  if (!object(block) || block.cloned === false || typeof block.error === 'string') return null
  if (object(block.sonar) && sonarGone(block.sonar)) return null
  return serverOf(block) ? 'sonar' : 'estimated'
}

export function sonarRows(snapshot, t, now) {
  const repos = snapshot?.repos
  if (!object(repos) || reposError(snapshot)) return []
  return Object.entries(repos).map(([name, repo]) => {
    const row = { name, source: sonarSource(repo), gate: DASH, gateState: null, coverage: DASH, coverageNote: '', bugs: DASH, vulns: DASH,
      debt: DASH, link: null, host: '', connect: null, error: '', unread: false }
    if (!object(repo)) return row
    if (typeof repo.error === 'string') return { ...row, unread: true, error: repo.error }
    if (repo.cloned === false) return row
    const sonar = object(repo.sonar) ? repo.sonar : null
    if (sonarGone(sonar)) return { ...row, unread: true, error: sonarReason(sonar.error, t) }
    if (sonar && typeof sonar.host === 'string') row.host = sonar.host
    if (sonar?.connect === true) row.connect = row.host
    if (sonar?.used) row.link = safeUrl(sonar.link)
    const server = serverOf(repo)
    if (server) {
      Object.assign(row, { gate: gateWord(server.gate, t), gateState: gateState(server.gate),
        bugs: figure(server.bugs), vulns: figure(server.vulnerabilities), debt: fmtDebt(server.debt_minutes) })
      Object.assign(row, num(server.coverage) ? { coverage: percent(server.coverage), coverageNote: sourceWord('sonar', t) } : coverageOf(repo, t))
      if (typeof sonar.error === 'string') row.error = sonarReason(sonar.error, t) + ' · ' + fmtAgo(server.at, now, t)
    } else Object.assign(row, coverageOf(repo, t))
    return row
  })
}

export function estimate(snapshot, name) {
  const repo = snapshot?.repos?.[name]
  const cov = object(repo?.coverage) && num(repo.coverage.percent) ? { percent: repo.coverage.percent, at: typeof repo.coverage.at === 'string' ? repo.coverage.at : '' } : null
  const v = object(repo?.vulns) && typeof repo.vulns.error !== 'string' ? repo.vulns : {}
  const pages = (key) => list(snapshot?.docs?.[key]).filter((p) => list(p?.repos).includes(name)).length
  const vulns = snapshot?.inventory?.scanned === false ? null
    : { total: Object.values(v).filter(num).reduce((a, b) => a + b, 0), high: num(v.high) ? v.high : 0 }
  return { coverage: cov, vulns,
    stale: pages('stale'), suspect: pages('suspect'), host: typeof repo?.sonar?.host === 'string' ? repo.sonar.host : '' }
}

export const filterSonar = (rows, { repo = '', source = '' } = {}) =>
  rows.filter((r) => (!repo || r.name === repo) && (!source || r.source === source))

export const sourceCounts = (rows) => ({ sonar: rows.filter((r) => r.source === 'sonar').length, estimated: rows.filter((r) => r.source === 'estimated').length })

// What a share (app.share.share, POST /api/sync/share) or a check for news
// (app.share.sync_status fetch) says, as a key and its vars for each app's own strings. An error
// git explained (projects.git_failure, plus no-token) gets its reason's sentence, with git's own
// line apart as the detail; anything else keeps its status sentence, as the wizard does.

const OK = ['pushed', 'up-to-date', 'nothing']
const REASONS = ['network', 'auth', 'no-token', 'denied', 'not-found']
const TOKEN = ['auth', 'no-token', 'denied']

export const shareOk = (r) => !!r && OK.includes(r.status)

// git@host:path, scheme://host/path; a local path names itself.
function hostOf(remote) {
  const ssh = /^[\w.+-]+@([^:/]+)[:/]/.exec(remote)
  if (ssh) return ssh[1]
  try { return new URL(remote).hostname || remote } catch { return remote }
}

function reasonSay(r, remote) {
  const host = r.host || hostOf(remote || '')
  return { key: `sy.err.${r.reason}`, vars: { host, url: remote || host }, detail: r.detail || '',
    token: TOKEN.includes(r.reason) && r.host ? r.host : '' }
}

export function shareSay(r, remote = '') {
  if (r?.status === 'error' && REASONS.includes(r.reason)) return reasonSay(r, remote)
  return { key: `sy.${statusKey(r)}`, vars: { detail: r?.detail || '' }, detail: '', token: '' }
}

// null when the check went well or did not run; an empty key when git failed for a reason it did not explain.
export function fetchSay(fetched, remote = '') {
  if (!fetched || fetched.ok) return null
  if (REASONS.includes(fetched.reason)) return reasonSay(fetched, remote)
  return { key: '', vars: {}, detail: fetched.detail || '', token: '' }
}

const n0 = (v) => v || 0

// `changes` (app.share.sync_status) leaves out the derived files the kit rewrites on every read; an older server sends
// only `pending`.
export function syncPrimary(s) {
  const behind = n0(s?.behind) > 0
  const mine = n0(s?.ahead) > 0 || (s?.changes ?? s?.pending ?? []).length > 0
  if (behind && mine) return 'share'
  if (behind) return 'pull'
  return mine ? 'push' : null
}

// A count of one has its own `.one` sentence.
const one = (key, n) => (n === 1 ? `${key}.one` : key)

function stepSay(prefix, r, remote, status = r?.status) {
  if (r?.status === 'error' && REASONS.includes(r.reason)) return reasonSay(r, remote)
  const key = `sy.${prefix}.${status}`
  return { key: status === 'pulled' ? one(key, r.commits) : key, vars: { n: r?.commits ?? 0, files: (r?.files || []).join(', '), detail: r?.detail || '' },
    detail: '', token: '' }
}

// A busy step by what holds the docs (a rebase or merge left half way: `git`; an autopilot run: `run`); anything
// else, a catch-up holding them included, is a plain wait.
const BUSY = { git: 'busyGit', run: 'busyRun' }
function statusKey(r) { return r?.status === 'busy' ? BUSY[r.detail] || 'busy' : r?.status }

// What a pull leaves the person: work in git for a terminal (a clash, changes kept in git's stash, a rebase or merge
// left half way), only a wait (an autopilot run holds the docs), or an error.
const TERMINAL = ['conflict', 'stashed', 'busyGit']
const pullTone = (key) => (TERMINAL.includes(key) ? 'warn' : key === 'busyRun' ? 'info' : 'error')

// When this machine was last level with the team (app.share.sync_status last_sync); an older server sends last_share.
export const lastSync = (s) => s?.last_sync ?? s?.last_share ?? null

export const pullSay = (r, remote = '') => {
  const key = statusKey(r)
  const said = { ...stepSay('pull', r, remote, key), tone: pullTone(key) }
  return TERMINAL.includes(key) ? { ...said, terminal: true } : said
}
export const pushSay = (r, remote = '') => stepSay('push', r, remote, statusKey(r))
export const pullOk = (r) => !!r && ['up-to-date', 'pulled', 'nothing'].includes(r.status)
export const pushOk = (r) => !!r && ['pushed', 'nothing'].includes(r.status)

// The Summary's line for the last catch-up (null: nothing to say). An error git explained reads as a share's does,
// with its token to save; any other (an internal one, a detached HEAD) keeps its own words as the detail.
export function catchUpSay(c, remote = '') {
  const p = c?.pull
  if (!c || c.status === 'busy' || !p) return null
  const key = statusKey(p)
  if (key === 'pulled') return { key: one('cu.pulled', p.commits), vars: { n: p.commits }, tone: 'info' }
  if (key === 'conflict') return { key: 'cu.conflict', vars: { files: (p.files || []).join(', ') }, tone: 'warn', terminal: true }
  if (key === 'stashed' || key === 'busyGit') return { key: `cu.${key}`, vars: {}, tone: 'warn', terminal: true }
  if (key === 'busyRun') return { key: 'cu.busyRun', vars: {}, tone: 'info' }
  if (key === 'error') return REASONS.includes(p.reason) ? { ...reasonSay(p, remote), tone: 'warn' } : { key: 'cu.unknown', vars: {}, tone: 'warn', detail: p.detail || '' }
  return null
}

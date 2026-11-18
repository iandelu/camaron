import { expect, test } from 'vitest'
import { catchUpSay, fetchSay, pullOk, pullSay, pushOk, pushSay, shareOk, shareSay, syncPrimary } from './share.js'

const REMOTE = 'https://gitlab-central.example.space/team/docs.git'
const fatal = "fatal: unable to access 'https://gitlab-central.example.space/team/docs.git/': Could not resolve host: gitlab-central.example.space"

test('a host that does not resolve says which one and to check the VPN, with git\'s line kept as the detail', () => {
  const r = { status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal }
  expect(shareSay(r, REMOTE)).toEqual({ key: 'sy.err.network', vars: { host: 'gitlab-central.example.space', url: REMOTE },
    detail: fatal, token: '' })
})

test('credentials refused or missing point at saving a token for that host', () => {
  for (const reason of ['auth', 'no-token', 'denied']) {
    const say = shareSay({ status: 'error', reason, host: 'git.acme', detail: 'fatal: x' }, REMOTE)
    expect(say.key).toBe(`sy.err.${reason}`)
    expect(say.token).toBe('git.acme')
  }
  expect(shareSay({ status: 'error', reason: 'not-found', host: 'git.acme', detail: '' }, REMOTE).token).toBe('')
})

test('a reason without a host (a local path, an older server) names the remote instead', () => {
  expect(shareSay({ status: 'error', reason: 'network', detail: '' }, REMOTE).vars.host).toBe('gitlab-central.example.space')
  expect(shareSay({ status: 'error', reason: 'network', detail: '' }, 'git@git.acme:team/docs.git').vars.host).toBe('git.acme')
  expect(shareSay({ status: 'error', reason: 'network', detail: '' }, '/mnt/share/docs').vars.host).toBe('/mnt/share/docs')
})

test('any other result keeps its status sentence, git\'s words inside it as before', () => {
  expect(shareSay({ status: 'pushed', detail: 'main' }, REMOTE)).toEqual({ key: 'sy.pushed', vars: { detail: 'main' }, detail: '', token: '' })
  expect(shareSay({ status: 'error', reason: 'unknown', detail: 'fatal: odd' }, REMOTE).key).toBe('sy.error')
  expect(shareSay({ status: 'error', detail: 'detached HEAD' }, REMOTE).vars.detail).toBe('detached HEAD')
  expect(shareSay({ status: 'conflict', detail: 'origin/main' }, REMOTE).key).toBe('sy.conflict')
})

test('only pushed, up to date and nothing are a success', () => {
  expect(['pushed', 'up-to-date', 'nothing'].every((status) => shareOk({ status }))).toBe(true)
  expect(['error', 'blocked', 'conflict', 'no-remote'].some((status) => shareOk({ status }))).toBe(false)
  expect(shareOk(null)).toBe(false)
})

test('a failed check for news reads like a failed share; a good one, or none, says nothing', () => {
  const fetched = { ok: false, reason: 'network', host: 'gitlab-central.example.space', detail: fatal }
  expect(fetchSay(fetched, REMOTE)).toEqual(shareSay({ status: 'error', ...fetched }, REMOTE))
  expect(fetchSay({ ok: false, reason: 'network' }, REMOTE).vars.host).toBe('gitlab-central.example.space')
  expect(fetchSay({ ok: false, reason: 'unknown', detail: 'fatal: odd' }, REMOTE)).toEqual({ key: '', vars: {}, detail: 'fatal: odd', token: '' })
  expect(fetchSay({ ok: true, reason: '' }, REMOTE)).toBeNull()
  expect(fetchSay(null, REMOTE)).toBeNull()
})

test('the useful action is the primary one', () => {
  expect(syncPrimary({ ahead: 0, behind: 3, pending: [] })).toBe('pull')
  expect(syncPrimary({ ahead: 1, behind: 0, pending: [] })).toBe('push')
  expect(syncPrimary({ ahead: 0, behind: 0, pending: ['docs/a.md'] })).toBe('push')
  expect(syncPrimary({ ahead: 1, behind: 2, pending: [] })).toBe('share')
  expect(syncPrimary({ ahead: null, behind: null, pending: [] })).toBe(null)
})

test('a pull names how many changes came in, or the files that clash', () => {
  expect(pullSay({ status: 'pulled', commits: 2, files: [] }).key).toBe('sy.pull.pulled')
  expect(pullSay({ status: 'pulled', commits: 2, files: [] }).vars.n).toBe(2)
  expect(pullSay({ status: 'conflict', commits: 0, files: ['docs/a.md', 'docs/b.md'] }).vars.files).toBe('docs/a.md, docs/b.md')
  expect(pullSay({ status: 'error', reason: 'network', host: 'git.acme', detail: 'fatal: x' }, 'https://git.acme/d.git').key).toBe('sy.err.network')
})

test('a push has its own keys and the same success rule shape', () => {
  expect(pushSay({ status: 'behind' }).key).toBe('sy.push.behind')
  expect(pushSay({ status: 'error', reason: 'auth', host: 'git.acme' }, REMOTE).token).toBe('git.acme')
  expect(['up-to-date', 'pulled', 'nothing'].every((status) => pullOk({ status }))).toBe(true)
  expect(['conflict', 'busy', 'error', 'no-remote'].some((status) => pullOk({ status }))).toBe(false)
  expect(['pushed', 'nothing'].every((status) => pushOk({ status }))).toBe(true)
  expect(['behind', 'blocked', 'error', 'no-remote'].some((status) => pushOk({ status }))).toBe(false)
  expect(pullOk(null) || pushOk(null)).toBe(false)
})

test('the summary speaks only when the catch-up brought something or failed', () => {
  expect(catchUpSay(null)).toBe(null)
  expect(catchUpSay({ status: 'busy', pull: null })).toBe(null)
  expect(catchUpSay({ status: 'done', pull: { status: 'up-to-date' } })).toBe(null)
  expect(catchUpSay({ status: 'done', pull: { status: 'pulled', commits: 4 } })).toEqual({ key: 'cu.pulled', vars: { n: 4 }, tone: 'info' })
  expect(catchUpSay({ status: 'done', pull: { status: 'conflict', files: ['docs/a.md'] } }).tone).toBe('warn')
  expect(catchUpSay({ status: 'done', pull: { status: 'error', reason: 'not-found' } }).key).toBe('sy.err.not-found')
})

test('changes the autostash kept are a warning with a terminal, after Traer and on open', () => {
  expect(pullSay({ status: 'stashed', commits: 2, files: ['docs/a.md'] }).key).toBe('sy.pull.stashed')
  expect(pullSay({ status: 'stashed', files: ['docs/a.md'] }).terminal).toBe(true)
  expect(pullOk({ status: 'stashed' })).toBe(false)
  expect(catchUpSay({ status: 'done', pull: { status: 'stashed', files: ['docs/a.md'] } }))
    .toEqual({ key: 'cu.stashed', vars: {}, tone: 'warn', terminal: true })
  expect(catchUpSay({ status: 'done', pull: { status: 'conflict', files: ['docs/a.md'] } }).terminal).toBe(true)
})

test('files the kit rewrites on its own never make uploading the primary', () => {
  expect(syncPrimary({ ahead: 0, behind: 0, pending: ['docs/.status.json'], changes: [] })).toBe(null)
  expect(syncPrimary({ ahead: 0, behind: 0, pending: ['docs/.status.json', 'docs/a.md'], changes: ['docs/a.md'] })).toBe('push')
  expect(syncPrimary({ ahead: 0, behind: 2, pending: ['docs/.status.json'], changes: [] })).toBe('pull')
})

test('a busy pull says what holds the docs: a rebase left half way wants a terminal, a run only waits', () => {
  expect(pullSay({ status: 'busy', detail: 'git' })).toMatchObject({ key: 'sy.pull.busyGit', terminal: true, tone: 'warn' })
  expect(pullSay({ status: 'busy', detail: 'run' })).toMatchObject({ key: 'sy.pull.busyRun', tone: 'info' })
  expect(pullSay({ status: 'busy', detail: 'run' }).terminal).toBeUndefined()
  expect(pullSay({ status: 'busy' }).key).toBe('sy.pull.busy')
  expect(pullSay({ status: 'conflict', files: [] }).tone).toBe('warn')
  expect(pullSay({ status: 'error', detail: 'boom' }).tone).toBe('error')
})

test('on open, each case the person must act on is worded; only an unexplained error falls back to offline', () => {
  const cu = (pull) => catchUpSay({ status: 'done', pull }, REMOTE)
  expect(cu({ status: 'busy', detail: 'git' })).toEqual({ key: 'cu.busyGit', vars: {}, tone: 'warn', terminal: true })
  expect(cu({ status: 'busy', detail: 'run' })).toEqual({ key: 'cu.busyRun', vars: {}, tone: 'info' })
  expect(cu({ status: 'error', reason: 'network', host: 'git.acme', detail: 'fatal: x' }))
    .toMatchObject({ key: 'sy.err.network', vars: { host: 'git.acme', url: REMOTE }, tone: 'warn', detail: 'fatal: x' })
  expect(cu({ status: 'error', reason: 'network', detail: '' }).vars.host).toBe('gitlab-central.example.space')
  expect(cu({ status: 'error', reason: 'no-token', host: 'git.acme', detail: '' }).token).toBe('git.acme')
  expect(cu({ status: 'error', reason: 'unknown', detail: 'fatal: odd' })).toEqual({ key: 'cu.offline', vars: {}, tone: 'warn' })
  expect(cu({ status: 'error', detail: 'boom' }).key).toBe('cu.offline')
})

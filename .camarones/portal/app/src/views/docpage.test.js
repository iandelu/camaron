import { expect, test } from 'vitest'
import { newPagePath, pageBanners, pageConflict, pageLede, pager } from './docpage.js'

const d = (over = {}) => ({ exists: true, trust: 'confirmed', fresh: 'fresh', ...over })

test('a confirmed, fresh page in English has no banner', () => {
  expect(pageBanners(d(), {}, '')).toEqual([])
})

test('a translation that is missing or older than the English page says so', () => {
  expect(pageBanners(d({ exists: false }), {}, 'es')).toEqual([{ tone: 'info', key: 'noTranslation' }])
  expect(pageBanners(d(), { i18n: { es: 'outdated' } }, 'es')).toEqual([{ tone: 'warn', key: 'outdatedTranslation' }])
  expect(pageBanners(d(), { i18n: { es: 'current' } }, 'es')).toEqual([])
})

test('trust and freshness banners, the cited files of a stale page included', () => {
  expect(pageBanners(d({ trust: 'needs-reconfirm' }), {}, '')).toEqual([{ tone: 'info', key: 'banner.needs-reconfirm' }])
  expect(pageBanners(d({ fresh: 'stale', freshness: { missing: ['a.java'], changed: ['b.java'] } }), {}, ''))
    .toEqual([{ tone: 'warn', key: 'banner.stale', code: 'a.java, b.java' }])
  expect(pageBanners(d({ trust: 'draft' }), {}, '')).toEqual([{ tone: 'warn', key: 'banner.draft', draft: true }])
  expect(pageBanners(d({ trust: 'draft' }), { space: 'notes' }, '')).toEqual([])     // working notes are drafts by nature
})

test('a page covered by an accepted ADR says so, pending implementation when new', () => {
  const decisions = [{ id: '0012', title: '0012 — Sessions', path: 'decisions/0012-sessions.md', kind: 'new', implementation: 'pending' },
    { id: '0003', title: '0003 — JPA', path: 'decisions/0003-jpa.md', kind: 'retro', implementation: 'n/a' }]
  expect(pageBanners(d({ decisions }), { space: 'docs' }, '').map((b) => b.key)).toEqual(['banner.adrPending', 'banner.adr'])
  expect(pageBanners(d({ decisions }), {}, '')[0]).toEqual({ tone: 'info', key: 'banner.adrPending',
    adr: { id: '0012', title: '0012 — Sessions', path: 'decisions/0012-sessions.md' } })
})

test('a new decision already implemented, or a page with no decisions, carries no pending banner', () => {
  const done = { id: '0012', title: 'T', path: 'decisions/0012-t.md', kind: 'new', implementation: 'done' }
  expect(pageBanners(d({ decisions: [done] }), {}, '').map((b) => b.key)).toEqual(['banner.adr'])
  expect(pageBanners(d({ decisions: [] }), {}, '')).toEqual([])
  expect(pageBanners(d({ decisions: undefined }), {}, '')).toEqual([])
})

test('the decision banners come after the translation, trust and freshness ones', () => {
  const decisions = [{ id: '0012', title: 'T', path: 'decisions/0012-t.md', kind: 'new', implementation: 'pending' }]
  expect(pageBanners(d({ trust: 'draft', decisions }), {}, '').map((b) => b.key)).toEqual(['banner.draft', 'banner.adrPending'])
})

test('the pager follows the reading order; a page outside it has none', () => {
  expect(pager(['a', 'b', 'c'], 'b')).toEqual({ prev: 'a', next: 'c' })
  expect(pager(['a', 'b'], 'a')).toEqual({ prev: null, next: 'b' })
  expect(pager(['a'], 'z')).toBeNull()
})

test('a new page goes under guides/ with a slug of its title', () => {
  expect(newPagePath('How to deploy (prod)')).toBe('guides/how-to-deploy-prod.md')
  expect(newPagePath('')).toBe('guides/.md')
})

test("the lede is the description of the page as read, the translation's in Spanish", () => {
  const row = { description: 'How an order is placed.' }        // the docs index: the English page's front matter
  expect(pageLede({ description: 'Cómo se hace un pedido.' }, row)).toBe('Cómo se hace un pedido.')
  expect(pageLede({}, row)).toBe('How an order is placed.')                // a payload without one keeps the index's
  expect(pageLede({}, {})).toBe('')
})

test('a save or confirm refused because the page changed gives the version it has now; anything else gives null', () => {
  const refused = (status, data) => Object.assign(new Error('x'), { status, data })
  expect(pageConflict(refused(409, { error: 'changed', sha: 'abc' }))).toBe('abc')
  expect(pageConflict(refused(409, { error: 'changed', body_sha: 'def' }), 'body_sha')).toBe('def')
  expect(pageConflict(refused(409, { error: 'changed', body_sha: 'def' }))).toBe(null)       // not the field asked for
  expect(pageConflict(refused(409, { error: 'another change is being saved: try again' }))).toBe(null)   // busy
  expect(pageConflict(refused(400, { sha: 'abc' }))).toBe(null)
  expect(pageConflict(new Error('offline'))).toBe(null)
})

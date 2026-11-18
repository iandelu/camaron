import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test, vi } from 'vitest'
import { DocsHealth, chipIcon, scrollToStale, showStale } from './DocsHealth.jsx'
import { DocsIcon } from './DocsIcons.jsx'
import { STALE_WIKIS, docsHealth } from '../docs.js'
import { setLang, t } from '../i18n.js'

const chip = (key, tone, n = null) => ({ key, tone, n, text: `docs.h.${key}` })
const draw = (props) => renderToStaticMarkup(<DocsHealth chips={[]} loading={false} {...props} />)

afterEach(() => { delete globalThis.document; setLang('es') })

// Every chip key docsHealth can emit, from inputs that reach all of its branches.
const full = { summary: { draft: 1, 'needs-reconfirm': 1, orphans: 1, untranslated: 1 }, feedback: 1 }
const wikis = [{ pages: 0 }, { pages: 1, old: true }, { pages: 1, stale: true }, { pages: 1 }]
const c4s = [{ exists: false, model: false }, { exists: false, model: true }, { exists: true, stale: true, model: true },
  { exists: true, stale: false, model: true }]
const emitted = [...new Set([docsHealth(full, wikis, null), ...c4s.map((c4) => docsHealth({}, null, { c4 })), []].flat().map((x) => x.key))]

test('the keys the test reaches are all of docsHealth\'s', () => {
  expect(emitted.sort()).toEqual(['c4Fresh', 'c4NoModel', 'c4None', 'c4Stale', 'drafts', 'feedback', 'orphans', 'reconfirm', 'untranslated',
    'wikiFresh', 'wikiNone', 'wikiOld', 'wikiStale'])
})

test.each(emitted)('%s has an icon and a text in both languages', (key) => {
  expect(renderToStaticMarkup(<DocsIcon name={chipIcon(key)} />), key).toContain('<svg')
  for (const lang of ['es', 'en']) {
    setLang(lang)
    const text = t(`docs.h.${key}`, { n: 7 })
    expect(text, `${lang}.${key}`).not.toBe(`docs.h.${key}`)
    expect(text).not.toContain('{n}')
    if (!key.startsWith('c4')) expect(text, `${lang}.${key} carries its figure`).toContain('7')
  }
})

test('each chip shows its icon, its text with its figure and its tone', () => {
  const out = draw({ chips: [chip('drafts', 'warn', 2), chip('wikiFresh', 'ok', 3), chip('feedback', 'info', 5), chip('c4Fresh', 'ok')] })
  expect(out).toContain('Borradores: 2')
  expect(out).toContain('Wikis al día: 3')
  expect(out).toContain('Comentarios pendientes: 5')
  expect(out).toContain('C4: al día')
  expect(out).toMatch(/class="dk-hchip is-warn"[^>]*>(<svg[^>]*>.*?<\/svg>)Borradores: 2</)
  expect(out).toMatch(/class="dk-hchip is-ok"[^>]*>(<svg[^>]*>.*?<\/svg>)Wikis al día: 3</)
  expect(out).toMatch(/class="dk-hchip is-info"[^>]*>(<svg[^>]*>.*?<\/svg>)Comentarios pendientes: 5</)
  expect(out.match(/<svg/g)).toHaveLength(4)
})

test('the strip is a status region the tour can point at, named in the app\'s language', () => {
  const out = draw({ chips: [chip('drafts', 'warn', 2)] })
  expect(out).toMatch(/<div[^>]*role="status"/)
  expect(out).toContain('data-tour="docs-health"')
  expect(out).toContain('aria-label="Estado de la documentación"')
  setLang('en')
  const en = draw({ chips: [chip('drafts', 'warn', 2)] })
  expect(en).toContain('Drafts: 2')
  expect(en).toContain('aria-label="Documentation status"')
})

test('while the wikis load the strip is a skeleton and has no chips', () => {
  const out = draw({ chips: [chip('drafts', 'warn', 2)], loading: true })
  expect(out).toContain('cu-skel')
  expect(out).not.toContain('dk-hchip')
  expect(out).not.toContain('Borradores')
  expect(out).toContain('role="status"')
  expect(out).toContain('data-tour="docs-health"')
})

test('with nothing to report it says so instead of an empty strip', () => {
  const out = draw({ chips: [] })
  expect(out).toContain('Nada que contar todavía')
  expect(out).not.toContain('dk-hchip')
  expect(out).not.toContain('cu-skel')
  setLang('en')
  expect(draw({ chips: [] })).toContain('Nothing to count yet')
})

// Only the stale-wikis chip points at a thing, so only it is a button.
test('the stale-wikis chip is a button; the others are plain text', () => {
  const out = draw({ chips: [chip('wikiStale', 'warn', 2), chip('wikiOld', 'warn', 1), chip('drafts', 'warn', 4)] })
  expect(out.match(/<button/g)).toHaveLength(1)
  expect(out).toMatch(/<button type="button" class="dk-hchip is-warn"[^>]*>(<svg[^>]*>.*?<\/svg>)Wikis desfasadas: 2<\/button>/)
  expect(out).toMatch(/<span class="dk-hchip is-warn">(<svg[^>]*>.*?<\/svg>)Wikis con alcance anterior: 1<\/span>/)
  expect(out).toMatch(/<span class="dk-hchip is-warn">(<svg[^>]*>.*?<\/svg>)Borradores: 4<\/span>/)
})

test('the stale chip scrolls to the first stale card when the page has one, and stays on the page', () => {
  const scrollIntoView = vi.fn()
  const querySelector = vi.fn(() => ({ scrollIntoView }))
  globalThis.document = { querySelector }
  const go = vi.fn()
  showStale(go)
  expect(querySelector).toHaveBeenCalledWith('[data-wiki-state="stale"]')
  expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' })
  expect(go).not.toHaveBeenCalled()
})

// The cards are on the Wikis tab, not on Read where the header is: with none in the page the chip opens that tab, asking for it.
test('with no stale card in the page the chip opens the Wikis tab asking for the first one', () => {
  globalThis.document = { querySelector: () => null }
  const go = vi.fn()
  expect(() => showStale(go)).not.toThrow()
  expect(go).toHaveBeenCalledWith(STALE_WIKIS)
})

test('a stale card that cannot scroll is still found, and nothing throws', () => {
  globalThis.document = { querySelector: () => ({}) }
  const go = vi.fn()
  expect(scrollToStale()).toBe(true)
  expect(() => showStale(go)).not.toThrow()
  expect(go).not.toHaveBeenCalled()
  globalThis.document = { querySelector: () => null }
  expect(scrollToStale()).toBe(false)
})

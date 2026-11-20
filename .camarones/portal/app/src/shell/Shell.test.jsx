import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import Shell, { Summary } from './Shell.jsx'

// WCAG 2.4.1: the portal starts with a link past the header and the sidebar to its main landmark, which can take the
// focus (the link moves it there itself: the hash is the router's).
test('the portal skips to its content', () => {
  const out = renderToStaticMarkup(<Shell />)
  expect(out).toMatch(/^<a class="cu-skip" href="#native">[^<]+<\/a><header class="top">/)
  expect(out).toContain('<main id="native" class="main native" tabindex="-1">')
})

// The header's trust counts: words with their number (one / many), a link to Review for what waits, no green zero.
test('the header counts trust in words and leads to Review', () => {
  const words = { 'trustN.draft.many': '{n} borradores', 'trustN.needs-reconfirm.one': '{n} por reconfirmar',
    'trustN.confirmed.one': '{n} confirmada' }
  const t = (k, v) => (words[k] || k).replace('{n}', v?.n)
  const out = renderToStaticMarkup(<Summary s={{ confirmed: 0, draft: 65, 'needs-reconfirm': 1 }} feedback={0} t={t} />)
  expect(out).not.toContain('confirmada')
  expect(out).toContain('<a class="cu-trust cu-trust--draft" href="#/review">65 borradores</a>')
  expect(out).toContain('<a class="cu-trust cu-trust--needs-reconfirm" href="#/review">1 por reconfirmar</a>')
  expect(renderToStaticMarkup(<Summary s={{ confirmed: 1 }} feedback={0} t={t} />))
    .toContain('<span class="cu-trust cu-trust--confirmed">1 confirmada</span>')
})

import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Failed, JobChip, Page, PlaceContext } from './parts.jsx'
import { Place } from './Place.jsx'
import { setLang } from './i18n.js'

// A read that failed says what, shows the server's own message and offers to try again: never a dead end.
test('a failed read is an alert with the server message and a retry', () => {
  setLang('es')
  const out = renderToStaticMarkup(<Failed title="No he podido leer el plan" detail="HTTP 500: boom" onRetry={() => {}} />)
  expect(out).toMatch(/^<div class="cu-aviso cu-aviso--error" role="alert">/)
  expect(out).toContain('<code class="cu-aviso-detail">HTTP 500: boom</code>')
  expect(out).toContain('>Reintentar</button>')
})

test('without a retry, no button', () => {
  expect(renderToStaticMarkup(<Failed title="x" detail="y" />)).not.toContain('<button')
})

test('a full page says so in its class; a plain one does not', () => {
  expect(renderToStaticMarkup(<Page title="Tablero" full />)).toMatch(/^<div class="dk-page full">/)
  expect(renderToStaticMarkup(<Page title="Plan" />)).toMatch(/^<div class="dk-page">/)
})

// A running job shimmers like the AI thinking (ui.css .cu-thinking): something is at work, not stuck. Once it ends
// its state is a plain word.
test('a running job says so with the thinking shimmer; a finished one is a plain word', () => {
  setLang('es')
  const html = (node) => renderToStaticMarkup(node)
  expect(html(<JobChip job={{ status: 'running' }} />)).toContain('<span class="cu-thinking">En curso</span>')
  const done = html(<JobChip job={{ status: 'done' }} />)
  expect(done).not.toContain('cu-thinking')
  expect(done).toContain('Hecho')
  expect(html(<JobChip job={{ status: 'failed', stopped: true }} />)).toContain('Parado')
})

// A page whose header carries its actions (Decisiones: Candidatas, Nuevo ADR) sets them beside the title.
test('a page with actions sets them beside its title; one without keeps the bare title', () => {
  const out = renderToStaticMarkup(<Page title="Decisiones" actions={<button type="button">Nuevo</button>} />)
  expect(out).toMatch(/^<div class="dk-page"><div class="dk-page-head"><h1 class="t-impact">Decisiones<\/h1><div class="row dk-page-acts"><button/)
  expect(renderToStaticMarkup(<Page title="Plan" />)).toBe('<div class="dk-page"><h1 class="t-impact">Plan</h1></div>')
})

// Inside a place the place owns the h1 and the width: a page's own title is a heading under the tabs with its actions
// beside it (an ADR's number and title, Present), unless it only repeats the place's name or the tab's (Plan, Decisiones).
test('inside a place a page titles itself under the tabs, beside its actions, unless the place already says it', () => {
  setLang('es')
  const inPlace = (node) => renderToStaticMarkup(<Place section="docs" view="decisions">{node}</Place>)
  const out = inPlace(<Page title="0012 · Sesiones" wide actions={<b>act</b>}><p>body</p></Page>)
  expect(out.match(/<h1/g)).toHaveLength(1)
  expect(out).toContain('<div class="dk-page-head"><h2 class="dk-page-h">0012 · Sesiones</h2><div class="row dk-page-acts"><b>act</b></div></div><p>body</p>')
  expect(out).toMatch(/^<div class="dk-page">/)                 // the place's width, not the page's
  for (const said of ['Decisiones', 'Docs']) expect(inPlace(<Page title={said}><p>body</p></Page>)).not.toContain('<h2')
  expect(inPlace(<Page title="Docs" actions={<b>act</b>} />)).toContain('<div class="dk-page-head"><div class="row dk-page-acts"><b>act</b>')
  const bare = renderToStaticMarkup(<PlaceContext.Provider value={['Docs']}><Page title="Nuevo ADR"><p>body</p></Page></PlaceContext.Provider>)
  expect(bare).toBe('<div class="dk-page-head"><h2 class="dk-page-h">Nuevo ADR</h2></div><p>body</p>')
  expect(renderToStaticMarkup(<Page title="X" />)).toContain('<h1 class="t-impact">X</h1>')
})

test('a place sets title, head, tabs and body in order', () => {
  setLang('es')
  const out = renderToStaticMarkup(<Place section="docs" view="wikis" head={<i>strip</i>}>c</Place>)
  const at = ['<h1', '<i>strip</i>', 'nav class="dk-guide-tabs"', 'href="#/docs"', 'href="#/docs/wikis"', 'href="#/docs/decisions"', 'href="#/docs/interviews"', '>c<']
    .map((x) => out.indexOf(x))
  expect(at.every((n) => n >= 0)).toBe(true)
  expect([...at].sort((a, b) => a - b)).toEqual(at)
  expect(out).toMatch(/href="#\/docs\/wikis"[^>]*aria-current="page"|aria-current="page"[^>]*href="#\/docs\/wikis"/)
  expect(out).toContain('data-tour="tabs-docs"')
  expect(renderToStaticMarkup(<Place section="settings" view="general" badges={{ trust: 2 }}>c</Place>)).toContain('Confianza · 2')
})

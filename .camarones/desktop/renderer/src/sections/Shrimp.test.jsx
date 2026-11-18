import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Shrimp } from './Shrimp.jsx'

const favicon = readFileSync(new URL('../../../../portal/app/public/favicon.svg', import.meta.url), 'utf-8')
const draw = (state) => renderToStaticMarkup(<Shrimp state={state} />)
const dots = (out) => out.match(/<i\b/g) ?? []

test.each(['idle', 'thinking', 'answering'])('%s is one svg with its state as a class, hidden from readers', (state) => {
  const out = draw(state)
  expect(out.match(/<svg/g)).toHaveLength(1)
  expect(out).toContain(`class="dk-shrimp ${state}"`)
  expect(out).toContain('viewBox="0 0 64 64"')
  expect(out).toContain('aria-hidden="true"')
})

test('only thinking has the three dots', () => {
  expect(dots(draw('thinking'))).toHaveLength(3)
  expect(dots(draw('idle'))).toHaveLength(0)
  expect(dots(draw('answering'))).toHaveLength(0)
})

test.each([undefined, null, '', 'sleeping', 'Thinking'])('%j is drawn as idle', (state) => {
  const out = draw(state)
  expect(out).toContain('class="dk-shrimp idle"')
  expect(dots(out)).toHaveLength(0)
})

test('the svg carries the favicon\'s own path data and the classes the motion moves', () => {
  const out = draw('idle')
  for (const [, d] of favicon.matchAll(/\sd="([^"]*)"/g)) expect(out).toContain(`d="${d}"`)
  for (const name of ['shrimp-antennae', 'shrimp-tail', 'shrimp-eye']) expect(out).toContain(`class="${name}"`)
  expect(out).not.toMatch(/<rect|#ff8a5b|#0a0a0a/i)
})

test('it is a picture: no text for a reader, none of its own', () => {
  for (const state of ['idle', 'thinking', 'answering']) expect(draw(state).replace(/<[^>]*>/g, '').trim()).toBe('')
})

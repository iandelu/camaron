import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Flow from './sections/Flow.jsx'
import { setLang } from './i18n.js'

afterEach(() => { setLang('es'); delete globalThis.location })

const never = () => new Promise(() => {})
const props = { srv: { get: never, post: never }, jobs: { subscribe: () => () => {}, get: () => ({ running: [], done: [] }) }, app: {}, index: null, sections: {} }

const render = (hash) => { globalThis.location = { hash }; return renderToStaticMarkup(<Flow {...props} />) }
const current = (out) => [...out.matchAll(/<a [^>]*aria-current="page"[^>]*>([^<]*)<\/a>/g)].map((m) => m[1])

test('the Flow place opens on the Summary under one title', () => {
  const out = render('#/flow')
  expect(out.match(/<h1/g)).toHaveLength(1)
  expect(out).toMatch(/<h1[^>]*>Flujo<\/h1>/)
  expect(current(out)).toEqual(['Resumen'])
})

test('the Plan view marks the Plan tab', () => {
  const out = render('#/flow/plan')
  expect(out.match(/<h1/g)).toHaveLength(1)
  expect(current(out)).toEqual(['Plan'])
})

import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Flow from './sections/Flow.jsx'
import { S, setLang } from './i18n.js'

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

// Summary and Plan are titled by their tab: inside the place their own title is not said twice.
test('neither view repeats its tab as a heading', () => {
  for (const hash of ['#/flow', '#/flow/plan']) expect(render(hash), hash).not.toContain('dk-page-h')
})

// The repo page is a view of Flow that draws no place: a way back and the bento, no Flujo title, no tabs.
test('the repo page draws no place shell, and a skeleton while it reads', () => {
  const out = render('#/flow/repo/api')
  expect(out).not.toMatch(/<nav class="dk-guide-tabs"/)
  expect(out).not.toMatch(/<h1[^>]*>Flujo<\/h1>/)
  expect(out).toContain('cu-skel')
})

test('a repo page whose name is not a plain name says the repo is unknown and asks the server nothing', () => {
  const asked = []
  globalThis.location = { hash: '#/flow/repo/..%2Fx' }
  const srv = { get: (...a) => { asked.push(a); return never() }, post: never }
  const out = renderToStaticMarkup(<Flow {...props} srv={srv} />)
  expect(out).toContain(S.es['rp.unknown'])
  expect(out).toMatch(/href="#\/flow"/)
  expect(asked).toEqual([])
})

import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test, vi } from 'vitest'
import { DocsMisses, MissesList } from './DocsMisses.jsx'
import { setLang } from '../i18n.js'

afterEach(() => setLang('es'))

const misses = [{ q: 'how are refunds made', n: 3, last: '2026-11-17' }, { q: 'who owns billing', n: 1, last: '2026-11-16' }]
const draw = (props) => renderToStaticMarkup(<MissesList misses={misses} busy="" error="" onAct={() => {}} {...props} />)

// Effects do not run in static markup: this is the card before its read lands, which is also what a failed read or no
// misses leave on screen (the list is then null or empty).
test('the card says nothing until there are misses', () => {
  expect(renderToStaticMarkup(<DocsMisses srv={{ get: vi.fn(), post: vi.fn() }} />)).toBe('')
})

test('each question shows with how many times it was asked and its two actions', () => {
  const out = draw()
  expect(out).toContain('how are refunds made')
  expect(out).toContain('who owns billing')
  expect(out).toContain('×3')
  expect(out).toContain('×1')
  expect(out).toContain('Preguntas sin respuesta')
  expect(out.match(/<li\b/g)).toHaveLength(2)
  expect(out.match(/<button\b/g)).toHaveLength(4)
  expect(out).toContain('aria-label="Añadir a preguntas abiertas: how are refunds made"')
  expect(out).toContain('aria-label="Descartar: how are refunds made"')
  expect(out).toContain('aria-label="Añadir a preguntas abiertas: who owns billing"')
  expect(out).toContain('aria-label="Descartar: who owns billing"')
  expect(out).not.toContain('disabled')
  expect(out).not.toContain('role="alert"')
})

test('it is worded in the app\'s language', () => {
  setLang('en')
  const out = draw()
  expect(out).toContain('Unanswered questions')
  expect(out).toContain('aria-label="Add to open questions: who owns billing"')
  expect(out).toContain('aria-label="Dismiss: who owns billing"')
})

test('a question is text, never markup', () => {
  const out = draw({ misses: [{ q: '<img src=x onerror=alert(1)> & more', n: 2, last: '2026-11-17' }] })
  expect(out).toContain('&lt;img src=x onerror=alert(1)&gt; &amp; more')
  expect(out).not.toContain('<img')
})

// Each answer is the whole list, so two actions at once could land out of order: while one runs, no row's buttons answer.
test('while an action runs the buttons are closed and its row says it is busy', () => {
  const out = draw({ busy: 'who owns billing' })
  expect(out.match(/<button\b[^>]*\bdisabled=""/g)).toHaveLength(4)
  expect(out.match(/aria-busy="true"/g)).toHaveLength(1)
  expect(out).toMatch(/<li\b[^>]*aria-busy="true"[^>]*>.*who owns billing/)
})

test('a rejection is shown as the server said it, as an alert', () => {
  const out = draw({ error: 'No he podido hacerlo: not in the list: who owns billing' })
  expect(out).toMatch(/role="alert"[^>]*>.*not in the list: who owns billing/)
})

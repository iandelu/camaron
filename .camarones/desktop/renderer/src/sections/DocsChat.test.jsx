import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { AskEntry, ChatPanel, DocsChat, canSend, chatKey, chatScroll, revealer } from './DocsChat.jsx'
import { S, setLang } from '../i18n.js'

afterEach(() => setLang('es'))

// What GET app/chat/models gives (lib/chat.py models()): a runner whose CLI decides the model has one entry with id ''.
const RUNNERS = [
  { runner: 'claude', label: 'Claude Code', models: [{ id: 'haiku', label: 'haiku', local: false }, { id: 'sonnet', label: 'sonnet', local: false }] },
  { runner: 'opencode', label: 'OpenCode', models: [{ id: 'ollama/llama3:8b', label: 'ollama/llama3:8b', local: true }] },
  { runner: 'gemini', label: 'Gemini', models: [{ id: '', label: 'default', local: false }] },
]
const BASE = { messages: [], running: false, runners: RUNNERS, choice: { runner: 'claude', model: 'haiku' }, ai: true, loadError: '' }
const noop = () => {}
const panel = (over = {}, props = {}) => renderToStaticMarkup(<ChatPanel state={{ ...BASE, ...over }} reveal={null} onSend={noop} onPick={noop}
  onClear={noop} onClose={noop} onOpen={noop} onSkip={noop} onRetry={noop} {...props} />)
const select = (out) => out.match(/<select[^>]*>.*?<\/select>/)?.[0] ?? ''
const field = (out) => out.match(/<textarea[^>]*>/)[0]
const status = (out) => out.match(/<span[^>]*role="status"[^>]*>(.*?)<\/span>/)[1]
const ask = { id: 1, role: 'user', text: 'How does auth work?' }
const reply = (result, over = {}) => ({ id: 2, role: 'assistant', text: result?.answer || '', result, ...over })
const JWT = { answer: 'It uses JWT.', cited: ['architecture/overview.md#Context'], runner: 'claude', model: 'haiku', seconds: 3 }

test('the picker is one select: a group per agent, an option per model, the value runner|model', () => {
  const out = select(panel())
  expect(out.match(/<select/g)).toHaveLength(1)
  expect(out.match(/<optgroup label="([^"]*)"/g).map((g) => g.match(/label="([^"]*)"/)[1])).toEqual(['Claude Code', 'OpenCode', 'Gemini'])
  expect([...out.matchAll(/<option value="([^"]*)"/g)].map((m) => m[1])).toEqual(['claude|haiku', 'claude|sonnet', 'opencode|ollama/llama3:8b', 'gemini|'])
  expect(out).toMatch(/aria-label="Agente y modelo"/)
})

test('a local model says so and the CLI\'s own default is worded in the app\'s language', () => {
  expect(select(panel())).toContain('>OpenCode · ollama/llama3:8b (local)</option>')
  expect(select(panel())).toContain('>Gemini · por defecto</option>')
  expect(select(panel())).not.toMatch(/default</)
  setLang('en')
  expect(select(panel())).toContain('>Gemini · default</option>')
  expect(select(panel())).toMatch(/aria-label="Agent and model"/)
})

// A closed select shows only its option's text, never the group's label: each option names its agent as well as its model.
test('every option names its agent and its model', () => {
  const texts = (out) => [...select(out).matchAll(/<option[^>]*>([^<]*)<\/option>/g)].map((m) => m[1])
  expect(texts(panel())).toEqual(['Claude Code · haiku', 'Claude Code · sonnet', 'OpenCode · ollama/llama3:8b (local)', 'Gemini · por defecto'])
  setLang('en')
  expect(texts(panel())).toEqual(['Claude Code · haiku', 'Claude Code · sonnet', 'OpenCode · ollama/llama3:8b (local)', 'Gemini · default'])
})

// lib/chat.py words a configured default (Codex's model, a command runner's model in prefs) as label "default" with its id.
test('a default entry with a model names it, in the app\'s language', () => {
  const codex = [{ runner: 'codex', label: 'Codex', models: [{ id: 'gpt-5.6-terra', label: 'default', local: false }] }]
  const out = select(panel({ runners: codex, choice: { runner: 'codex', model: 'gpt-5.6-terra' } }))
  expect(out).toContain('<option value="codex|gpt-5.6-terra" selected="">Codex · por defecto (gpt-5.6-terra)</option>')
  expect(out).not.toMatch(/default/)
  setLang('en')
  expect(select(panel({ runners: codex, choice: { runner: 'codex', model: 'gpt-5.6-terra' } }))).toContain('>Codex · default (gpt-5.6-terra)</option>')
})

test('two agents that both have a default entry read apart, and the chosen one is named', () => {
  const two = [{ runner: 'fake', label: 'Fake', models: [{ id: '', label: 'default', local: false }] },
    { runner: 'broken', label: 'Broken', models: [{ id: '', label: 'default', local: false }] }]
  const chosen = (runner) => select(panel({ runners: two, choice: { runner, model: '' } })).match(/<option [^>]*selected=""[^>]*>([^<]*)</)[1]
  expect(chosen('fake')).toBe('Fake · por defecto')
  expect(chosen('broken')).toBe('Broken · por defecto')
  setLang('en')
  expect(chosen('broken')).toBe('Broken · default')
})

test('the option shown is the store\'s choice', () => {
  const picked = (out) => select(out).match(/<option value="([^"]*)" selected=""/)[1]
  expect(picked(panel())).toBe('claude|haiku')
  expect(picked(panel({ choice: { runner: 'opencode', model: 'ollama/llama3:8b' } }))).toBe('opencode|ollama/llama3:8b')
  expect(picked(panel({ choice: { runner: 'gemini', model: '' } }))).toBe('gemini|')
})

test('ready: the composer is open, labelled and empty; the shrimp is idle and says nothing', () => {
  const out = panel()
  expect(field(out)).toMatch(/aria-label="Escribe tu pregunta"/)
  expect(field(out)).not.toMatch(/disabled|readonly|aria-disabled/i)
  expect(out).toContain('class="dk-shrimp idle"')
  expect(status(out)).toBe('')
  expect(out).toMatch(/<button[^>]*type="submit"[^>]*>Enviar<\/button>/)
  expect(out).not.toContain('cu-btn--primary')
})

test('the conversation is a polite live region, and with no message yet it says what the chat answers from', () => {
  const out = panel()
  expect(out).toMatch(/<div[^>]*class="dk-chat-list"[^>]*aria-live="polite"/)
  expect(out).toMatch(/aria-label="Conversación"/)
  expect(out).toContain('Responde solo con lo que dice la documentación')
  expect(out).toMatch(/<aside[^>]*aria-label="Preguntar con IA"/)
  setLang('en')
  expect(panel()).toMatch(/aria-label="Conversation"/)
  expect(field(panel())).toMatch(/aria-label="Type your question"/)
})

test('the header has Clear and Close; Clear is closed with nothing to clear', () => {
  const clear = (out) => out.match(/<button[^>]*>Vaciar<\/button>/)[0]
  expect(clear(panel())).toContain('disabled')
  expect(clear(panel({ messages: [ask] }))).not.toContain('disabled')
  expect(clear(panel({ messages: [ask], running: true }))).not.toContain('disabled')
  expect(panel()).toMatch(/<button[^>]*>Cerrar<\/button>/)
  setLang('en')
  expect(panel()).toMatch(/>Clear<\/button>/)
  expect(panel()).toMatch(/>Close<\/button>/)
})

test('no agent on this machine: the way out is Machine, the composer is closed, there is no picker', () => {
  const out = panel({ runners: [], choice: null })
  expect(out).toContain('No hay ningún agente instalado en esta máquina que pueda responder.')
  expect(out).toMatch(/<a [^>]*href="#\/machine"[^>]*>Prepararla en Máquina<\/a>/)
  expect(field(out)).toContain('disabled')
  expect(select(out)).toBe('')
  setLang('en')
  expect(panel({ runners: [], choice: null })).toContain('No agent that can answer is installed on this machine.')
})

test('ask.ai off: the existing sentence, the composer closed, and the picker shown but off', () => {
  const out = panel({ ai: false })
  expect(out).toContain('Aquí no hay IA para responder')
  expect(field(out)).toContain('disabled')
  expect(select(out)).toMatch(/^<select[^>]*disabled=""/)
  expect(select(panel())).not.toMatch(/^<select[^>]*disabled/)
})

// The chat answers on the picker's model, not on ask.model: the timeout's advice points at the picker.
test('a turn that timed out points at the picker, not at workspace.yaml', () => {
  const slow = (lang) => { setLang(lang); return panel({ messages: [ask, reply(undefined, { error: 'no answer within 90 s: claude is slow' })] }) }
  expect(slow('es')).toContain('La IA no ha respondido a tiempo (90 s). Reintenta, o elige arriba un modelo más rápido.')
  expect(slow('en')).toContain('The AI did not answer in time (90 s). Try again, or pick a faster model above.')
  for (const lang of ['es', 'en']) expect(slow(lang)).not.toMatch(/ask\.model|workspace\.yaml/)
})

test('without a choice the composer stays closed', () => {
  expect(field(panel({ choice: null }))).toContain('disabled')
})

test('a failed read of the models with models kept: a warning with Retry, and the picker still works', () => {
  const out = panel({ loadError: 'Failed to fetch' })
  expect(out).toContain('No he podido leer los agentes de esta máquina.')
  expect(out).toMatch(/>Reintentar<\/button>/)
  expect(select(out)).not.toBe('')
  expect(field(out)).not.toContain('disabled')
  expect(out).not.toContain('No hay ningún agente instalado')
  expect(out).not.toContain('Failed to fetch')
  setLang('en')
  expect(panel({ loadError: 'boom' })).toContain('I could not read the agents on this machine.')
})

// Unread is not "none installed": with nothing read, saying no agent is installed would contradict the warning above it.
test('a failed read with no models: only the warning with Retry, not the no-agent way out', () => {
  const out = panel({ runners: [], choice: null, loadError: 'Failed to fetch' })
  expect(out).toContain('No he podido leer los agentes de esta máquina.')
  expect(out).toMatch(/>Reintentar<\/button>/)
  expect(out).not.toContain('No hay ningún agente instalado')
  expect(out).not.toMatch(/href="#\/machine"/)
  expect(field(out)).toContain('disabled')
  setLang('en')
  expect(panel({ runners: [], choice: null, loadError: 'boom' })).not.toContain('No agent that can answer is installed')
})

test('while a turn runs the shrimp thinks with the one joke, and neither the composer nor the picker take input', () => {
  const out = panel({ messages: [ask], running: true })
  expect(out).toContain('class="dk-shrimp thinking"')
  expect(status(out)).toBe('Pelando tus docs…')
  expect(field(out)).toMatch(/readonly=""/i)                     // React writes it readOnly; HTML attributes ignore case
  expect(field(out)).not.toMatch(/\sdisabled=""/)                  // a disabled field would drop the focus to the page
  expect(field(out)).toMatch(/aria-disabled="true"/)
  expect(out).toMatch(/<button[^>]*type="submit"[^>]*disabled=""[^>]*>Enviar<\/button>/)
  expect(select(out)).toMatch(/^<select[^>]*disabled=""/)
  expect(out).toContain('How does auth work?')
  setLang('en')
  expect(status(panel({ messages: [ask], running: true }))).toBe('Peeling your docs…')
})

// The rest of the answer is laid out but hidden while it is revealed: the answer has its whole height from the first step, so
// the list can bring its start into view once when it lands and never move again while it fills in.
test('while an answer is revealed the shrimp answers, plainly; the text shown is the reveal\'s and the list is busy', () => {
  const out = panel({ messages: [ask, reply(JWT)] }, { reveal: { id: 2, text: 'It uses' } })
  expect(out).toContain('class="dk-shrimp answering"')
  expect(status(out)).toBe('Contestando…')
  expect(out).toContain('>It uses<span class="dk-answer-rest" aria-hidden="true"> JWT.</span></p>')
  expect(out).not.toContain('It uses JWT.')
  expect(out).toMatch(/class="dk-chat-list"[^>]*aria-busy="true"/)
  setLang('en')
  expect(status(panel({ messages: [ask, reply(JWT)] }, { reveal: { id: 2, text: 'It' } }))).toBe('Answering…')
})

test('a reveal of another message leaves this one whole', () => {
  const out = panel({ messages: [ask, reply(JWT)] }, { reveal: { id: 9, text: 'x' } })
  expect(out).toContain('It uses JWT.')
  expect(out).not.toContain('dk-answer-rest')
  expect(panel({ messages: [ask, reply(JWT)] }, { reveal: { id: 2, text: 'It uses JWT.' } })).not.toContain('dk-answer-rest')
})

test('an answer shows its text, who wrote it and its sources as buttons that open the portal', () => {
  const out = panel({ messages: [ask, reply(JWT)] })
  expect(out).toContain('It uses JWT.')
  expect(out).toContain('Respondido por claude (haiku). Compruébalo en sus fuentes.')
  expect(out).toMatch(/<button[^>]*aria-label="Ver: architecture\/overview.md#Context">architecture\/overview.md#Context<\/button>/)
  expect(out).not.toMatch(/<a [^>]*href=/)
  expect(out).toContain('class="dk-shrimp idle"')
})

test('a result without a model still says who answered, never "undefined"', () => {
  const out = panel({ messages: [ask, reply({ answer: 'Yes.', cited: [], runner: 'codex' })] })
  expect(out).toContain('Respondido por codex.')
  expect(out).not.toContain('undefined')
})

test('docs that had nothing to answer from: the existing sentence, not an error', () => {
  const out = panel({ messages: [ask, reply({ answer: null, cited: [], runner: 'claude' })] })
  expect(out).toContain('No he encontrado nada en la documentación que responda a eso.')
  expect(out).not.toContain('role="alert"')
  expect(out).not.toContain('undefined')
})

test.each([
  ['no AI answer here: no runner for bounded work (or ask.ai is false in workspace.yaml)', 'Aquí no hay IA para responder',
    'There is no AI to answer here'],
  ['no answer within 90 s: claude is slow or waiting for a login; try again', 'La IA no ha respondido a tiempo', 'The AI did not answer in time'],
  ['claude:haiku gave no answer: is it signed in, and does it have that model?', 'claude:haiku no ha contestado: ¿ha iniciado sesión y tiene ese modelo?',
    'claude:haiku gave no answer: is it signed in, and does it have that model?'],
  ['busy: a chat turn is still running', 'Todavía estoy respondiendo a la pregunta anterior', 'I am still answering the previous question'],
])('a failed turn is said in the app\'s language: %s', (raw, es, en) => {
  const failed = (lang) => { setLang(lang); return panel({ messages: [ask, reply(undefined, { error: raw })] }) }
  const out = failed('es')
  expect(out).toMatch(/role="alert"/)
  expect(out).toContain(es)
  expect(out).not.toContain('⚠')
  expect(failed('en')).toContain(en)
})

test('a question keeps its line breaks as text', () => {
  expect(panel({ messages: [{ id: 1, role: 'user', text: 'one\ntwo' }] })).toMatch(/<p class="dk-chat-q">one\ntwo<\/p>/)
})

// The wiring: the store's state as the panel's, through useStore (its snapshot in a static render).
test('DocsChat shows the store\'s state', () => {
  const state = { ...BASE, messages: [ask], running: true }
  const chat = { get: () => state, subscribe: () => () => {}, load: noop, send: noop, pick: noop, clear: noop }
  const out = renderToStaticMarkup(<DocsChat chat={chat} onClose={noop} onOpen={noop} />)
  expect(out).toContain('How does auth work?')
  expect(out).toContain('class="dk-shrimp thinking"')
})

test('the page\'s entry: a labelled field, a button that is not the page\'s primary, the tour\'s target', () => {
  const chat = { get: () => BASE, subscribe: () => () => {}, send: noop }
  const out = renderToStaticMarkup(<AskEntry chat={chat} onAsk={noop} />)
  expect(out).toMatch(/^<form[^>]*data-tour="docs-chat"/)
  expect(out).toMatch(/<input[^>]*aria-label="Pregunta"/)
  expect(out).toMatch(/<button type="submit" class="cu-btn cu-btn--secondary cu-btn--sm">Preguntar<\/button>/)
  setLang('en')
  const en = renderToStaticMarkup(<AskEntry chat={chat} onAsk={noop} />)
  expect(en).toMatch(/aria-label="Question"/)
  expect(en).toMatch(/>Ask<\/button>/)
})

test('the page\'s entry says what it is in words you can see, before its field, tied to it', () => {
  const chat = { get: () => BASE, subscribe: () => () => {}, send: noop }
  const out = renderToStaticMarkup(<AskEntry chat={chat} onAsk={noop} />)
  const label = out.match(/<label[^>]*for="([^"]+)"[^>]*>Preguntar con IA<\/label>/)
  expect(label).not.toBeNull()
  expect(out.indexOf('<label')).toBeLessThan(out.indexOf('<input'))
  expect(out).toMatch(new RegExp(`<input[^>]*id="${label[1]}"`))
  expect(out).toMatch(/<input[^>]*aria-label="Pregunta"/)
  setLang('en')
  expect(renderToStaticMarkup(<AskEntry chat={chat} onAsk={noop} />)).toMatch(/<label[^>]*>Ask with AI<\/label>/)
})

// The list's scroll: to the end when the person's question goes in (the thinking shrimp and what comes next are in view), to the
// START of an answer once when it lands (a long answer reads from its top), and nothing while it is revealed or for what was seen.
test('the conversation scrolls once per new message: to the end for a question, to the start of an answer', () => {
  const q2 = { id: 3, role: 'user', text: 'And the gateway?' }
  const a2 = { id: 4, role: 'assistant', text: 'Through Kong.', result: { answer: 'Through Kong.' } }
  expect(chatScroll(0, [])).toBe(null)
  expect(chatScroll(0, [ask])).toEqual({ id: 1, to: 'end' })
  expect(chatScroll(1, [ask])).toBe(null)
  expect(chatScroll(1, [ask, reply(JWT)])).toEqual({ id: 2, to: 'start' })
  expect(chatScroll(2, [ask, reply(JWT)])).toBe(null)
  expect(chatScroll(2, [ask, reply(JWT), q2])).toEqual({ id: 3, to: 'end' })
  expect(chatScroll(3, [ask, reply(JWT), q2, a2])).toEqual({ id: 4, to: 'start' })
  expect(chatScroll(0, [ask, reply(JWT), q2, a2])).toEqual({ id: 4, to: 'start' })     // the panel opens on the newest answer
  expect(chatScroll(4, [ask, reply(undefined, { id: 5, error: 'boom' })])).toEqual({ id: 5, to: 'start' })
})

test('a question goes out only when an agent and model are picked, AI is on and no turn runs', () => {
  expect(canSend(BASE)).toBe(true)
  expect(canSend({ ...BASE, running: true })).toBe(false)
  expect(canSend({ ...BASE, choice: null })).toBe(false)
  expect(canSend({ ...BASE, ai: false })).toBe(false)
  expect(canSend({ ...BASE, runners: [] })).toBe(false)
  expect(canSend({ ...BASE, runners: null })).toBe(false)
})

// The composer's keys (KeyboardEvent): Enter sends, Shift+Enter is a new line, an input method's Enter confirms its word.
test('Enter sends, Shift+Enter breaks the line, an IME\'s Enter does not send; Escape closes', () => {
  expect(chatKey({ key: 'Enter' })).toBe('send')
  expect(chatKey({ key: 'Enter', shiftKey: true })).toBe(null)
  expect(chatKey({ key: 'Enter', isComposing: true })).toBe(null)
  expect(chatKey({ key: 'Enter', keyCode: 229 })).toBe(null)
  expect(chatKey({ key: 'Escape' })).toBe('close')
  expect(chatKey({ key: 'Escape', isComposing: true })).toBe(null)
  expect(chatKey({ key: 'a' })).toBe(null)
})

// Which answer reveals: the newest, the first time it lands while the panel is open, once. One already there when the
// panel opens (a reopen, a return from another section) shows whole; Clear forgets them all.
test('an answer reveals once, only if it landed while the panel was open, and Clear starts over', () => {
  const r = revealer(new Set())
  const old = [ask, reply(JWT)]
  r.open(old)
  expect(r.next(old)).toBe(null)
  const q2 = { id: 3, role: 'user', text: 'And the gateway?' }
  expect(r.next([...old, q2])).toBe(null)
  const a2 = { id: 4, role: 'assistant', text: 'Through Kong.', result: { answer: 'Through Kong.' } }
  expect(r.next([...old, q2, a2])).toBe(a2)
  expect(r.next([...old, q2, a2])).toBe(null)
  const failed = { id: 5, role: 'assistant', text: '', error: 'boom' }
  expect(r.next([...old, q2, a2, failed])).toBe(null)
  r.open([...old, q2, a2])
  expect(r.next([...old, q2, a2])).toBe(null)
  r.clear()
  expect(r.next([...old, q2, a2])).toBe(a2)
})

test('every string of the chat exists in es and en', () => {
  const keys = Object.keys(S.es).filter((k) => k.startsWith('docs.chat.'))
  expect(keys.length).toBeGreaterThanOrEqual(10)
  for (const k of keys) expect(S.en[k], k).toBeTruthy()
})

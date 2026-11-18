import { expect, test, vi } from 'vitest'
import { chatStore, revealSteps } from './chat.js'

const MODELS = {
  runners: [
    { runner: 'claude', label: 'Claude', models: [{ id: 'haiku', label: 'Haiku', local: false }, { id: 'sonnet', label: 'Sonnet', local: false }] },
    { runner: 'codex', label: 'Codex', models: [{ id: '', label: 'default', local: false }] },
  ],
  choice: { runner: 'claude', model: 'haiku' },
  ai: true,
}

const done = (answer, extra = {}) => ({ status: 'done', log: answer ? [answer] : [], lines: 1, result: { answer, cited: [], runner: 'claude', model: 'haiku', ...extra } })
const failed = (...log) => ({ status: 'failed', log, lines: log.length, result: null })

// A follower that feeds the lines of the end it is given, as cmd.js's follow does, then resolves to it.
const finish = (end) => async (_srv, _job, { onLine }) => { end.log.forEach((l) => onLine?.(l)); return end }

function fake({ models = MODELS, follow = finish(done('ok')) } = {}) {
  const srv = {
    get: vi.fn(async (name) => { if (name !== 'app/chat/models') throw new Error(`unexpected GET ${name}`); return models }),
    post: vi.fn(async () => ({ id: 'j' })),
  }
  return { srv, store: chatStore(srv, { follow }) }
}

// A turn the test ends by hand, and the options its follower was given.
function held() {
  const turns = []
  const follow = (_srv, _job, opts) => new Promise((resolve) => turns.push({ opts, resolve }))
  return { turns, follow }
}

const loaded = async (opts) => { const f = fake(opts); await f.store.load(); return f }
const bodies = (srv) => srv.post.mock.calls.map(([, body]) => body)

test('a turn posts the question with the choice, then the answer lands in the conversation', async () => {
  const { srv, store } = await loaded({ follow: finish(done('The gateway signs tokens.', { cited: ['a.md'] })) })
  const turn = store.send('  what does the gateway do?  ')
  expect(store.get().running).toBe(true)
  expect(store.get().messages).toMatchObject([{ role: 'user', text: 'what does the gateway do?' }])
  await turn
  expect(srv.post).toHaveBeenCalledWith('app/chat', { q: 'what does the gateway do?', history: [], runner: 'claude', model: 'haiku' })
  const { messages, running } = store.get()
  expect(running).toBe(false)
  expect(messages).toHaveLength(2)
  expect(messages[1]).toMatchObject({ role: 'assistant', text: 'The gateway signs tokens.', result: { cited: ['a.md'], model: 'haiku' } })
  expect(messages[1].error).toBeUndefined()
})

test('the second question carries the first turn as history, never itself', async () => {
  let n = 0
  const { srv, store } = await loaded({ follow: async (...a) => finish(done(`answer ${++n}`))(...a) })
  await store.send('one')
  await store.send('two')
  await store.send('three')
  expect(bodies(srv).map((b) => b.q)).toEqual(['one', 'two', 'three'])
  expect(bodies(srv)[0].history).toEqual([])
  expect(bodies(srv)[1].history).toEqual([{ role: 'user', text: 'one' }, { role: 'assistant', text: 'answer 1' }])
  expect(bodies(srv)[2].history).toEqual([
    { role: 'user', text: 'one' }, { role: 'assistant', text: 'answer 1' }, { role: 'user', text: 'two' }, { role: 'assistant', text: 'answer 2' },
  ])
})

test('history leaves out what has no text and what failed', async () => {
  const ends = [done(null, { cited: [], runner: 'claude', model: undefined }), failed('⚠ boom'), done('fine')]
  const { srv, store } = await loaded({ follow: async (...a) => finish(ends.shift())(...a) })
  await store.send('nothing found here')
  await store.send('this fails')
  await store.send('this works')
  await store.send('last')
  expect(bodies(srv)[3].history).toEqual([
    { role: 'user', text: 'nothing found here' }, { role: 'user', text: 'this fails' }, { role: 'user', text: 'this works' }, { role: 'assistant', text: 'fine' },
  ])
})

test('a question sent while a turn runs is ignored: one turn at a time', async () => {
  const { turns, follow } = held()
  const { srv, store } = await loaded({ follow })
  const first = store.send('one')
  await vi.waitFor(() => expect(turns).toHaveLength(1))
  await store.send('two')
  expect(srv.post).toHaveBeenCalledTimes(1)
  expect(store.get().messages).toHaveLength(1)
  turns[0].resolve(done('a'))
  await first
  expect(store.get().running).toBe(false)
  store.send('two')
  await vi.waitFor(() => expect(srv.post).toHaveBeenCalledTimes(2))
})

test('an empty or blank question is ignored and changes nothing', async () => {
  const { srv, store } = await loaded()
  const before = store.get()
  const seen = vi.fn()
  store.subscribe(seen)
  await store.send('')
  await store.send('   \n\t ')
  await store.send(undefined)
  expect(srv.post).not.toHaveBeenCalled()
  expect(store.get()).toBe(before)
  expect(seen).not.toHaveBeenCalled()
})

test('a failed job becomes an error message with the last line, without its warning sign', async () => {
  const { store } = await loaded({ follow: finish(failed('thinking…', '⚠ no answer within 90 s')) })
  await store.send('q')
  const { messages, running } = store.get()
  expect(running).toBe(false)
  expect(messages[1]).toEqual({ id: messages[1].id, role: 'assistant', text: '', error: 'no answer within 90 s' })
})

test('the error is the last line the follower saw, even when the final read had no new ones', async () => {
  const follow = async (_srv, _job, { onLine }) => { onLine('⚠ the runner is gone'); return { status: 'failed', log: [], lines: 1, result: null } }
  const { store } = await loaded({ follow })
  await store.send('q')
  expect(store.get().messages[1].error).toBe('the runner is gone')
})

test('a failed job with no line at all is still an error', async () => {
  const { store } = await loaded({ follow: finish(failed()) })
  await store.send('q')
  expect(store.get().messages[1].error).toBe('failed')
})

test('a refused POST becomes an error message with the server\'s words', async () => {
  const { srv, store } = await loaded()
  srv.post.mockRejectedValueOnce(Object.assign(new Error('no AI answer here: ask.ai is off'), { status: 400 }))
  await store.send('q')
  const { messages, running } = store.get()
  expect(running).toBe(false)
  expect(messages.map((m) => m.role)).toEqual(['user', 'assistant'])
  expect(messages[1]).toMatchObject({ text: '', error: 'no AI answer here: ask.ai is off' })
  await store.send('again')
  expect(srv.post).toHaveBeenCalledTimes(2)
})

test('a follower that throws ends the turn as an error too', async () => {
  const { store } = await loaded({ follow: async () => { throw new Error('Failed to fetch') } })
  await store.send('q')
  expect(store.get().running).toBe(false)
  expect(store.get().messages[1].error).toBe('Failed to fetch')
})

test('a done job that found nothing is an answer with no text and no error', async () => {
  const { store } = await loaded({ follow: finish({ status: 'done', log: [], lines: 0, result: { answer: null, cited: [], runner: 'claude' } }) })
  await store.send('q')
  const reply = store.get().messages[1]
  expect(reply).toMatchObject({ role: 'assistant', text: '', result: { answer: null, cited: [], runner: 'claude' } })
  expect(reply.error).toBeUndefined()
  expect(store.get().running).toBe(false)
})

test('clear() empties the conversation and a turn still running no longer lands', async () => {
  const { turns, follow } = held()
  const { store } = await loaded({ follow })
  const turn = store.send('one')
  await vi.waitFor(() => expect(turns).toHaveLength(1))
  expect(turns[0].opts.gone()).toBe(false)
  store.clear()
  expect(store.get()).toMatchObject({ messages: [], running: false })
  expect(turns[0].opts.gone()).toBe(true)
  turns[0].resolve(done('too late'))
  await turn
  expect(store.get()).toMatchObject({ messages: [], running: false })
})

test('the old turn that ends after clear() does not touch a new one, and a new send works', async () => {
  const { turns, follow } = held()
  const { srv, store } = await loaded({ follow })
  const old = store.send('old')
  await vi.waitFor(() => expect(turns).toHaveLength(1))
  store.clear()
  const fresh = store.send('fresh')
  await vi.waitFor(() => expect(turns).toHaveLength(2))
  expect(bodies(srv)[1]).toMatchObject({ q: 'fresh', history: [] })
  turns[0].resolve(done('old answer'))
  await old
  expect(store.get().running).toBe(true)
  expect(store.get().messages.map((m) => m.text)).toEqual(['fresh'])
  turns[1].resolve(done('fresh answer'))
  await fresh
  expect(store.get().running).toBe(false)
  expect(store.get().messages.map((m) => m.text)).toEqual(['fresh', 'fresh answer'])
})

test('a POST that ends after clear() does not land either', async () => {
  const { srv, store } = await loaded()
  let release
  srv.post.mockImplementationOnce(() => new Promise((r) => { release = r }))
  const turn = store.send('one')
  await vi.waitFor(() => expect(release).toBeTypeOf('function'))
  store.clear()
  release({ id: 'j' })
  await turn
  expect(store.get()).toMatchObject({ messages: [], running: false })
})

test('a refused POST after clear() leaves no error message behind', async () => {
  const { srv, store } = await loaded()
  let refuse
  srv.post.mockImplementationOnce(() => new Promise((_, r) => { refuse = r }))
  const turn = store.send('one')
  await vi.waitFor(() => expect(refuse).toBeTypeOf('function'))
  store.clear()
  refuse(new Error('boom'))
  await turn
  expect(store.get()).toMatchObject({ messages: [], running: false })
})

test('the messages outlast a section: the store keeps them while nobody listens', async () => {
  const { store } = await loaded({ follow: finish(done('kept')) })
  const off = store.subscribe(() => {})
  await store.send('q')
  off()
  const again = vi.fn()
  const off2 = store.subscribe(again)
  expect(store.get().messages.map((m) => m.text)).toEqual(['q', 'kept'])
  off2()
})

test('a turn that ends while the section is away lands in the conversation', async () => {
  const { turns, follow } = held()
  const { store } = await loaded({ follow })
  const off = store.subscribe(() => {})
  const turn = store.send('q')
  await vi.waitFor(() => expect(turns).toHaveLength(1))
  off()
  turns[0].resolve(done('late but kept'))
  await turn
  expect(store.get().messages.map((m) => m.text)).toEqual(['q', 'late but kept'])
})

test('listeners hear every change at once, and stop hearing when they unsubscribe', async () => {
  const { store } = await loaded({ follow: finish(done('a')) })
  const seen = []
  const off = store.subscribe(() => seen.push({ running: store.get().running, n: store.get().messages.length }))
  const turn = store.send('q')
  expect(seen).toEqual([{ running: true, n: 1 }])
  await turn
  expect(seen).toEqual([{ running: true, n: 1 }, { running: false, n: 2 }])
  store.pick('claude', 'sonnet')
  store.clear()
  expect(seen).toHaveLength(4)
  off()
  store.pick('claude', 'haiku')
  expect(seen).toHaveLength(4)
})

test('get() is the same object until something changes, and a change never edits the old one', async () => {
  const { store } = await loaded({ follow: finish(done('a')) })
  const a = store.get()
  expect(store.get()).toBe(a)
  const turn = store.send('q')
  const b = store.get()
  expect(b).not.toBe(a)
  expect(a.messages).toEqual([])
  expect(a.running).toBe(false)
  await turn
  const c = store.get()
  expect(c).not.toBe(b)
  expect(b.messages).toHaveLength(1)
  expect(b.running).toBe(true)
  expect(store.get()).toBe(c)
  store.clear()
  expect(store.get()).not.toBe(c)
  expect(c.messages).toHaveLength(2)
})

test('each message has its own id, which clear() does not reuse', async () => {
  const { store } = await loaded()
  await store.send('one')
  await store.send('two')
  const ids = store.get().messages.map((m) => m.id)
  expect(new Set(ids).size).toBe(4)
  expect(ids).toEqual([...ids].sort((x, y) => x - y))
  store.clear()
  await store.send('three')
  expect(Math.min(...store.get().messages.map((m) => m.id))).toBeGreaterThan(Math.max(...ids))
})

test('before load() nothing is known: no runners yet, no choice, AI assumed', () => {
  const { store } = fake()
  expect(store.get()).toEqual({ messages: [], running: false, runners: null, choice: null, ai: true, loadError: '' })
})

test('load() reads the runners, the choice the server opens with and whether AI is on', async () => {
  const { srv, store } = fake()
  await store.load()
  expect(srv.get).toHaveBeenCalledWith('app/chat/models')
  expect(store.get()).toMatchObject({ runners: MODELS.runners, choice: { runner: 'claude', model: 'haiku' }, ai: true, loadError: '' })
})

test('with no runner installed there is no choice, whatever the server said', async () => {
  const { store } = await loaded({ models: { runners: [], choice: { runner: 'claude', model: 'haiku' }, ai: true } })
  expect(store.get()).toMatchObject({ runners: [], choice: null, loadError: '' })
})

test('ai: false is kept', async () => {
  const { store } = await loaded({ models: { ...MODELS, ai: false } })
  expect(store.get().ai).toBe(false)
})

test('load() that fails says why and leaves the runners empty', async () => {
  const { srv, store } = fake()
  srv.get.mockRejectedValueOnce(new Error('Failed to fetch'))
  await store.load()
  expect(store.get()).toMatchObject({ runners: [], choice: null, loadError: 'Failed to fetch' })
  await store.load()
  expect(store.get()).toMatchObject({ runners: MODELS.runners, choice: { runner: 'claude', model: 'haiku' }, loadError: '' })
})

test('a reload that fails keeps what was offered', async () => {
  const { srv, store } = await loaded()
  store.pick('claude', 'sonnet')
  srv.get.mockRejectedValueOnce(new Error('down'))
  await store.load()
  expect(store.get()).toMatchObject({ runners: MODELS.runners, choice: { runner: 'claude', model: 'sonnet' }, loadError: 'down' })
})

test('pick() changes the choice and the next turn uses it', async () => {
  const { srv, store } = await loaded()
  store.pick('claude', 'sonnet')
  expect(store.get().choice).toEqual({ runner: 'claude', model: 'sonnet' })
  await store.send('q')
  expect(bodies(srv)[0]).toMatchObject({ runner: 'claude', model: 'sonnet' })
  store.pick('codex', '')
  await store.send('q2')
  expect(bodies(srv)[1]).toMatchObject({ runner: 'codex', model: '' })
})

test('a reload keeps the pick while it is still offered, and takes the server\'s when it is not', async () => {
  const { srv, store } = await loaded()
  store.pick('claude', 'sonnet')
  await store.load()
  expect(store.get().choice).toEqual({ runner: 'claude', model: 'sonnet' })
  const trimmed = MODELS.runners.map((r) => (r.runner === 'claude' ? { ...r, models: [r.models[0]] } : r))
  srv.get.mockResolvedValueOnce({ ...MODELS, runners: trimmed })
  await store.load()
  expect(store.get().choice).toEqual({ runner: 'claude', model: 'haiku' })
})

test('without a pick of its own, a reload takes the server\'s new choice', async () => {
  const { srv, store } = await loaded()
  srv.get.mockResolvedValueOnce({ ...MODELS, choice: { runner: 'codex', model: '' } })
  await store.load()
  expect(store.get().choice).toEqual({ runner: 'codex', model: '' })
})

test('with no choice at all the turn goes out with empty ones and the server\'s refusal is the answer', async () => {
  const { srv, store } = await loaded({ models: { runners: [], choice: null, ai: true } })
  srv.post.mockRejectedValueOnce(new Error('no runner installed'))
  await store.send('q')
  expect(srv.post).toHaveBeenCalledWith('app/chat', { q: 'q', history: [], runner: '', model: '' })
  expect(store.get().messages[1].error).toBe('no runner installed')
})

test('clear() leaves the runners and the choice alone', async () => {
  const { store } = await loaded()
  store.pick('claude', 'sonnet')
  store.clear()
  expect(store.get()).toMatchObject({ runners: MODELS.runners, choice: { runner: 'claude', model: 'sonnet' }, ai: true })
})

const words = (n) => Array.from({ length: n }, (_, i) => `w${i}`).join(' ')

test('the reveal grows by words and ends with the whole text', () => {
  expect(revealSteps('one two three')).toEqual(['one', 'one two', 'one two three'])
  const text = 'Gateway signs the tokens.\n\nSecond paragraph here.  '
  const steps = revealSteps(text)
  expect(steps.at(-1)).toBe(text)
  expect(steps[0]).toBe('Gateway')
  steps.forEach((s, i) => { expect(text.startsWith(s)).toBe(true); if (i) expect(s.length).toBeGreaterThan(steps[i - 1].length) })
})

test('a long text reveals in at most maxMs / stepMs steps', () => {
  const text = words(500)
  const steps = revealSteps(text)
  expect(steps).toHaveLength(30)
  expect(steps.at(-1)).toBe(text)
  steps.slice(0, -1).forEach((s) => expect(text.slice(s.length, s.length + 1)).toBe(' '))
  expect(revealSteps(text, { maxMs: 1000, stepMs: 100 })).toHaveLength(10)
  expect(revealSteps(text, { maxMs: 40, stepMs: 50 })).toEqual([text])
  expect(revealSteps(words(8), { maxMs: 1500, stepMs: 50 })).toHaveLength(8)
  expect(revealSteps(words(31))).toHaveLength(30)
  expect(revealSteps(words(30))).toHaveLength(30)
})

test('an empty or blank text reveals as one empty step', () => {
  expect(revealSteps('')).toEqual([''])
  expect(revealSteps('   \n ')).toEqual([''])
  expect(revealSteps(undefined)).toEqual([''])
  expect(revealSteps(null)).toEqual([''])
})

test('one very long word is one step: it is never cut in the middle', () => {
  const word = 'x'.repeat(5000)
  expect(revealSteps(word)).toEqual([word])
  expect(revealSteps(`  ${word}`)).toEqual([`  ${word}`])
})

test('the reveal never splits a character made of two UTF-16 units, nor leaves a word half said', () => {
  const text = Array.from({ length: 40 }, () => '😀🦐 ok').join(' ')
  const steps = revealSteps(text)
  expect(steps.at(-1)).toBe(text)
  steps.forEach((s) => {
    expect(s).toMatch(/^(?:[^\uD800-\uDFFF]|[\uD800-\uDBFF][\uDC00-\uDFFF])*$/)
    expect(s).toMatch(/(?:😀🦐|ok)$/)
  })
  expect(revealSteps('🦐')).toEqual(['🦐'])
})

test('the reveal is pure: the same text gives the same steps', () => {
  const text = words(100)
  expect(revealSteps(text)).toEqual(revealSteps(text))
})

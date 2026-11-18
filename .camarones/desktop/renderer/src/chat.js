import { follow } from './cmd.js'

// The Docs chat's conversation as one store for the window (like jobs.js). Docs unmounts when you go to the Board and
// useJob drops a result on unmount, so the messages and the turn in flight live here, and a late answer still lands.
// One per window: switching projects opens a new window in this one's place. Errors are kept as the raw strings; the
// panel words them.

// Growing prefixes of text, cut after a whole word, at most maxMs / stepMs of them, the last one the whole text: the
// answer arrives in one piece, so showing it in chunks is presentation only.
export function revealSteps(text, { maxMs = 1500, stepMs = 50 } = {}) {
  const s = String(text ?? '')
  const ends = [...s.matchAll(/\s*\S+/g)].map((m) => m.index + m[0].length)
  if (!ends.length) return ['']
  const n = Math.min(Math.max(1, Math.floor(maxMs / stepMs)), ends.length)
  const steps = Array.from({ length: n }, (_, i) => s.slice(0, ends[Math.ceil(((i + 1) * ends.length) / n) - 1]))
  steps[n - 1] = s
  return steps
}

const offers = (runners, c) => !!c && runners.some((r) => r.runner === c.runner && r.models.some((m) => m.id === c.model))

// srv: the project's server client (get, post). followJob is injectable for tests.
export function chatStore(srv, { follow: followJob = follow } = {}) {
  let state = { messages: [], running: false, runners: null, choice: null, ai: true, loadError: '' }
  let epoch = 0, nextId = 0, picked = null
  const listeners = new Set()
  const set = (patch) => {
    state = { ...state, ...patch }
    listeners.forEach((f) => f())
  }
  const message = (role, rest) => ({ id: ++nextId, role, ...rest })

  async function load() {
    try {
      const m = await srv.get('app/chat/models')
      const runners = m.runners || []
      const choice = !runners.length ? null : offers(runners, picked) ? picked : m.choice || null
      set({ runners, choice, ai: m.ai !== false, loadError: '' })
    } catch (e) {
      set({ runners: state.runners || [], loadError: e.message })
    }
  }

  // A turn dropped by clear() is still followed to its end, its answer thrown away: the server runs one turn at a time and
  // refuses another meanwhile, so the composer stays closed (`running`) until it ends.
  async function send(q) {
    const text = String(q ?? '').trim()
    if (!text || state.running) return
    const mine = epoch
    const history = state.messages.filter((m) => m.text && !m.error).map((m) => ({ role: m.role, text: m.text }))
    set({ messages: [...state.messages, message('user', { text })], running: true })
    const lines = []
    let reply
    try {
      const job = await srv.post('app/chat', { q: text, history, runner: state.choice?.runner ?? '', model: state.choice?.model ?? '' })
      const end = await followJob(srv, job, { onLine: (l) => lines.push(l) })
      reply = end.status === 'done'
        ? { text: end.result?.answer || '', result: end.result }
        : { text: '', error: (lines.at(-1) || end.status).replace(/^⚠ /, '') }
    } catch (e) {
      reply = { text: '', error: e.message }
    }
    set(epoch === mine ? { messages: [...state.messages, message('assistant', reply)], running: false } : { running: false })
  }

  return {
    get: () => state,
    subscribe(f) { listeners.add(f); return () => listeners.delete(f) },
    load,
    send,
    pick(runner, model) {
      picked = { runner, model }
      set({ choice: picked })
    },
    clear() {
      epoch++
      set({ messages: [] })
    },
  }
}

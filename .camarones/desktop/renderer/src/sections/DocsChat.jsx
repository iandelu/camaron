import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { Aviso, Button } from '@camaron/ui'
import { revealSteps } from '../chat.js'
import { answerView, askError } from '../docs.js'
import { useStore } from '../hooks.js'
import { t } from '../i18n.js'
import { Shrimp } from './Shrimp.jsx'

// The Docs chat on the window's chat store (chat.js): the page's entry into it and the panel beside the page (Docs owns
// whether it is open). ChatPanel draws a state; DocsChat wires it to the store and owns what a static render cannot show:
// the reveal, the focus and the scroll.

const STEP_MS = 50

// A question can go out: an agent and model picked among those installed, AI not switched off, no turn running (one at a time).
export const canSend = (s) => !s.running && !!s.runners?.length && !!s.choice && s.ai !== false

// What a key does in the panel (a KeyboardEvent): Enter sends from the composer, Shift+Enter is the textarea's new line, Escape
// closes. An input method's Enter or Escape is its own: it confirms or drops the word being composed.
export function chatKey(e) {
  if (e.isComposing || e.keyCode === 229) return null
  if (e.key === 'Escape') return 'close'
  return e.key === 'Enter' && !e.shiftKey ? 'send' : null
}

// Which answer the panel reveals: the newest message, when it is an answer with text not shown before. `seen` outlives the
// panel, so an answer is revealed once, the first time it lands while the panel is open; those already there when it opens
// (a reopen, a return from another section) show whole. Clear forgets them.
export function revealer(seen) {
  return {
    open(messages) { for (const m of messages) seen.add(m.id) },
    next(messages) {
      const last = messages.at(-1)
      if (last?.role !== 'assistant' || !last.text || seen.has(last.id)) return null
      seen.add(last.id)
      return last
    },
    clear() { seen.clear() },
  }
}
const REVEAL = revealer(new Set())

const lessMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

// The newest answer's text in growing steps, as {id, text} while they run, else null; `skip` shows it whole. Layout effects,
// in this order: what was there is marked before a new answer is looked for, and the first step lands before paint, so the
// whole text never flashes first. The timer stops with the panel.
function useReveal(messages) {
  const [reveal, setReveal] = useState(null)
  const timer = useRef(0)
  const halt = () => clearInterval(timer.current)
  useLayoutEffect(() => { REVEAL.open(messages); return halt }, [])
  useLayoutEffect(() => {
    const m = REVEAL.next(messages)
    if (!m || lessMotion()) return
    halt()
    const steps = revealSteps(m.text, { stepMs: STEP_MS })
    let i = 0
    setReveal({ id: m.id, text: steps[0] })
    timer.current = setInterval(() => {
      i += 1
      if (i < steps.length) setReveal({ id: m.id, text: steps[i] })
      else { halt(); setReveal(null) }
    }, STEP_MS)
  }, [messages])
  return { reveal, skip: () => { halt(); setReveal(null) } }
}

// How the list scrolls for a new message (`seen`: the id it last scrolled for): to the end for the person's question, so it and
// the thinking shrimp below are in view; to the start of an answer, so a long one reads from its top. Once per message: never
// while an answer is revealed, never again for one already seen. {id, to: 'end' | 'start'}, or null.
export function chatScroll(seen, messages) {
  const last = messages.at(-1)
  if (!last || last.id === seen) return null
  return { id: last.id, to: last.role === 'user' ? 'end' : 'start' }
}

// Opening moves the focus to the composer (to the panel itself while the composer is closed). The list scrolls as chatScroll says,
// in one jump (no smooth scrolling, so nothing moves for who asked for less motion), and only itself: the newest message is its
// last element.
export function DocsChat({ chat, onClose, onOpen }) {
  const state = useStore(chat)
  const { reveal, skip } = useReveal(state.messages)
  const refs = { root: useRef(null), field: useRef(null), list: useRef(null) }
  const scrolled = useRef(0)
  useEffect(() => { (refs.field.current?.disabled ? refs.root.current : refs.field.current)?.focus() }, [])
  useEffect(() => {
    const l = refs.list.current, s = chatScroll(scrolled.current, state.messages)
    if (!l || !s) return
    scrolled.current = s.id
    if (s.to === 'end') l.scrollTop = l.scrollHeight
    else if (l.lastElementChild) l.scrollTop += l.lastElementChild.getBoundingClientRect().top - l.getBoundingClientRect().top
  }, [state.messages])
  const clear = () => { skip(); REVEAL.clear(); chat.clear() }
  return <ChatPanel state={state} reveal={reveal} refs={refs} onSend={chat.send} onPick={chat.pick} onClear={clear} onClose={onClose}
    onOpen={onOpen} onSkip={skip} onRetry={chat.load} />
}

// The panel for one state of the store. `reveal` ({id, text} or null) is the part of an answer shown so far. While a turn runs
// the composer keeps the focus but takes no input (read-only, not disabled: a disabled field would drop the focus to the page).
export function ChatPanel({ state, reveal = null, refs = {}, onSend, onPick, onClear, onClose, onOpen, onSkip, onRetry }) {
  const [q, setQ] = useState('')
  const usable = !!state.runners?.length && !!state.choice && state.ai !== false
  const can = canSend(state)
  const send = () => { if (can && q.trim()) { onSend(q); setQ('') } }
  const shrimp = state.running ? 'thinking' : reveal ? 'answering' : 'idle'
  return (
    <aside className="dk-chat" ref={refs.root} tabIndex={-1} aria-label={t('docs.ask')}
      onKeyDown={(e) => { if (chatKey(e.nativeEvent) === 'close') { e.preventDefault(); onClose() } }}>
      <div className="row dk-chat-head">
        <h2 className="dk-chat-title">{t('docs.ask')}</h2>
        <Button size="sm" variant="ghost" disabled={!state.messages.length} onClick={onClear}>{t('docs.chat.clear')}</Button>
        <Button size="sm" variant="ghost" onClick={onClose}>{t('docs.chat.close')}</Button>
      </div>
      {state.runners?.length
        ? <Picker runners={state.runners} choice={state.choice} disabled={state.running || state.ai === false} onPick={onPick} /> : null}
      <Notices state={state} onRetry={onRetry} />
      <div className="dk-chat-list" ref={refs.list} role="log" aria-live="polite" aria-busy={reveal ? 'true' : undefined}
        aria-label={t('docs.chat.messages')}>
        {state.messages.length ? state.messages.map((m) => (m.role === 'user'
          ? <p key={m.id} className="dk-chat-q">{m.text}</p>
          : <Reply key={m.id} message={m} shown={reveal?.id === m.id ? reveal.text : null} onOpen={onOpen} onSkip={onSkip} />))
          : <p className="muted small">{t('docs.askHint')}</p>}
      </div>
      <div className="dk-chat-status">
        <Shrimp state={shrimp} />
        <span className="muted small" role="status">
          {shrimp === 'thinking' ? t('docs.chat.thinking') : shrimp === 'answering' ? t('docs.chat.answering') : ''}</span>
      </div>
      <form className="dk-chat-form" onSubmit={(e) => { e.preventDefault(); send() }}>
        <textarea className="cu-input dk-chat-field" ref={refs.field} rows={2} value={q} placeholder={t('docs.askPh')}
          aria-label={t('docs.chat.field')} disabled={!usable} readOnly={state.running} aria-disabled={state.running ? 'true' : undefined}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (chatKey(e.nativeEvent) === 'send') { e.preventDefault(); send() } }} />
        <Button type="submit" size="sm" disabled={!can || !q.trim()}>{t('docs.chat.send')}</Button>
      </form>
    </aside>
  )
}

// One select: a group per installed agent, an option per model, valued `runner|model` (a model id never holds a `|`). A closed
// select shows only the option's text, so each names its agent too. The entry whose model the CLI decides has id '' and is
// worded "default"; a configured default (lib/chat.py's label "default" with an id, Codex's) names its model; a local one says so.
const modelName = (m) => {
  const name = m.id === '' ? t('docs.chat.default') : m.label === 'default' && !m.local ? t('docs.chat.defaultIs', { model: m.id }) : m.label
  return m.local ? t('docs.chat.local', { model: name }) : name
}
function Picker({ runners, choice, disabled, onPick }) {
  const pick = (e) => {
    const v = e.target.value
    const at = v.indexOf('|')
    onPick(v.slice(0, at), v.slice(at + 1))
  }
  return (
    <select className="cu-input dk-chat-pick" aria-label={t('docs.chat.model')} value={choice ? `${choice.runner}|${choice.model}` : ''}
      disabled={disabled} onChange={pick}>
      {runners.map((r) => (
        <optgroup key={r.runner} label={r.label}>
          {r.models.map((m) => <option key={m.id} value={`${r.runner}|${m.id}`}>{`${r.label} · ${modelName(m)}`}</option>)}
        </optgroup>))}
    </select>
  )
}

// Why the composer is closed, each with its way out. A failed read keeps the models it had, so it may come with a picker; with
// none it is said alone: nothing read is not "no agent installed".
function Notices({ state, onRetry }) {
  const none = Array.isArray(state.runners) && !state.runners.length
  if (state.loadError && none) return <Unread onRetry={onRetry} />
  return (
    <>
      {state.loadError ? <Unread onRetry={onRetry} /> : null}
      {none
        ? <Aviso tone="warn" title={t('docs.chat.noAgent')} action={<Button size="sm" href="#/machine">{t('docs.chat.toMachine')}</Button>} />
        : state.ai === false ? <Aviso tone="info" title={t('docs.askNoAi')} /> : null}
    </>
  )
}
const Unread = ({ onRetry }) => <Aviso tone="warn" title={t('docs.chat.unread')} action={<Button size="sm" onClick={onRetry}>{t('retry')}</Button>} />

// An answer while it is revealed (`shown`) is its text alone: who wrote it and its sources follow once it is whole.
function Reply({ message, shown, onOpen, onSkip }) {
  if (message.error) return <Aviso tone="error" title={askError(message.error, t)} />
  const view = answerView(message.result)
  return shown == null ? <AnswerView view={view} onOpen={onOpen} />
    : <AnswerView view={{ ...view, text: shown, by: '', sources: [] }} onOpen={onOpen} onText={onSkip} />
}

// The answer as text, who wrote it, and its sources as buttons that open the page in the portal. `onText`: a click on the text.
export function AnswerView({ view, onOpen, onText }) {
  if (view.kind === 'none') return <p className="muted">{t('docs.askNone')}</p>
  return (
    <div className="dk-out">
      <p className="dk-answer" onClick={onText}>{view.text}</p>
      {view.by ? <p className="muted small">{t('docs.by', { who: view.by })}</p> : null}
      {view.sources.length ? (
        <div className="row">
          <span className="muted small">{t('docs.sources')}</span>
          {view.sources.map((s) => (
            <Button key={s.cite} size="sm" variant="ghost" aria-label={`${t('docs.view')}: ${s.cite}`} onClick={() => onOpen(s.hash)}>{s.cite}</Button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

// The page's way into the chat, under its visible name: the question goes to the conversation when one can go, and the panel
// opens on it. An empty field only opens the panel; a question that cannot go yet stays in the field.
export function AskEntry({ chat, onAsk }) {
  const [q, setQ] = useState('')
  const id = useId()
  const submit = (e) => {
    e.preventDefault()
    if (q.trim() && canSend(chat.get())) { chat.send(q); setQ('') }
    onAsk()
  }
  return (
    <form className="dk-ask" data-tour="docs-chat" onSubmit={submit}>
      <label className="eyebrow dk-ask-label" htmlFor={id}>{t('docs.ask')}</label>
      <input className="cu-input dk-grow" id={id} value={q} placeholder={t('docs.askPh')} aria-label={t('docs.askLabel')}
        onChange={(e) => setQ(e.target.value)} />
      <Button type="submit" size="sm">{t('docs.askGo')}</Button>
    </form>
  )
}

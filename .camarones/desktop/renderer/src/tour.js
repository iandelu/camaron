// The guided tours, pure: each step names the section it lives in (null: wherever you are) and the data-tour target it
// points at; its title and text are i18n keys tour.<id>.<n>.t / .b (n from 1). Where the bubble goes and the dim around
// the target are worked out here, so the overlay (Tour.jsx) only draws.

import { LIBS } from './nav.js'

const nav = (s) => ({ section: null, target: `nav-${s}` })
const at = (section, ...targets) => targets.map((target) => ({ section, target }))

export const TOURS = {
  app: [{ section: null, target: 'rail' }, ...['flow', 'board', 'quality', 'docs', 'settings'].map(nav),
    { section: null, target: 'find' }, { section: null, target: 'portal' }, { section: null, target: 'menu' },
    { section: null, target: 'jobs' }, nav('guide')],
  flow: at('flow', 'tabs-flow', 'summary-next', 'summary-doctor', 'summary-stats', 'summary-repos'),
  plan: at('flow/plan', 'plan-run', 'plan-keep', 'plan-units', 'plan-cost', 'plan-reset'),
  board: at('board', 'board-columns', 'board-add', 'board-help'),
  quality: at('quality', 'q-verdict', 'q-areas', 'q-repos'),
  libs: at(LIBS, 'libs-actions', 'libs-filters', 'libs-table'),
  docs: at('docs', 'docs-team', 'tabs-docs', 'docs-portal', 'docs-c4', 'docs-ask'),
  interviews: at('docs/interviews', 'iv-mode', 'iv-questionnaire', 'iv-agents'),
  settings: [...at('settings', 'tabs-settings', 'mc-guide', 'mc-setup', 'mc-settings', 'mc-repos'), ...at('settings/tokens', 'mc-tokens'),
    ...at('settings/skills', 'team-skills'), ...at('settings/plugins', 'team-plugins'), ...at('settings/trust', 'team-trust'),
    ...at('settings/kit', 'mc-kit', 'mc-uninstall')],
}

// The place each tour belongs to: its steps live there or in one of its views.
export const HOME = { flow: 'flow', plan: 'flow/plan', board: 'board', quality: 'quality', libs: LIBS, docs: 'docs', interviews: 'docs/interviews', settings: 'settings' }

// Tours that merged into a place keep answering to their old id (old guides in projects still carry them).
const ALIAS = { summary: 'flow', team: 'docs', machine: 'settings' }
export const tourAlias = (id) => ALIAS[id] || id

export const tourIds = () => Object.keys(TOURS)

const MARGIN = 8
const clamp = (v, lo, hi) => Math.max(lo, Math.min(v, hi))

// Below the target if it fits, else above, right, left; else centred. Always inside the window, MARGIN from its edges.
export function place(rect, bubble, view, gap = 12) {
  const x = (v) => clamp(v, MARGIN, view.w - bubble.w - MARGIN)
  const y = (v) => clamp(v, MARGIN, view.h - bubble.h - MARGIN)
  if (rect) {
    const below = rect.top + rect.height + gap
    if (below + bubble.h <= view.h - MARGIN) return { top: below, left: x(rect.left), side: 'below' }
    const above = rect.top - gap - bubble.h
    if (above >= MARGIN) return { top: above, left: x(rect.left), side: 'above' }
    const right = rect.left + rect.width + gap
    if (right + bubble.w <= view.w - MARGIN) return { top: y(rect.top), left: right, side: 'right' }
    const left = rect.left - gap - bubble.w
    if (left >= MARGIN) return { top: y(rect.top), left, side: 'left' }
  }
  return { top: y((view.h - bubble.h) / 2), left: x((view.w - bubble.w) / 2), side: 'center' }
}

// The dim as four bands around the target, padded and kept inside the window.
export function holes(rect, view, pad = 6) {
  const top = clamp(rect.top - pad, 0, view.h)
  const left = clamp(rect.left - pad, 0, view.w)
  const bottom = clamp(rect.top + rect.height + pad, top, view.h)
  const right = clamp(rect.left + rect.width + pad, left, view.w)
  return [
    { top: 0, left: 0, width: view.w, height: top },
    { top: bottom, left: 0, width: view.w, height: view.h - bottom },
    { top, left: 0, width: left, height: bottom - top },
    { top, left: right, width: view.w - right, height: bottom - top },
  ]
}

// What a key does while a tour is open; null leaves it to the page. Keys typed into a field or a dialog (the palette),
// or pressed on the control in the hole, are the page's. Inside the bubble a focused button presses itself with Enter.
export function tourAction(key, { typing = false, inBubble = false, onBubble = false } = {}) {
  if (typing || !(inBubble || onBubble)) return null
  if (key === 'Escape') return 'close'
  if (key === 'ArrowRight') return 'next'
  if (key === 'ArrowLeft') return 'back'
  return key === 'Enter' && onBubble ? 'next' : null
}

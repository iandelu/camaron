// The app's places, pure: a project's places and their views, this machine's, which one an address asks for, a project's initials.
import places from './places.json'

export const PROJECT = ['flow', 'board', 'quality', 'docs']
export const MACHINE = ['settings', 'guide', 'kitdev']

// The views of a place (tabs), the first one its default: it has no segment in the address.
export const VIEWS = places.views

// Kit dev is the bench of a checkout of the kit (lib/kitdev.py): only there.
export const sections = ({ kitdev }) => ({ project: PROJECT, machine: kitdev ? MACHINE : MACHINE.filter((s) => s !== 'kitdev') })

// The first-run wizard (#/start): a place of its own, full width, never listed in the nav.
export const START = 'start'

export const LIBS = 'quality/libs'

// Every place the tours and the nav follow: a section, then each of its views but the default one.
export const PLACES = [...PROJECT, ...MACHINE].flatMap((s) => [s, ...(VIEWS[s] || []).slice(1).map((v) => `${s}/${v}`)])

// Sections that became a place or a view of another keep their old address (a bookmark, an old guide).
const MOVED = { summary: 'flow', plan: 'flow/plan', decisions: 'docs/decisions', interviews: 'docs/interviews', team: 'docs', machine: 'settings', libs: 'quality/libs' }

// Where an old address goes now (what follows it is kept), or null when it has not moved.
export const movedRoute = (hash) => {
  const m = String(hash || '').match(/^#\/([\w-]+)(?=[/?]|$)(.*)$/)
  if (!m || !Object.hasOwn(MOVED, m[1])) return null
  const [, name, rest] = m
  // The Tokens form is what Quality links to with a host or a kind.
  const q = rest.startsWith('?') ? new URLSearchParams(rest.slice(1)) : null
  if (name === 'machine' && q && (q.has('host') || q.has('kind'))) return `#/settings/tokens${rest}`
  return `#/${MOVED[name]}${rest}`
}

// The place a guide's go: marker names (old names follow their moves), or null when it names nothing known.
export const goPlace = (target) => {
  const place = (movedRoute(`#/${target}`) || `#/${target}`).slice(2).split('?')[0]
  return PLACES.includes(place) ? place : null
}

const current = (hash) => movedRoute(hash) || String(hash || '')

export function sectionOf(hash, flags) {
  const s = (current(hash).match(/^#\/([\w-]+)/) || [])[1]
  const all = [...PROJECT, ...sections(flags).machine, START]
  return all.includes(s) ? s : 'flow'
}

// The view of a section the address asks for; the second segment of #/quality/<x> may also be a command of the folded
// list, so anything that is not a view is the default one. '' for a section without views.
export function viewOf(hash, section) {
  const views = VIEWS[section]
  if (!views) return ''
  const [, first, second] = current(hash).match(/^#\/([\w-]+)(?:\/([\w-]+))?/) || []
  return first === section && views.includes(second) ? second : views[0]
}

export function placeOf(hash, flags) {
  const s = sectionOf(hash, flags)
  const v = viewOf(hash, s)
  return v && v !== VIEWS[s][0] ? `${s}/${v}` : s
}

// What #/settings/tokens?host=<h>&kind=<k> asks the Tokens card to fill in (Quality links there for a repo's SonarQube).
export const TOKEN_KINDS = ['gitlab', 'github', 'sonarqube']
export function tokenPrefill(hash) {
  const [route, query = ''] = String(hash || '').split('?')
  if (route !== '#/settings/tokens') return { host: '', kind: '' }
  const q = new URLSearchParams(query)
  const kind = q.get('kind') || ''
  return { host: q.get('host') || '', kind: TOKEN_KINDS.includes(kind) ? kind : '' }
}

// The Tokens notice for a prefill: SonarQube comes from Quality; a forge or no kind, from a share Docs could not make
// (its refused-token link, or an old #/machine?host= one). null: nothing to say.
export const tokenNotice = ({ host, kind }) => (!host ? null : kind === 'sonarqube' ? 'st.fromQuality' : 'st.fromShare')

// #/flow/plan?term=<id>: the Plan opens with that terminal in front. Anything but a terminal's id is ignored.
export function termOf(hash) {
  const [route, query = ''] = String(hash || '').split('?')
  const id = route === '#/flow/plan' ? new URLSearchParams(query).get('term') : null
  return /^t-[\w.-]+-\d+$/.test(id || '') ? id : null
}

// Where a project window goes once it knows its first run (GET app/onboard/state): an unfinished one to the wizard,
// unless it is there already; a finished one (or no state: the read failed) stays where it was asked. null: stay.
export const firstRunPending = (state) => state?.done === false
export const firstRunRoute = (state, hash) => (firstRunPending(state) && sectionOf(hash, {}) !== START ? `#/${START}` : null)

// Two letters for the rail: the first letters of the first two words, or the first two of a single word.
export function initials(name) {
  const words = String(name || '').split(/[\s_-]+/).filter(Boolean)
  if (!words.length) return '?'
  const s = words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2)
  return s.toUpperCase()
}

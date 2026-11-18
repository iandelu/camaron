// The app's places, pure: a project's sections, this machine's, which one an address asks for, a project's initials.

export const PROJECT = ['summary', 'board', 'decisions', 'plan', 'interviews', 'team', 'quality', 'docs']
export const MACHINE = ['machine', 'guide', 'kitdev']

// Kit dev is the bench of a checkout of the kit (lib/kitdev.py): only there.
export const sections = ({ kitdev }) => ({ project: PROJECT, machine: kitdev ? MACHINE : MACHINE.filter((s) => s !== 'kitdev') })

// The first-run wizard (#/start): a place of its own, full width, never listed in the nav.
export const START = 'start'

// Places that moved into another section keep their old address (a bookmark, an old guide): #/libs is Quality's libraries.
const MOVED = { libs: 'quality' }

export function sectionOf(hash, flags) {
  const s = ((hash || '').match(/^#\/([\w-]+)/) || [])[1]
  const all = [...PROJECT, ...sections(flags).machine, START]
  return all.includes(s) ? s : MOVED[s] || 'summary'
}

// Quality shows its board or, beside it, the libraries. The second segment of #/quality/<x> is also the command the
// palette opens in the folded list, so only `libs` is a view.
export const LIBS = 'quality/libs'
export const qualityView = (hash) => (/^#\/(quality\/)?libs(?=[/?]|$)/.test(hash || '') ? 'libs' : 'health')

// Where an old address goes now (what follows it is kept), or null when it has not moved.
export const movedRoute = (hash) => {
  const m = String(hash || '').match(/^#\/libs(?=[/?]|$)(.*)$/)
  return m ? `#/${LIBS}${m[1]}` : null
}

// The place the tours and the nav follow: the section, but the libraries are a place of their own inside Quality.
export function placeOf(hash, flags) {
  const s = sectionOf(hash, flags)
  return s === 'quality' && qualityView(hash) === 'libs' ? LIBS : s
}

// What #/machine?host=<h>&kind=<k> asks the Tokens card to fill in (Quality links there for a repo's SonarQube).
export const TOKEN_KINDS = ['gitlab', 'github', 'sonarqube']
export function tokenPrefill(hash) {
  const [route, query = ''] = String(hash || '').split('?')
  if (route !== '#/machine') return { host: '', kind: '' }
  const q = new URLSearchParams(query)
  const kind = q.get('kind') || ''
  return { host: q.get('host') || '', kind: TOKEN_KINDS.includes(kind) ? kind : '' }
}

// #/plan?term=<id>: the Plan opens with that terminal in front. Anything but a terminal's id is ignored.
export function termOf(hash) {
  const [route, query = ''] = String(hash || '').split('?')
  const id = route === '#/plan' ? new URLSearchParams(query).get('term') : null
  return /^t-[\w.-]+-\d+$/.test(id || '') ? id : null
}

// Where a project window goes once it knows its first run (GET app/onboard/state): an unfinished one to the wizard,
// unless it is there already; a finished one (or no state: the read failed) stays where it was asked. null: stay.
export const firstRunPending = (state) => state?.done === false
export const firstRunRoute = (state, hash) => (firstRunPending(state) && sectionOf(hash, {}) !== START ? `#/${START}` : null)

// The window catches up with the team on open, unless the first run is still ahead (the wizard sets the docs up first).
export const catchUpOnOpen = (state, hash) => !firstRunRoute(state, hash) && !firstRunPending(state)

// Two letters for the rail: the first letters of the first two words, or the first two of a single word.
export function initials(name) {
  const words = String(name || '').split(/[\s_-]+/).filter(Boolean)
  if (!words.length) return '?'
  const s = words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2)
  return s.toUpperCase()
}

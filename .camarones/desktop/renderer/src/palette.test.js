import { expect, test } from 'vitest'
import { ALIASES, chord, entries, GO, keyFor, pick, typing } from './palette.js'

const ALL = ['flow', 'board', 'quality', 'docs', 'settings', 'guide', 'kitdev']
const t = (k) => `<${k}>`

test('one letter per section, each section once', () => {
  expect(GO).toEqual({ f: 'flow', b: 'board', q: 'quality', d: 'docs', m: 'settings', h: 'guide', k: 'kitdev' })
  expect(ALIASES).toEqual({ s: 'flow', p: 'flow/plan', a: 'docs/decisions', i: 'docs/interviews', t: 'docs' })
  expect(keyFor('flow')).toBe('f')
  expect(keyFor('settings')).toBe('m')
  expect(keyFor('nope')).toBeUndefined()
})

test('g and then a letter goes to its place, while the g is fresh', () => {
  const g = chord(0, 'g', 1000, ALL)
  expect(g).toEqual({ pending: 1000, go: null })
  expect(chord(g.pending, 'p', 1800, ALL)).toEqual({ pending: 0, go: 'flow/plan' })
  expect(chord(g.pending, 'a', 1800, ALL)).toEqual({ pending: 0, go: 'docs/decisions' })
  expect(chord(g.pending, 'a', 1800, ['flow'])).toEqual({ pending: 0, go: null })
  expect(chord(g.pending, 'p', 3000, ALL).go).toBeNull()
  expect(chord(0, 'p', 1000, ALL).go).toBeNull()
  expect(chord(g.pending, 'x', 1200, ALL)).toEqual({ pending: 0, go: null })
  expect(chord(g.pending, 'g', 1200, ALL)).toEqual({ pending: 1200, go: null })
})

test('a section this window does not have is no shortcut', () => {
  const without = ALL.filter((s) => s !== 'kitdev')
  expect(chord(1000, 'k', 1100, without).go).toBeNull()
})

test('keys typed into a field or a dialog are text, not shortcuts', () => {
  const el = (tagName, more = {}) => ({ tagName, isContentEditable: false, closest: () => null, ...more })
  expect(typing(el('INPUT'))).toBe(true)
  expect(typing(el('TEXTAREA'))).toBe(true)
  expect(typing(el('SELECT'))).toBe(true)
  expect(typing(el('DIV', { isContentEditable: true }))).toBe(true)
  expect(typing(el('BUTTON', { closest: (s) => (s === 'dialog' ? {} : null) }))).toBe(true)
  expect(typing(el('A'))).toBe(false)
  expect(typing(null)).toBe(false)
})

const cmd = (name, zone, more = {}) => ({ name, zone, verdict: 'app', es: `es ${name}`, en: `en ${name}`, ...more })

test('the sections with their shortcut, the other projects that exist, the actions and the reachable commands', () => {
  const groups = entries({
    sections: ['flow', 'quality', 'settings'], t, lang: 'es',
    projects: [{ name: 'api', path: '/a', exists: true, current: true }, { name: 'web', path: '/w', exists: true },
      { name: 'old', path: '/o', exists: false }],
    commands: [cmd('doctor', 'check'), cmd('radar', 'analyze'), cmd('confirm', 'generate', { verdict: 'portal' }),
      cmd('ci', 'team')],
  })
  const by = Object.fromEntries(groups.map((g) => [g.id, g]))
  expect(groups.map((g) => g.id)).toEqual(['sections', 'projects', 'actions', 'commands', 'guide'])
  expect(by.sections.label).toBe('<pal.sections>')
  expect(by.projects.items.map((i) => i.label)).toEqual(['web'])
  expect(by.projects.items[0].project.path).toBe('/w')
  expect(by.actions.items.map((i) => i.id)).toEqual(['read', 'review', 'search', 'add', 'tour'])
  expect(by.actions.items[0].href).toBe('../#/')
  expect(by.commands.items).toEqual([
    { id: 'cmd:doctor', label: 'es doctor', sub: 'camaron doctor', href: '#/quality' },
    { id: 'cmd:radar', label: 'es radar', sub: 'camaron radar', href: '#/quality/radar' },
  ])
})

test('the sections group lists each section, then its other views', () => {
  const ids = (sections) => entries({ sections, t }).find((x) => x.id === 'sections').items.map((i) => i.id)
  expect(ids(['flow', 'quality', 'docs'])).toEqual(['go:flow', 'go:flow/plan', 'go:quality', 'go:quality/sonar', 'go:quality/libs', 'go:docs',
    'go:docs/wikis', 'go:docs/decisions', 'go:docs/interviews'])
  const items = entries({ sections: ['flow'], t }).find((x) => x.id === 'sections').items
  expect(items[0]).toEqual({ id: 'go:flow', label: '<nav.flow>', keys: ['g', 'f'], href: '#/flow' })
  expect(items[1]).toEqual({ id: 'go:flow/plan', label: '<nav.plan>', sub: '<nav.flow>', href: '#/flow/plan' })
})

test('commands go to the place that holds them', () => {
  const hrefs = Object.fromEntries(entries({ sections: ALL, t, commands: [cmd('radar', 'analyze'), cmd('ci', 'team'),
    cmd('run', 'generate'), cmd('trust', 'team'), cmd('skills', 'team'), cmd('repair', 'machine')] }).find((x) => x.id === 'commands').items.map((i) => [i.id, i.href]))
  expect(hrefs).toEqual({ 'cmd:radar': '#/quality/radar', 'cmd:ci': '#/docs/ci', 'cmd:run': '#/flow/plan',
    'cmd:trust': '#/settings/trust', 'cmd:skills': '#/settings/skills', 'cmd:repair': '#/settings/kit' })
})

test('with no query, everything but the commands; typing finds them too', () => {
  const groups = entries({ sections: ['flow', 'settings'], t: (k) => ({ 'nav.settings': 'Máquina' })[k] || k, lang: 'es',
    commands: [cmd('setup', 'machine', { es: 'Preparar la máquina' }), cmd('version', 'machine', { es: 'Versión' })] })
  expect(pick(groups, '').map((g) => g.id)).toEqual(['sections', 'actions'])
  const found = pick(groups, 'maquina')                              // accents and case aside
  expect(found.map((g) => [g.id, g.items.map((i) => i.label)])).toEqual([
    ['sections', ['Máquina', 'nav.tokens', 'nav.skills', 'nav.plugins', 'nav.trust', 'nav.kit']], ['commands', ['Preparar la máquina']]])
})

test('every word must match, in the label or its hint; labels that start with the query come first', () => {
  const groups = [{ id: 'commands', label: 'C', items: [
    { id: 'a', label: 'Revisar el radar', sub: 'camaron radar' },
    { id: 'b', label: 'Radar de tecnologías', sub: 'camaron radar' },
    { id: 'c', label: 'Doctor', sub: 'camaron doctor' }] }]
  expect(pick(groups, 'radar')[0].items.map((i) => i.id)).toEqual(['b', 'a'])
  expect(pick(groups, 'camaron doc')[0].items.map((i) => i.id)).toEqual(['c'])
  expect(pick(groups, 'zzz')).toEqual([])
})

test('the guide chapters show once you type, like the commands', () => {
  const guide = [{ id: 'guide:app/plan', label: 'Plan', sub: 'The app', href: '#/guide/app/plan' }]
  const groups = entries({ sections: ALL, t, guide })
  expect(pick(groups, '').map((g) => g.id)).not.toContain('guide')
  const found = pick(groups, 'plan').find((g) => g.id === 'guide')
  expect(found.label).toBe('<pal.guide>')
  expect(found.items).toEqual(guide)
})

test('the palette finds the libraries by name', () => {
  const groups = entries({ sections: ['quality'], t: (k) => ({ 'nav.libs': 'Librerías' })[k] || k })
  expect(pick(groups, 'librerias').map((g) => g.id)).toEqual(['sections'])
  expect(pick(groups, 'librerias')[0].items.map((i) => i.id)).toEqual(['go:quality/libs'])
})

import { expect, test } from 'vitest'
import { NO_ICON, skillsView, switchArgs } from './skills.js'

const DATA = {
  skills: [
    { name: 'cam-task', origin: 'kit', icon: '🧭', description: 'Start here', project: 'on', machine: 'on', needs_trust: false, pack: null },
    { name: 'ponytail', origin: 'team-only', icon: '🪮', description: 'Lazy', project: 'on', machine: 'off', needs_trust: true, pack: 'ponytail' },
    { name: 'our-review', origin: 'team-only', icon: '', description: '', project: 'off', machine: 'on', needs_trust: false, pack: null },
  ],
  available: [{ name: 'impeccable', title: 'Impeccable', icon: '🎨', summary: { en: 'Frontend design', es: 'Diseño frontend' },
    license: 'Apache-2.0', runs_code: true, skills: ['impeccable'] }],
}

test('rows carry the icon, where the skill came from and both switches', () => {
  const { rows } = skillsView(DATA)
  expect(rows.map((r) => [r.name, r.icon, r.origin, r.project, r.machine, r.waiting])).toEqual([
    ['cam-task', '🧭', 'tm.skKit', true, true, false],
    ['ponytail', '🪮', 'tm.skPack', true, false, true],
    ['our-review', NO_ICON, 'tm.skTeamOnly', false, true, false],
  ])
})

test('a pack reads in the app language, English when the catalog has no line in it', () => {
  expect(skillsView(DATA, 'es').packs[0]).toMatchObject({ title: 'Impeccable', summary: 'Diseño frontend', runsCode: true })
  expect(skillsView(DATA, 'en').packs[0].summary).toBe('Frontend design')
  expect(skillsView({ available: [{ name: 'x', summary: { en: 'Only English' } }] }, 'es').packs[0].summary).toBe('Only English')
  expect(skillsView(null)).toEqual({ rows: [], packs: [] })
})

test('a switch flips its own scope only', () => {
  const [kit, pony] = skillsView(DATA).rows
  expect(switchArgs(kit, 'project')).toEqual({ action: 'disable', args: ['cam-task'] })
  expect(switchArgs(pony, 'machine')).toEqual({ action: 'enable', args: ['ponytail'], machine: true })
})

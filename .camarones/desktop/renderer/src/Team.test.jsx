import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { SkillsList } from './sections/Team.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))

const SKILLS = {
  skills: [
    { name: 'cam-task', origin: 'kit', icon: '🧭', description: 'Start here', project: 'on', machine: 'on', needs_trust: false, pack: null },
    { name: 'ponytail', origin: 'team-only', icon: '🪮', description: 'Lazy', project: 'on', machine: 'off', needs_trust: true, pack: 'ponytail' },
  ],
  available: [{ name: 'impeccable', title: 'Impeccable', icon: '🎨', summary: { en: 'Frontend design', es: 'Diseño frontend' },
    license: 'Apache-2.0', runs_code: true, skills: ['impeccable'] }],
}

test('the skills card shows each skill with its icon, both switches and the packs one can add', () => {
  const out = renderToStaticMarkup(<SkillsList data={SKILLS} />)
  expect(out).toContain('🧭')
  expect(out).toContain('<b>cam-task</b>')
  expect(out).toContain('del kit · Start here')
  expect(out).toContain('pack ponytail · Lazy')
  expect(out).toContain('espera aprobación')
  expect((out.match(/type="checkbox" checked=""/g) || []).length).toBe(3)       // ponytail is off on this machine only
  expect(out).toContain('Solo en Claude Code')
  expect(out).toContain('Packs opcionales')
  expect(out).toContain('Diseño frontend · Apache-2.0 · impeccable')
  expect(out).toContain('ejecuta código')
  expect(out).toContain('Añadir')
  setLang('en')
  const en = renderToStaticMarkup(<SkillsList data={SKILLS} />)
  expect(en).toContain('Frontend design')
  expect(en).toContain('awaits approval')
})

import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { DriftList, HooksReport, QualityViews, SecretsResult } from './sections/Quality.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))

const drift = [
  { path: 'chub/CLAUDE.md', state: 'not linked', what: 'workspace link', why: 'yours' },
  { path: '.claude/skills/cam-docs-unit/SKILL.md', state: 'edited', what: 'kit skill' },
  { path: 'chub/.mcp.json', state: 'not linked', what: 'workspace link', why: 'missing' },
]

test('each kit file that is off says what and why, and whether Repair can fix it', () => {
  const out = renderToStaticMarkup(<DriftList items={drift} repaired={false} />)
  expect(out).toContain('chub/CLAUDE.md')
  expect(out).toContain('Es tuyo: el kit nunca lo reemplaza')
  expect(out).toContain('Editado a mano: Reparar vuelve al texto del kit.')
  expect(out).toContain('Falta el enlace a cam-docs: Reparar lo crea.')
  setLang('en')
  expect(renderToStaticMarkup(<DriftList items={drift} repaired={false} />)).toContain('It is yours: the kit never replaces it')
})

test('after a repair it says plainly what it could not fix', () => {
  const out = renderToStaticMarkup(<DriftList items={drift.slice(2)} repaired />)
  expect(out).toContain('Reparar no ha podido con 1')
})

test('nothing off: it says all is in place', () => {
  expect(renderToStaticMarkup(<DriftList items={[]} repaired />)).toContain('Todo en su sitio')
})

test('a file of the person\'s that stays is not a failure: all is in place, and it is listed as kept', () => {
  const out = renderToStaticMarkup(<DriftList items={drift.slice(0, 1)} repaired />)
  expect(out).toContain('Todo en su sitio')
  expect(out).not.toContain('no ha podido')
  expect(out).toContain('chub/CLAUDE.md')
  expect(out).toContain('se queda como está')
})

// Libraries is a view of Quality, beside the board: two links, the open one marked, never a section of the nav.
test('quality has two views, the board and the libraries, and says which one is open', () => {
  const links = (view) => renderToStaticMarkup(<QualityViews view={view} />).split('</a>').filter((x) => x.includes('<a '))
  const [board, libs] = links('libs')
  expect(board).toContain('href="#/quality"')
  expect(board).not.toContain('aria-current')
  expect(libs).toContain('href="#/quality/libs"')
  expect(libs).toContain('aria-current="page"')
  expect(libs).toContain('Librerías')
  expect(links('health')[0]).toContain('aria-current="page"')
  setLang('en')
  expect(renderToStaticMarkup(<QualityViews view="health" />)).toContain('>Libraries<')
})

test('the secret scan: clean, the places it found (never a value), or a scan that could not run', () => {
  const out = (verdict) => renderToStaticMarkup(<SecretsResult verdict={verdict} />)
  expect(out({ state: 'clean', items: [] })).toContain('Sin secretos')
  const found = out({ state: 'found', items: ['docs/a.md:3: possible secret (aws-key) — remove it or use a placeholder'] })
  expect(found).toContain('Posibles secretos: 1')
  expect(found).toContain('docs/a.md:3')
  const skipped = out({ state: 'skipped', items: ['gitleaks not installed — secret scan skipped'] })
  expect(skipped).toContain('No se ha podido escanear')
  expect(skipped).toContain('gitleaks not installed')
  expect(skipped).not.toContain('Sin secretos')
})

test('the hooks report: what they saw, that nothing was seen yet, and a switched-off gate', () => {
  const rep = { prompts: 12, prompts_with_docs: 9, edit_sessions: 4, consulted_first: 3, stops: 2, share: 0.75 }
  const out = renderToStaticMarkup(<HooksReport r={{ enabled: true, gate: true, report: rep }} />)
  expect(out).toContain('12 prompts (9 con documentación)')
  expect(out).toContain('3 de 4 sesiones')
  expect(out).toContain('75%')
  expect(out).toContain('2 ediciones frenadas')
  expect(out).not.toContain('apagado')
  const none = { prompts: 0, prompts_with_docs: 0, edit_sessions: 0, consulted_first: 0, stops: 0, share: null }
  expect(renderToStaticMarkup(<HooksReport r={{ enabled: true, gate: true, report: none }} />)).toContain('Aún no han visto ninguna sesión')
  expect(renderToStaticMarkup(<HooksReport r={{ enabled: true, gate: false, report: rep }} />)).toContain('apagado')
  expect(renderToStaticMarkup(<HooksReport r={null} />)).toBe('')
})

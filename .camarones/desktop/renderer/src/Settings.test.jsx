import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { SettingsView } from './sections/Settings.jsx'
import { Trust } from './sections/SettingsTeam.jsx'
import { setLang } from './i18n.js'

afterEach(() => { delete globalThis.location; setLang('es') })

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
const M = {
  setup: null, setup_steps: 5, settings: { lang: 'es', model: 'opus', codex_model: '', sessions: 'canvas' },
  models: ['opus'], codex_models: [], sessions: ['canvas', 'window'], agents: [], repos: [{ name: 'api', cloned: true, stack: '' }],
  profile: 'quick', kit: { version: '4.80.0', global: true },
}
const render = (hash, props = {}) => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash }
  const view = hash.replace(/^#\/settings\/?/, '').split('?')[0] || 'general'
  return renderToStaticMarkup(<SettingsView view={view} m={M} pending={0} fill={{ host: '', kind: '' }} srv={srv} jobs={null} app={{}} {...props} />)
}

test('General is the current tab and holds the guide, setup, session settings and repos', () => {
  const out = render('#/settings')
  expect(out).toMatch(/aria-current="page"[^>]*>General</)
  for (const tour of ['mc-guide', 'mc-setup', 'mc-settings', 'mc-repos']) expect(out).toContain(`data-tour="${tour}"`)
  expect(out).not.toContain('data-tour="mc-tokens"')
  expect(out).not.toContain('data-tour="mc-kit"')
})

test('before the machine read arrives, General still shows the guide card and a skeleton', () => {
  const out = render('#/settings', { m: null })
  expect(out).toContain('data-tour="mc-guide"')
  expect(out).toContain('cu-skel')
})

test('Tokens is prefilled from the address and says where the user came from', () => {
  const out = render('#/settings/tokens?host=sonar.example.com&kind=sonarqube', { fill: { host: 'sonar.example.com', kind: 'sonarqube' } })
  expect(out).toContain('data-tour="mc-tokens"')
  expect(out).toMatch(/id="tk-host"[^>]*value="sonar.example.com"/)
  expect(out).toMatch(/<option value="sonarqube" selected/)
  expect(out).toContain('Vienes de Calidad: falta el token de sonar.example.com.')
  setLang('en')
  expect(render('#/settings/tokens', { fill: { host: 'h.io', kind: '' } })).toContain('You came from Quality: the token for h.io is missing.')
})

test('Tokens without a prefill shows no notice', () => {
  const out = render('#/settings/tokens')
  expect(out).toContain('data-tour="mc-tokens"')
  expect(out).not.toContain('Vienes de Calidad')
})

test('Kit holds the kit and uninstall cards', () => {
  const out = render('#/settings/kit')
  expect(out).toContain('data-tour="mc-kit"')
  expect(out).toContain('data-tour="mc-uninstall"')
})

test('the Trust tab carries the pending count', () => {
  expect(render('#/settings', { pending: 2 })).toContain('Confianza · 2')
  expect(render('#/settings')).not.toContain('Confianza ·')
})

test.each([['skills', 'team-skills'], ['plugins', 'team-plugins'], ['trust', 'team-trust']])('%s renders its card', (view, tour) => {
  const out = render(`#/settings/${view}`)
  expect(out).toContain(`data-tour="${tour}"`)
})

const find = (el, type) => (Array.isArray(el) ? el.flatMap((x) => find(x, type)) : el?.props ? [...(el.type === type ? [el] : []), ...find(el.props.children, type)] : [])

test('an approval in the Trust card reaches the tab count through onChange', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/settings/trust' }
  let bumps = 0
  const tree = SettingsView({ view: 'trust', m: M, pending: 2, fill: { host: '', kind: '' }, srv, jobs: null, app: {}, onSkillsChange: () => { bumps++ } })
  const [card] = find(tree, Trust)
  card.props.onChange()
  expect(bumps).toBe(1)
})

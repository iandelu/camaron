import { expect, test } from 'vitest'
import { inPanel, others, sectionFor, wantedCommand, ZONES } from './catalog.js'

const c = (name, zone, more = {}) => ({ name, zone, verdict: 'app', destructive: false, ...more })
const names = (cmds, place) => { const o = others(cmds, place); return [...o.safe, ...o.careful].map((x) => x.name) }

test('each place reads the catalog zones of its work', () => {
  expect(ZONES).toEqual({ 'flow/plan': ['generate'], quality: ['check', 'analyze'], docs: ['team', 'interviews'], settings: ['machine'] })
})

test('quality and settings leave out what their panels run', () => {
  const cmds = ['doctor', 'eval', 'ab', 'inventory', 'fresh', 'blocks', 'check', 'radar'].map((n) => c(n, n === 'radar' ? 'analyze' : 'check'))
  expect(names(cmds, 'quality')).toEqual(['check', 'radar'])
  const m = ['setup', 'config', 'sync', 'detect', 'stack', 'profile', 'repair', 'version'].map((n) => c(n, 'machine'))
  const extra = [c('self-update', 'machine'), c('uninstall', 'machine', { destructive: true }), c('unlink', 'machine', { destructive: true })]
  expect(others([...m, ...extra], 'settings')).toEqual({ safe: [m[7]], careful: [extra[2]] })
})

test('all the commands of a place, but the ones its panels already run; what deletes goes last', () => {
  const cmds = [c('run', 'generate'), c('autopilot', 'generate'), c('wiki', 'generate'), c('pr', 'generate'),
    c('remote', 'team'), c('ci', 'team'), c('confirm', 'generate', { verdict: 'portal' }),
    c('unlink', 'team', { destructive: true })]
  expect(others(cmds, 'flow/plan')).toEqual({ safe: [cmds[2], cmds[3]], careful: [] })
  expect(others(cmds, 'docs')).toEqual({ safe: [cmds[5]], careful: [cmds[7]] })
  expect(others(cmds, 'flow')).toEqual({ safe: [], careful: [] })
  expect(others(null, 'flow/plan')).toEqual({ safe: [], careful: [] })
})

test('docs lists ci but none of the commands that moved to settings or interviews', () => {
  const cmds = ['ci', 'remote', 'share', 'trust', 'plugins', 'skills', 'interview'].map((n) => c(n, n === 'interview' ? 'interviews' : 'team'))
  expect(names(cmds, 'docs')).toContain('ci')
  for (const n of ['remote', 'share', 'trust', 'plugins', 'skills', 'interview']) expect(names(cmds, 'docs')).not.toContain(n)
})

test('where the app runs each command', () => {
  expect(sectionFor(c('doctor', 'check'))).toBe('quality')
  expect(inPanel(c('doctor', 'check'))).toBe(true)
  expect(sectionFor(c('radar', 'analyze'))).toBe('quality')
  expect(inPanel(c('radar', 'analyze'))).toBe(false)
  expect(sectionFor(c('uninstall', 'machine', { destructive: true }))).toBe('settings/kit')
  expect(sectionFor(c('repair', 'machine'))).toBe('settings/kit')                // the Kit card's Repair button
  expect(sectionFor(c('self-update', 'machine'))).toBe('settings/kit')
  expect(sectionFor(c('trust', 'team'))).toBe('settings/trust')
  expect(sectionFor(c('interview', 'interviews'))).toBe('docs/interviews')
  expect(sectionFor(c('run', 'generate'))).toBe('flow/plan')
  expect(sectionFor(c('confirm', 'generate', { verdict: 'portal' }))).toBeNull()
  expect(sectionFor(c('up', 'docs'))).toBeNull()
  expect(sectionFor(c('radar', 'analyze'), ['flow', 'quality'])).toBe('quality')
  expect(sectionFor(c('radar', 'analyze'), ['flow'])).toBeNull()
})

test('the method hooks are a panel of quality', () => {
  expect(sectionFor(c('hooks', 'team'))).toBe('quality')
  expect(inPanel(c('hooks', 'team'))).toBe(true)
  const cmds = [c('hooks', 'team'), c('ci', 'team')]
  expect(names(cmds, 'docs')).toEqual(['ci'])
  expect(names(cmds, 'quality')).toEqual([])
})

test('the secret scan is `check --secrets`: the full check stays in the folded list', () => {
  expect(names([c('check', 'check')], 'quality')).toEqual(['check'])
})

test('the wanted command is the segment after the place, unless it is a view', () => {
  expect(wantedCommand('#/quality/radar', 'quality')).toBe('radar')
  expect(wantedCommand('#/quality/libs', 'quality')).toBeNull()
  expect(wantedCommand('#/flow/plan/plan', 'flow/plan')).toBe('plan')
  expect(wantedCommand('#/docs/decisions/0012', 'docs')).toBeNull()
  expect(wantedCommand('#/settings', 'settings')).toBeNull()
})

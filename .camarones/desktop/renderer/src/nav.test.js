import { expect, test } from 'vitest'
import { firstRunPending, firstRunRoute, initials, LIBS, MACHINE, movedRoute, placeOf, PLACES, PROJECT, sectionOf, sections, repoHref, repoOf, repoPage, termOf, tokenNotice, tokenPrefill, viewOf, withRepo } from './nav.js'

test('a project has four places; this machine has its own, Kit dev only in a kit checkout', () => {
  expect(PROJECT).toEqual(['flow', 'board', 'quality', 'docs'])
  expect(MACHINE).toEqual(['settings', 'guide', 'kitdev'])
  expect(sections({ kitdev: false }).machine).toEqual(['settings', 'guide'])
  expect(sections({ kitdev: true }).machine).toEqual(MACHINE)
  expect(PLACES).toEqual(['flow', 'flow/plan', 'board', 'quality', 'quality/sonar', 'quality/libs', 'docs', 'docs/wikis', 'docs/decisions',
    'docs/interviews', 'settings', 'settings/tokens', 'settings/skills', 'settings/plugins', 'settings/trust', 'settings/kit', 'guide', 'kitdev'])
})

test('the address picks the view of a place; the first view is the default', () => {
  expect(viewOf('#/flow', 'flow')).toBe('summary')
  expect(viewOf('#/flow/plan?term=t-a-1', 'flow')).toBe('plan')
  expect(viewOf('#/quality/radar', 'quality')).toBe('health')            // a command of the fold, not a view
  expect(viewOf('#/docs/decisions/0012', 'docs')).toBe('decisions')
  expect(viewOf('#/settings/tokens?kind=sonarqube', 'settings')).toBe('tokens')
  expect(viewOf('#/board', 'board')).toBe('')
})

test('the address picks the section, old addresses included', () => {
  for (const [h, s] of [['#/flow', 'flow'], ['', 'flow'], ['#/nope', 'flow'], ['#/start', 'start'], ['#/summary', 'flow'],
    ['#/plan?term=t-a-1', 'flow'], ['#/decisions/0012', 'docs'], ['#/interviews', 'docs'], ['#/team', 'docs'],
    ['#/machine?kind=sonarqube', 'settings'], ['#/libs', 'quality'], ['#/guide/app/plan', 'guide']]) expect(sectionOf(h, {}), h).toBe(s)
  expect(sectionOf('#/kitdev', { kitdev: true })).toBe('kitdev')
  expect(sectionOf('#/kitdev', { kitdev: false })).toBe('flow')
})

test('start is a known section, not in the nav', () => {
  expect([...PROJECT, ...MACHINE]).not.toContain('start')
})

test('a place is the section, plus its view when it is not the default (the tours follow it)', () => {
  expect(LIBS).toBe('quality/libs')
  for (const [h, p] of [['#/flow', 'flow'], ['#/flow/plan', 'flow/plan'], ['#/plan', 'flow/plan'], ['#/quality/libs', 'quality/libs'],
    ['#/libs', 'quality/libs'], ['#/quality/radar', 'quality'], ['#/docs/decisions/new', 'docs/decisions'],
    ['#/machine?kind=sonarqube', 'settings/tokens'], ['#/board', 'board']]) expect(placeOf(h, {}), h).toBe(p)
})

test('an old address is rewritten to its new place, anything after it kept; nothing else moves', () => {
  for (const [from, to] of [['#/summary', '#/flow'], ['#/plan', '#/flow/plan'], ['#/plan?term=t-a-1', '#/flow/plan?term=t-a-1'],
    ['#/plan/unit-x', '#/flow/plan/unit-x'], ['#/decisions/0012', '#/docs/decisions/0012'], ['#/decisions/new', '#/docs/decisions/new'],
    ['#/interviews', '#/docs/interviews'], ['#/team', '#/docs'], ['#/team/ci', '#/docs/ci'], ['#/machine', '#/settings'],
    ['#/machine/setup', '#/settings/setup'], ['#/machine?host=gitlab.example.com', '#/settings/tokens?host=gitlab.example.com'],
    ['#/machine?kind=sonarqube&host=x', '#/settings/tokens?kind=sonarqube&host=x'], ['#/libs?repo=web', '#/quality/libs?repo=web']])
    expect(movedRoute(from), from).toBe(to)
  for (const h of ['#/flow', '#/quality/libs', '#/plans', '#/libsx', '#/teams', '']) expect(movedRoute(h), h).toBeNull()
})

// Quality links to the Tokens view with the host and the kind to fill in: #/settings/tokens?host=<h>&kind=sonarqube.
test('the tokens address can prefill the token form', () => {
  expect(tokenPrefill('#/settings/tokens?host=https%3A%2F%2Fsonar.example.com&kind=sonarqube')).toEqual({ host: 'https://sonar.example.com', kind: 'sonarqube' })
  expect(tokenPrefill('#/settings/tokens?kind=nope&host=x')).toEqual({ host: 'x', kind: '' })
  expect(tokenPrefill('#/settings/tokens')).toEqual({ host: '', kind: '' })
  expect(tokenPrefill('#/machine?host=x')).toEqual({ host: '', kind: '' })    // the redirect runs first
  expect(tokenPrefill('')).toEqual({ host: '', kind: '' })
})

// Only SonarQube comes from Quality; the forge hosts and a bare host come from a share Docs could not make.
test('the tokens notice names where the prefill came from', () => {
  expect(tokenNotice({ host: 'sonar.io', kind: 'sonarqube' })).toBe('st.fromQuality')
  for (const kind of ['', 'gitlab', 'github']) expect(tokenNotice({ host: 'git.acme', kind }), kind).toBe('st.fromShare')
  expect(tokenNotice({ host: '', kind: 'sonarqube' })).toBeNull()
})

test('an address can ask the Plan for one terminal', () => {
  expect(termOf('#/flow/plan?term=t-explain_api-2')).toBe('t-explain_api-2')
  expect(termOf('#/flow/plan')).toBe(null)
  expect(termOf('#/flow/plan?term=../x')).toBe(null)
  expect(termOf('#/plan?term=t-a-1')).toBe(null)
  expect(termOf('#/board?term=t-a-1')).toBe(null)
})

test('an unfinished first run goes to the wizard; a finished one stays', () => {
  expect(firstRunRoute({ done: false }, '#/flow/plan')).toBe('#/start')
  expect(firstRunRoute({ done: false }, '')).toBe('#/start')
  expect(firstRunRoute({ done: false }, '#/start')).toBeNull()
  expect(firstRunRoute(null, '#/flow/plan')).toBeNull()            // no state (the read failed): stay
  expect(firstRunRoute({ done: true }, '#/flow')).toBeNull()
  expect(firstRunRoute({ done: true }, '')).toBeNull()
})

test('the rail names a project by its initials', () => {
  expect(initials('petclinic')).toBe('PE')
  expect(initials('spring-petclinic-rest')).toBe('SP')
  expect(initials('api pagos')).toBe('AP')
  expect(initials('')).toBe('?')
})

// Someone who left the wizard for another section sees, on the Summary, a way back while the first run is unfinished.
test('the first run is pending only while the state says done: false', () => {
  expect(firstRunPending({ done: false })).toBe(true)
  expect(firstRunPending({ done: true })).toBe(false)
  expect(firstRunPending(null)).toBe(false)                    // no state (the read failed): no notice
  expect(firstRunPending({})).toBe(false)
})

test('the repo page is a view of Flow that is not a place; ?repo= names a repo', () => {
  expect(viewOf('#/flow/repo/api', 'flow')).toBe('repo')
  expect(placeOf('#/flow/repo/api', {})).toBe('flow/repo')
  expect(PLACES).not.toContain('flow/repo')
  expect(repoOf('#/board?repo=api')).toBe('api')
  expect(repoOf('#/docs/decisions?repo=my.repo-2&x=1')).toBe('my.repo-2')
  expect(repoOf('#/board?repo=%3Cscript%3E')).toBe('')
  expect(repoOf('#/board')).toBe('')
  expect(repoPage('#/flow/repo/api')).toBe('api')
  expect(repoPage('#/flow/repo/my.repo')).toBe('my.repo')
  expect(repoPage('#/flow/repo/..%2Fx')).toBeNull()
  expect(repoPage('#/flow/repo/')).toBeNull()
  expect(repoPage('#/flow')).toBeNull()
  expect(repoHref('a b')).toBe('#/flow/repo/a%20b')
  expect(withRepo('quality/sonar', 'api')).toBe('#/quality/sonar?repo=api')
})

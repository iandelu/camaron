import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import Start, { JoinRepos, Setup, Steps, Tools, closeFirstRun } from './sections/Start.jsx'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }

// Sketch C: one row of steps, the current one marked, the finished ones ticked, the rest numbered.
test('the step row marks where the first run stands', () => {
  const out = renderToStaticMarkup(<Steps steps={['repos', 'tools', 'setup', 'intro']} at={2} done={false} />)
  expect(out).toContain('<li class="done">✔ Repos</li>')
  expect(out).toContain('<li class="done">✔ Herramientas</li>')
  expect(out).toContain('<li class="current" aria-current="step">3. Instalar</li>')
  expect(out).toContain('<li class="future">4. Listo</li>')
  const all = renderToStaticMarkup(<Steps steps={['tools', 'setup', 'intro']} at={2} done />)
  expect(all.match(/class="done"/g)).toHaveLength(3)
})

// A failed tools read is not a dead end (join starts on tools, with no Back): it says so and offers Retry, on the
// tools step and on the install step, which needs the same list.
test('a failed tools read says so and offers Retry, never a skeleton for good', () => {
  for (const out of [renderToStaticMarkup(<Tools tools={null} picked={[]} setPicked={() => {}} error="boom" onRetry={() => {}} />),
    renderToStaticMarkup(<Setup srv={srv} jobs={null} tools={null} picked={null} repos={[]} state={{ result: null, running: false }}
      setState={() => {}} reloadTools={() => {}} error="boom" />)]) {
    expect(out).toContain('role="alert"')
    expect(out).toContain('No he podido leer las herramientas de esta máquina')
    expect(out).toContain('boom')
    expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--secondary cu-btn--sm">Reintentar<\/button>/)
    expect(out).not.toContain('aria-busy')
  }
  // still loading: the skeleton
  expect(renderToStaticMarkup(<Tools tools={null} picked={[]} setPicked={() => {}} />)).toContain('aria-busy="true"')
})

// The icon-only buttons (the stack's edit) carry their name; the icons themselves are hidden from assistive tech.
test('an icon never stands alone without a name', () => {
  const src = readFileSync(new URL('./sections/Start.jsx', import.meta.url), 'utf-8')
  // a button whose opening tag is followed by an icon and nothing else (a labelled one has its text in between)
  const iconOnly = src.split(/<(?:button|Button)\b/).slice(1).map((b) => b.split(/<\/(?:button|Button)>/)[0])
    .filter((b) => />\s*<\w+Icon \/>\s*$/.test(b))
  expect(iconOnly.length).toBeGreaterThan(0)
  for (const b of iconOnly) expect(b).toMatch(/aria-label=/)
  expect(src).toMatch(/'aria-hidden': true/)
})

test('the wizard waits for its state with a skeleton', () => {
  const out = renderToStaticMarkup(<Start srv={srv} jobs={null} app={{}} />)
  expect(out).toContain('aria-busy="true"')
})

// A reload that fails AFTER an install leaves the old list on screen: the error and Retry show anyway (a stale list
// must not pass for the current one).
test('a failed tools reload with a stale list still says so and offers Retry', () => {
  const tools = { rows: [{ id: 'git', kind: 't_required', ok: true, label: 'git' }], required_ok: true }
  for (const out of [renderToStaticMarkup(<Tools tools={tools} picked={[]} setPicked={() => {}} error="boom" onRetry={() => {}} />),
    renderToStaticMarkup(<Setup srv={srv} jobs={null} tools={tools} picked={[]} repos={[]} state={{ result: { ok: true }, running: false }}
      setState={() => {}} reloadTools={() => {}} error="boom" />)]) {
    expect(out).toContain('role="alert"')
    expect(out).toContain('boom')
    expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--secondary cu-btn--sm">Reintentar<\/button>/)
  }
  // no error: the list alone
  expect(renderToStaticMarkup(<Tools tools={tools} picked={[]} setPicked={() => {}} />)).not.toContain('role="alert"')
})

// The window skipped its catch-up while the first run was ahead: closing the first run brings in the team's work then.
test('closing the first run catches up with the team', async () => {
  const posts = []
  let refreshed = 0
  const srv = { post: (path) => { posts.push(path); return Promise.resolve({}) } }
  await closeFirstRun(srv, { refresh: () => { refreshed += 1 } })
  expect(posts).toEqual(['app/onboard/done', 'app/catch-up'])
  expect(refreshed).toBe(1)
})

test('a refused close does not catch up, and a failed catch-up does not fail the close', async () => {
  const posts = []
  const refused = { post: (path) => { posts.push(path); return Promise.reject(new Error('step')) } }
  await expect(closeFirstRun(refused, { refresh: () => {} })).rejects.toThrow('step')
  expect(posts).toEqual(['app/onboard/done'])
  const flaky = { post: (path) => (path === 'app/catch-up' ? Promise.reject(new Error('busy')) : Promise.resolve({})) }
  await expect(closeFirstRun(flaky, { refresh: () => {} })).resolves.toBeUndefined()
})


test('a join: the repos step is read-only and Continue never posts the team\'s list', () => {
  const src = readFileSync(new URL('./sections/Start.jsx', import.meta.url), 'utf-8')
  expect(src).toContain("step === 'repos' && !join ? saveRepos : null")
  const out = renderToStaticMarkup(<JoinRepos srv={srv} app={{}} />)
  expect(out).toContain('Repos del equipo en esta máquina')
  expect(out).toContain('Buscar en otra carpeta…')
})

test('a join\'s tools step says what leaving a tool out costs, only on this machine', () => {
  const rows = [{ id: 'openwiki', kind: 't_kit', label: 'OpenWiki', ok: false, sys: false, rec: true, found: '', note: '' }]
  const out = renderToStaticMarkup(<Tools tools={{ rows }} picked={[]} setPicked={() => {}} join />)
  expect(out).toContain('Sin OpenWiki esta máquina no puede generar wikis')
  expect(renderToStaticMarkup(<Tools tools={{ rows }} picked={['openwiki']} setPicked={() => {}} join />))
    .not.toContain('Sin OpenWiki')
  expect(renderToStaticMarkup(<Tools tools={{ rows }} picked={[]} setPicked={() => {}} />)).not.toContain('Sin OpenWiki')
})

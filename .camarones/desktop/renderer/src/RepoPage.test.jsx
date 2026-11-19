import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { gateWord, stateWord, uiText } from '@camaron/ui'
import { RepoBento } from './sections/RepoPage.jsx'
import { S, setLang } from './i18n.js'

afterEach(() => setLang('es'))

const es = (k) => uiText(k, 'es')
const NOW = Date.parse('2026-11-19T12:00:00Z')
const secondsAgo = (h) => Math.floor((NOW - h * 3600e3) / 1000)
const WEEKS = ['2026-08-31', '2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28', '2026-10-05', '2026-10-12', '2026-10-19',
  '2026-10-26', '2026-11-02', '2026-11-09', '2026-11-16']
const COMMITS = [2, 3, 1, 4, 2, 5, 3, 2, 4, 3, 1, 4]

const data = {
  name: 'api', cloned: true, state: 'bad', at: '2026-11-19T11:55:00Z',
  head: { branch: 'main', sha: 'a1b2c3d', at: secondsAgo(2), subject: 'Límite de peticiones en el gateway', author: 'Ana' },
  stack: [{ role: 'language', label: 'Java 17' }, { role: 'framework', label: 'Spring Boot 3.3' }, { role: 'build', label: 'Maven' },
    { role: 'data', label: 'PostgreSQL' }, { role: 'container', label: 'Docker' }, { role: 'ci', label: 'GitHub Actions' }],
  build: 'maven',
  sonar: { source: 'sonar', gate: 'OK', coverage: 78, coverageSource: 'sonar', coverageAt: '2026-11-19T11:55:00Z', bugs: 3,
    vulnerabilities: 0, debtMinutes: 540, link: 'https://sonar.example/dashboard?id=api', host: 'sonar.example', connect: false, error: null },
  trend: [70, 71, 71, 73, 74, 74, 76, 78].map((coverage, i) => ({ at: `2026-11-${String(10 + i).padStart(2, '0')}T09:00:00Z`, coverage })),
  activity: { weeks: WEEKS.map((start, i) => ({ start, n: COMMITS[i] })), total: 34, people: 4,
    last: { author: 'Ana', at: secondsAgo(2), subject: 'Límite de peticiones en el gateway' } },
  libs: { total: 5, vulns: { high: 1, medium: 1 }, scanned: true, outdated: 4 },
  docs: { total: 12, fresh: 9, suspect: 2, stale: 1 },
  wiki: { pages: 42, at: '2026-11-17T10:00:00Z', stale: false, chosen: true, unit: 'wiki-api' },
  c4: { fqn: 'petclinic.api', title: 'api', technology: 'Spring Cloud Gateway', in: [{ fqn: 'petclinic.browser', title: 'Navegador' }],
    out: [{ fqn: 'petclinic.customers', title: 'customers-service' }, { fqn: 'petclinic.vets', title: 'vets-service' }] },
  graph: 214,
  work: { columns: [{ status: 'Backlog', n: 1 }, { status: 'Ready', n: 1 }, { status: 'In Progress', n: 1 }, { status: 'In Review', n: 1 },
    { status: 'Done', n: 1 }, { status: 'Blocked', n: 1 }], total: 6 },
  adrs: [{ id: '0009', title: 'Separar la consulta de citas', chip: 'proposed', status: 'proposed' },
    { id: '0008', title: 'Límite de peticiones con Redis', chip: 'accepted', status: 'accepted' }],
}

const noop = () => {}
const render = (o = {}, onPortal = noop) => renderToStaticMarkup(<RepoBento data={{ ...data, ...o }} now={NOW} onPortal={onPortal} />)

// The bento's own handlers, fired with no DOM: the first element `hit` picks, function components drawn by hand.
function drawn(node, hit) {
  if (Array.isArray(node)) { for (const n of node) { const found = drawn(n, hit); if (found) return found } return null }
  if (!node?.type) return null
  if (hit(node)) return node
  if (typeof node.type !== 'function') return drawn(node.props?.children, hit)
  return drawn(node.type(node.props), hit)
}
const words = (el) => (typeof el === 'string' || typeof el === 'number' ? String(el) : Array.isArray(el) ? el.map(words).join('')
  : el?.props ? words(el.props.children) : '')
const press = (label) => {
  const asked = []
  const bento = <RepoBento data={data} now={NOW} onPortal={(h) => asked.push(h)} />
  const button = drawn(bento, (n) => n.type === 'button' && words(n) === label)
  expect(button, label).toBeTruthy()
  button.props.onClick()
  return asked
}

test('the header names the repo, its state with its word, the branch and the stack read from the code', () => {
  const out = render()
  expect(out).toMatch(/<a [^>]*href="#\/flow"[^>]*>← Resumen<\/a>/)
  expect(out).toMatch(/<h1[^>]*>api<\/h1>/)
  expect(out).toContain(`<span class="cu-chip cu-chip--bad">${stateWord('code', 'bad', es)}</span>`)
  expect(out).toMatch(/rama <code>main<\/code>/)
  expect(out).toContain('último commit hace 2 h')
  expect(out).toContain('salud hace 5 min')
  for (const [role, label] of [['Lenguaje', 'Java 17'], ['Framework', 'Spring Boot 3.3'], ['Build', 'Maven'], ['Datos', 'PostgreSQL'],
    ['Contenedor', 'Docker'], ['CI', 'GitHub Actions']]) expect(out).toContain(`${role}</span><b>${label}</b>`)
})

test('every tile with a window links to it, filtered to the repo', () => {
  const out = render()
  for (const href of ['#/quality/sonar?repo=api', '#/quality/libs?repo=api', '#/docs/wikis?repo=api', '#/board?repo=api',
    '#/docs/decisions?repo=api']) expect(out, href).toContain(`href="${href}"`)
})

test('the SonarQube tile: coverage, the gate with its word, the trend and the figures, and where they live', () => {
  const out = render()
  expect(out).toContain('78 %')
  expect(out).toContain(`<span class="cu-chip cu-chip--ok">${gateWord('OK', es)}</span>`)
  expect(out).toContain('+8 puntos en 8 lecturas')
  expect(out).toMatch(/<svg class="cu-spark"[^>]*aria-label="[^"]*70 %[^"]*78 %"/)
  expect(out).toMatch(/Bugs<\/dt><dd>3<\/dd>/)
  expect(out).toMatch(/Deuda<\/dt><dd>1 d 1 h<\/dd>/)
  expect(out).toMatch(/<a class="dk-tile s4"[^>]*href="#\/quality\/sonar\?repo=api"[\s\S]*?Calidad › SonarQube →<\/span><\/a>/)
})

test('an estimated repo says so and where its coverage came from, with no gate', () => {
  const out = render({ sonar: { ...data.sonar, source: 'estimated', gate: null, coverage: 64, coverageSource: 'report', bugs: null,
    vulnerabilities: null, debtMinutes: null } })
  expect(out).toContain('Estimado')
  expect(out).toContain('64 %')
  expect(out).toContain('informe')
  expect(out).not.toContain(gateWord('OK', es))
})

test('one reading draws no trend and says why; no snapshot sends to Quality', () => {
  const few = render({ trend: [data.trend[7]] })
  expect(few).toContain(S.es['rp.trendFew'])
  expect(few).not.toContain('cu-spark')
  const none = render({ sonar: null })
  expect(none).toContain(S.es['rp.noHealth'])
  expect(none).toMatch(/href="#\/quality"[^>]*>Hacerla en Calidad</)
  expect(none).not.toContain('href="#/quality/sonar?repo=api"')
})

test('the Activity tile: twelve weekly bars with their numbers, and the last commit', () => {
  const out = render()
  const label = out.match(/<div class="cu-bars" role="img" aria-label="([^"]*)"/)?.[1]
  expect(label).toContain('34')
  expect(label).toContain('12')
  expect(out.match(/class="cu-bars-col"/g)).toHaveLength(12)
  expect(out).toContain('34 commits en 12 semanas · 4 personas')
  expect(out).toContain('«Límite de peticiones en el gateway» · Ana · hace 2 h')
  const none = render({ activity: null })
  expect(none).toContain(S.es['rp.noGit'])
  expect(none).not.toContain('cu-bars')
})

test('the Libraries tile: vulnerabilities by severity with their words, and how many libraries', () => {
  const out = render()
  expect(out).toContain('cu-hbars')
  const rows = [...out.matchAll(/cu-hbars-label">([^<]*)<[\s\S]*?cu-hbars-n">(\d+)</g)].map((m) => [m[1], m[2]])
  expect(rows).toEqual([['Crítica', '0'], ['Alta', '1'], ['Media', '1'], ['Baja', '0']])
  expect(out).toContain('<span class="cu-chip cu-chip--bad">2 vulnerabilidades</span>')
  expect(out).toContain('De 5 librerías · 4 con versión nueva')
  expect(out).toMatch(/Calidad › Librerías →<\/span><\/a>/)
  const never = render({ libs: { ...data.libs, scanned: false } })
  expect(never).toContain(S.es['rp.libsNever'])
  expect(never).not.toContain('cu-hbars')
})

test('the Documentation tile: its pages by freshness, the wiki, and Review opens the portal', () => {
  const out = render()
  expect(out).toMatch(/>12<\/b><span[^>]*>páginas del repo</)
  expect(out).toContain('cu-seg')
  for (const [w, n] of [['al día', 9], ['por revisar', 2], ['desactualizadas', 1]]) expect(out).toContain(`</span>${w}<span class="cu-legend-n">${n}<`)
  expect(out).toMatch(/href="#\/docs\/wikis\?repo=api"[^>]*>Wiki · 42 páginas →</)
  expect(out).toMatch(/<button[^>]*>Revisar 3 ↗<\/button>/)
  expect(out).not.toMatch(/<a [^>]*>Revisar/)
  expect(press('Revisar 3 ↗')).toEqual(['#/review'])
})

test('the Architecture tile: who calls the repo, the repo itself, what it calls, and the portal\'s C4 and graph', () => {
  const out = render()
  expect(out).toContain('<div class="dk-rp-c4" role="img" aria-label="api: lo llaman Navegador; llama a customers-service, vets-service">')
  const boxes = out.slice(out.indexOf('<div class="dk-rp-c4"')).replace(/^<[^>]*>/, '')
  const me = boxes.indexOf('dk-rp-node me')
  expect(boxes.indexOf('Navegador')).toBeLessThan(me)
  expect(boxes).toMatch(/dk-rp-node me"[^>]*><b>api<\/b><span>Spring Cloud Gateway · este repo<\/span>/)
  expect(me).toBeLessThan(boxes.indexOf('customers-service'))
  expect(me).toBeLessThan(boxes.indexOf('vets-service'))
  expect(out).toContain('214 nodos en el grafo de código')
  expect(press('Ver el C4 ↗')).toEqual(['#/c4'])
  expect(press('Ver el grafo ↗')).toEqual(['#/code/api/graph'])
  expect(render({ c4: null })).toContain(S.es['rp.noC4'])
})

test('the Work tile: the cards by column with their words, and the decisions that name the repo', () => {
  const out = render()
  expect(out).toContain('6 tarjetas tocan este repo')
  expect(out).toContain('cu-seg')
  for (const w of ['Por hacer', 'Haciendo', 'Revisión', 'Hecho', 'Bloqueadas']) expect(out).toContain(`</span>${w}<span class="cu-legend-n">`)
  for (const s of ['0009', 'Separar la consulta de citas', '0008', 'Límite de peticiones con Redis']) expect(out).toContain(s)
  expect(out).toMatch(/href="#\/board\?repo=api"[^>]*>Tablero →</)
  expect(out).toMatch(/href="#\/docs\/decisions\?repo=api"[^>]*>Docs › Decisiones →</)
  expect(render({ work: { columns: [], total: 0 }, adrs: [] })).toContain(S.es['rp.noWork'])
})

test('a repo not cloned here says so in the header and shows no stack', () => {
  const out = render({ cloned: false })
  expect(out).toContain(S.es['rp.notCloned'])
  expect(out).not.toContain('dk-rp-pill')
  expect(out).not.toContain('Java 17')
})

test('the page speaks English too', () => {
  setLang('en')
  const out = render()
  expect(out).toContain('← Summary')
  expect(out).toContain('branch <code>main</code>')
  expect(out).toContain('last commit 2 h ago')
  expect(out).toContain('6 cards touch this repo')
})

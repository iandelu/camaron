import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test, vi } from 'vitest'
import { Button } from '@camaron/ui'
import { CatchUpNote, FirstRunNotice } from './sections/Summary.jsx'
import { TerminalButton } from './sections/TeamStrip.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))

// While the first run is unfinished, the Summary offers the way back to the wizard (#/start), in both languages.
test('an unfinished first run gets a notice with a button back to the wizard', () => {
  const out = renderToStaticMarkup(<FirstRunNotice />)
  expect(out).toContain('El primer arranque del proyecto está a medias.')
  expect(out).toMatch(/<a [^>]*href="#\/start"[^>]*>Seguir con la preparación<\/a>/)
  setLang('en')
  const en = renderToStaticMarkup(<FirstRunNotice />)
  expect(en).toContain('first run is not finished.')
  expect(en).toMatch(/>Continue setting it up<\/a>/)
})

const walk = (node, out = []) => {
  if (!node || typeof node !== 'object') return out
  if (Array.isArray(node)) { node.forEach((n) => walk(n, out)); return out }
  if (node.type === Button) out.push(node)
  else if (node.type === TerminalButton) out.push(node.type(node.props))
  walk(node.props?.children, out)
  walk(node.props?.action, out)
  return out
}

test('a catch-up that hit a conflict warns, names the files and opens a terminal', () => {
  const post = vi.fn().mockResolvedValue({ opened: true })
  const el = CatchUpNote({ srv: { post }, catchUp: { status: 'done', pull: { status: 'conflict', files: ['docs/a.md', 'docs/b.md'] } } })
  const out = renderToStaticMarkup(el)
  expect(out).toContain('chocan con los tuyos en docs/a.md, docs/b.md')
  expect(out).toContain('href="#/docs"')
  expect(out).toContain('>Repo del equipo<')
  expect(out).not.toContain('#/team')
  const term = walk(el).find((b) => b.props.children === 'Abrir una terminal aquí')
  term.props.onClick()
  expect(post).toHaveBeenCalledWith('app/terminal', {})
})

test('an unexplained error warns with its own words and a link to the team strip; pulled is a quiet status line; up to date shows nothing', () => {
  const failed = renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={{ status: 'done', pull: { status: 'error', reason: 'unknown', detail: 'KeyError: odd' } }} />)
  expect(failed).toContain('No he podido traer los cambios del equipo.')
  expect(failed).toContain('KeyError: odd')
  expect(failed).not.toContain('No llego al repo')
  expect(failed).not.toContain('Abrir una terminal')
  const pulled = renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={{ status: 'done', pull: { status: 'pulled', commits: 3 } }} />)
  expect(pulled).toContain('role="status"')
  expect(pulled).toContain('He traído 3 cambios del equipo.')
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={{ status: 'done', pull: { status: 'up-to-date' } }} />)).toBe('')
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={null} />)).toBe('')
  setLang('en')
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={{ status: 'done', pull: { status: 'pulled', commits: 3 } }} />)).toContain('Brought in 3 changes from the team.')
})

test('changes kept in the stash warn and open a terminal, in both languages', () => {
  const post = vi.fn().mockResolvedValue({ opened: true })
  const el = CatchUpNote({ srv: { post }, catchUp: { status: 'done', pull: { status: 'stashed', files: ['docs/a.md'] } } })
  const out = renderToStaticMarkup(el)
  expect(out).toContain('están a salvo en el stash de git (`git stash list`)')
  walk(el).find((b) => b.props.children === 'Abrir una terminal aquí').props.onClick()
  expect(post).toHaveBeenCalledWith('app/terminal', {})
  setLang('en')
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={{ status: 'done', pull: { status: 'stashed', files: [] } }} />))
    .toContain('they are safe in git&#x27;s stash (`git stash list`). Review them in a terminal.')
})

test('on open, a known reason reads as a share does, with the token to save; a rebase left half way opens a terminal', () => {
  const remote = 'https://git.acme/team/docs.git'
  const net = renderToStaticMarkup(<CatchUpNote srv={{}} remote={remote} catchUp={{ status: 'done', pull: { status: 'error', reason: 'network', detail: '' } }} />)
  expect(net).toContain('No llego a git.acme: revisa la conexión, la VPN o el proxy.')
  const token = renderToStaticMarkup(<CatchUpNote srv={{}} remote={remote} catchUp={{ status: 'done', pull: { status: 'error', reason: 'no-token', host: 'git.acme', detail: '' } }} />)
  expect(token).toContain('href="#/settings/tokens?host=git.acme"')
  const post = vi.fn().mockResolvedValue({ opened: true })
  const el = CatchUpNote({ srv: { post }, catchUp: { status: 'done', pull: { status: 'busy', detail: 'git' } } })
  expect(renderToStaticMarkup(el)).toContain('Hay un rebase o un merge a medias en cam-docs: termínalo o cancélalo en una terminal.')
  walk(el).find((b) => b.props.children === 'Abrir una terminal aquí').props.onClick()
  expect(post).toHaveBeenCalledWith('app/terminal', {})
  const run = renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={{ status: 'done', pull: { status: 'busy', detail: 'run' } }} />)
  expect(run).toContain('role="status"')
  expect(run).toContain('Hay una ejecución del autopiloto usando los docs: trae los cambios del equipo cuando termine.')
  setLang('en')
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={{ status: 'done', pull: { status: 'busy', detail: 'run' } }} />))
    .toContain('An autopilot run is using the docs: bring in the team&#x27;s changes once it ends.')
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={{ status: 'done', pull: { status: 'busy', detail: 'git' } }} />))
    .toContain('A rebase or merge is unfinished in cam-docs: finish or abort it in a terminal.')
})

const repos = (r) => ({ status: 'done', pull: { status: 'up-to-date' }, repos: { here: [], linked: [], missing: [], taken: [], ...r } })

test('a repo of the team that is not on this machine is said with the way to prepare it; linked clones say nothing', () => {
  const out = renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={repos({ missing: ['wallet-adapter', 'web'] })} />)
  expect(out).toContain('Estos repos del equipo no están en esta máquina: wallet-adapter, web.')
  expect(out).toMatch(/<a [^>]*href="#\/settings"[^>]*>Preparar la máquina<\/a>/)
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={repos({ here: ['web'], linked: ['api'] })} />)).toBe('')
  setLang('en')
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={repos({ missing: ['api'] })} />))
    .toContain('This team repo is not on this machine: api.')
})

test('a folder that holds something else where a team repo goes warns and was left alone; it comes after the pull', () => {
  const c = { ...repos({ taken: ['worker'] }), pull: { status: 'pulled', commits: 2 } }
  const out = renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={c} />)
  expect(out.indexOf('He traído 2 cambios del equipo.')).toBeGreaterThanOrEqual(0)
  expect(out.indexOf('La carpeta worker no es el repo del equipo y no la he tocado')).toBeGreaterThan(out.indexOf('He traído 2'))
  expect(out).not.toContain('Preparar la máquina')
  setLang('en')
  expect(renderToStaticMarkup(<CatchUpNote srv={{}} catchUp={repos({ taken: ['worker', 'web'] })} />))
    .toContain('The folders worker, web are not the team&#x27;s repos and I left them as they are')
})

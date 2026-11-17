import { beforeEach, expect, test, vi } from 'vitest'

// The docs index the portal loads: one translated page, one not translated yet, one row from an older kit's export
// (no `i18n_titles` at all).
vi.mock('./docsApi.js', () => ({
  docsGet: async () => ({ project: 'demo', langs: ['es'], docs: [
    { path: 'flows/agent-mcp.md', title: 'Coding agent through MCP', i18n_titles: { es: 'Agente de código por MCP' } },
    { path: 'flows/review.md', title: 'Review and confirm', i18n_titles: {} },
    { path: 'wikis/kit/desktop-app.md', title: 'Desktop app', space: 'wiki' },
  ] }),
}))

const { core, inLang } = await import('./core.js')

beforeEach(async () => {
  globalThis.document = { documentElement: {} }         // the tests run without a page
  core.setLang('')
  await core.reload()
})

test('a row is named in the reader\'s language, else keeps its own title', () => {
  const rows = [{ path: 'a.md', title: 'Orders', i18n_titles: { es: 'Pedidos' } }, { path: 'b.md', title: 'Old row' }]
  expect(inLang(rows, 'es').map((d) => d.title)).toEqual(['Pedidos', 'Old row'])
  expect(inLang(rows, '').map((d) => d.title)).toEqual(['Orders', 'Old row'])
  expect(inLang(rows, 'fr').map((d) => d.title)).toEqual(['Orders', 'Old row'])
})

test('with Español picked, the index (tree, breadcrumb, pager, ⌘K) names pages in Spanish', () => {
  core.setLang('es')
  expect(core.byPath('flows/agent-mcp.md').title).toBe('Agente de código por MCP')
  expect(core.tree().docs.find((d) => d.path === 'flows/agent-mcp.md').title).toBe('Agente de código por MCP')
  expect(core.byPath('flows/review.md').title).toBe('Review and confirm')            // not translated yet
  expect(core.byPath('wikis/kit/desktop-app.md').title).toBe('Desktop app')          // an older export's row
  expect(core.byPath('wikis/kit/desktop-app.md').space).toBe('wiki')
})

test('back to English, the canonical titles return', () => {
  core.setLang('es')
  core.setLang('')
  expect(core.byPath('flows/agent-mcp.md').title).toBe('Coding agent through MCP')
  expect(core.tree().docs.map((d) => d.title)).toEqual(['Coding agent through MCP', 'Review and confirm', 'Desktop app'])
})

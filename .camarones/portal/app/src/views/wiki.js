// A repo wiki's page, pure: which page an address asks for, the wiki's reading order, the pages that link to it.
// rows: api/wikis; rel: the page under wikis/<repo>/ ('' = the wiki's home); titleOf: a page's title in the reader's
// language (the docs index), when it has one.
export function wikiTarget(rows, repo, rel, titleOf = () => undefined) {
  const wiki = (rows || []).find((r) => r.repo === repo) || null
  const nav = wiki?.nav || { home: null, pages: [], backlinks: {} }
  const path = rel ? `wikis/${repo}/${rel}` : nav.home || null
  const title = (p) => titleOf(p) || nav.pages.find((x) => x.path === p)?.title || p.split('/').pop()
  return { wiki, nav, path, order: nav.pages.map((p) => p.path),
    backlinks: (path && nav.backlinks[path] || []).map((p) => ({ path: p, title: title(p) })) }
}

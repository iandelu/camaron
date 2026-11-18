import { sectionOf, viewOf, placeOf } from './nav.js'
import { crumb } from './adr.js'

// The header's breadcrumbs: the project, the place, its view when it is not the default, and the step inside Decisions.
export function crumbs({ hash, project, t, flags = {} }) {
  const root = { label: project || '…', href: '#/flow' }
  const section = sectionOf(hash, flags)
  const place = { label: t('nav.' + section), href: `#/${section}` }
  const view = viewOf(hash, section)
  const isDefault = placeOf(hash, flags) === section
  if (!view || isDefault) return [root, { label: place.label }]
  const inner = view === 'decisions' ? crumb(hash, t) : null
  const viewCrumb = { label: t('nav.' + view), href: `#/${section}/${view}` }
  return inner ? [root, place, viewCrumb, { label: inner }] : [root, place, { label: viewCrumb.label }]
}

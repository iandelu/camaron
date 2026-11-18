import { Page, PlaceContext } from './parts.jsx'
import { VIEWS } from './nav.js'
import { t } from './i18n.js'

const href = (section, view) => (view === VIEWS[section][0] ? `#/${section}` : `#/${section}/${view}`)

export function PlaceTabs({ section, view, badges = {} }) {
  return (
    <nav className="dk-guide-tabs" aria-label={t('place.tabs', { place: t('nav.' + section) })} data-tour={`tabs-${section}`}>
      {VIEWS[section].map((v) => (
        <a key={v} href={href(section, v)} className={'dk-guide-tab' + (v === view ? ' on' : '')} aria-current={v === view ? 'page' : undefined}>
          {t('nav.' + v) + (badges[v] > 0 ? ` · ${badges[v]}` : '')}
        </a>))}
    </nav>
  )
}

export function Place({ section, view, head = null, wide = false, full = false, badges, children }) {
  return (
    <Page title={t('nav.' + section)} wide={wide} full={full}>
      {head}
      <PlaceTabs section={section} view={view} badges={badges} />
      <PlaceContext.Provider value={[t('nav.' + section), t('nav.' + view)]}>{children}</PlaceContext.Provider>
    </Page>
  )
}

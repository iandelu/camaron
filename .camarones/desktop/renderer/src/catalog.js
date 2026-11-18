import places from './places.json'

// Each place's "All commands": the catalog (lib/catalog.py, read from the CLI's parser) of the zones of its work,
// without the commands its own panels already run. What deletes or moves data goes apart, last.
export const ZONES = places.zones
export const PANELS = places.panels

export function others(commands, place) {
  const zones = ZONES[place] || []
  const mine = (commands || []).filter((c) => zones.includes(c.zone) && c.verdict !== 'portal' && !inPanel(c))
  return { safe: mine.filter((c) => !c.destructive), careful: mine.filter((c) => c.destructive) }
}

// Where the app runs a command (the ⌘K palette goes there): the place whose panel runs it, else the one whose "All
// commands" lists it; none for the portal's own commands or a place whose section this window lacks.
export const inPanel = (c) => Object.values(PANELS).some((names) => names.includes(c.name))
export function sectionFor(c, available) {
  if (c.verdict === 'portal') return null
  const p = Object.keys(PANELS).find((k) => PANELS[k].includes(c.name)) || Object.keys(ZONES).find((k) => ZONES[k].includes(c.zone))
  return p && (!available || available.includes(p.split('/')[0])) ? p : null
}

// The command an address names (#/quality/radar), unless that segment is a view of the section. A place that is a view
// itself (flow/plan) has nothing left to clash with.
export function wantedCommand(hash, place) {
  const prefix = `#/${place}/`
  if (!String(hash || '').startsWith(prefix)) return null
  const seg = (hash.slice(prefix.length).match(/^[\w-]+/) || [])[0]
  const views = place.includes('/') ? [] : places.views[place] || []
  return seg && !views.includes(seg) ? seg : null
}

// The Docs section's icons: inline SVG on the 24px grid, drawn in the text colour. Always next to their word.
const svg = { className: 'dk-ico', viewBox: '0 0 24 24', 'aria-hidden': true, fill: 'none', stroke: 'currentColor',
  strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }

const PAGE = 'M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z'
const FOLD = 'M14 2v4a2 2 0 0 0 2 2h4'

const DRAWINGS = {
  none: <><path d={PAGE} /><path d={FOLD} /></>,
  generating: <><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" /></>,
  fresh: <><circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" /></>,
  stale: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
  old: <><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4" /><path d="M8 2v4" /><path d="M3 10h18" /></>,
  failed: <><circle cx="12" cy="12" r="10" /><path d="m15 9-6 6" /><path d="m9 9 6 6" /></>,
  blocked: <><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></>,
  docs: <><path d={PAGE} /><path d={FOLD} /><path d="M10 9H8" /><path d="M16 13H8" /><path d="M16 17H8" /></>,
  wikis: <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20" />,
  c4: <><rect x="3" y="3" width="18" height="18" rx="2" /><rect x="8" y="8" width="8" height="8" rx="1" /></>,
  read: <><path d="M12 7v14" />
    <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" /></>,
  review: <><path d="M12.5 22H18a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v9.5" /><path d={FOLD} />
    <path d="M13.378 15.626a1 1 0 1 0-3.004-3.004l-5.01 5.012a2 2 0 0 0-.506.854l-.837 2.87a.5.5 0 0 0 .62.62l2.87-.837a2 2 0 0 0 .854-.506z" /></>,
  search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
  ci: <><rect x="3" y="3" width="8" height="8" rx="2" /><path d="M7 11v4a2 2 0 0 0 2 2h4" /><rect x="13" y="13" width="8" height="8" rx="2" /></>,
}

export function DocsIcon({ name }) {
  return Object.hasOwn(DRAWINGS, name) ? <svg {...svg}>{DRAWINGS[name]}</svg> : null
}

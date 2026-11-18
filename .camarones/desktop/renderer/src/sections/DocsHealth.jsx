import { Skeleton } from '@camaron/ui'
import { t } from '../i18n.js'
import { DocsIcon } from './DocsIcons.jsx'

// The drawing beside each chip's words, by the chip's key (docs.js docsHealth). The tone is only a tint: the words say it.
const ICONS = { drafts: 'review', reconfirm: 'review', orphans: 'docs', untranslated: 'docs', feedback: 'docs',
  wikiFresh: 'fresh', wikiStale: 'stale', wikiOld: 'old', wikiNone: 'none',
  c4None: 'c4', c4NoModel: 'c4', c4Stale: 'c4', c4Fresh: 'c4' }
export const chipIcon = (key) => ICONS[key]

// The stale-wikis chip points at the first card in that state (WikiCard's data-wiki-state); with none in the page it does nothing.
export const showStale = () => document.querySelector('[data-wiki-state="stale"]')?.scrollIntoView?.({ block: 'nearest' })

// The state of the docs at a glance: `chips` are docsHealth's, `loading` the first read of the wikis (a skeleton, not chips that
// would then jump). Only the stale-wikis chip does something, so only it is a button.
export function DocsHealth({ chips, loading }) {
  return (
    <div className="dk-health" role="status" aria-label={t('docs.h.label')} data-tour="docs-health">
      {loading ? <Skeleton lines={1} />
        : chips.length ? chips.map((c) => <HealthChip key={c.key} chip={c} />)
          : <span className="muted small">{t('docs.h.empty')}</span>}
    </div>
  )
}

function HealthChip({ chip }) {
  const body = <><DocsIcon name={chipIcon(chip.key)} />{t(chip.text, { n: chip.n })}</>
  const cls = `dk-hchip is-${chip.tone}`
  return chip.key === 'wikiStale'
    ? <button type="button" className={cls} onClick={showStale}>{body}</button>
    : <span className={cls}>{body}</span>
}

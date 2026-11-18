import favicon from '../../../../portal/app/public/favicon.svg?raw'
import { shrimpMarkup } from '../shrimp.js'

// A picture only: the words that say what it is doing come from the panel that shows it. The markup is the kit's own
// static favicon, never user input.
const DRAWING = { __html: shrimpMarkup(favicon) }
const STATES = ['idle', 'thinking', 'answering']

export function Shrimp({ state }) {
  const now = STATES.includes(state) ? state : 'idle'
  return (
    <span className="dk-shrimp-box">
      <svg className={`dk-shrimp ${now}`} viewBox="0 0 64 64" aria-hidden="true" dangerouslySetInnerHTML={DRAWING} />
      {now === 'thinking' && <span className="dk-shrimp-dots"><i /><i /><i /></span>}
    </span>
  )
}

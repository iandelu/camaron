import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card } from '@camaron/ui'
import { actOnMiss, readMisses } from '../docs.js'
import { errorLine } from '../onboarding.js'
import { t } from '../i18n.js'

// The questions asked (in the portal's Ask, the docs chat or by agents) that no page answered, read from GET misses on mount and
// again whenever `version` changes (the chat's newest reply that found nothing). Each can go to the open questions of the next
// interview or be dismissed. The card shows nothing while it first reads, when that read failed and when there are no misses;
// `misses` is null until a list lands, and a later read that fails leaves the list it had.
export function DocsMisses({ srv, version = 0 }) {
  const [state, setState] = useState({ misses: null, busy: '', error: '' })
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])
  useEffect(() => {
    let current = true                               // a read overtaken by a newer one does not land
    readMisses(srv, () => current && alive.current, (misses) => setState((s) => ({ ...s, misses: misses ?? s.misses })))
    return () => { current = false }
  }, [version])
  async function act(q, action) {
    setState((s) => ({ ...s, busy: q, error: '' }))
    const done = await actOnMiss(srv, q, action, (e) => errorLine(e, t))
    if (alive.current) setState((s) => ({ misses: done.misses ?? s.misses, busy: '', error: done.error || '' }))
  }
  if (!state.misses?.length) return null
  return <MissesList misses={state.misses} busy={state.busy} error={state.error} onAct={act} />
}

// The card itself: `busy` is the question whose action runs ('' when none). Each answer is the whole list, so while one runs no
// row's buttons answer: two actions at once could land out of order. The buttons repeat per row, so each names its question.
export function MissesList({ misses, busy = '', error = '', onAct }) {
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('docs.misses')}</span>
      <p className="muted small">{t('docs.missesHint')}</p>
      <ul className="dk-misses">
        {misses.map((m) => (
          <li key={m.q} className="dk-miss" aria-busy={busy === m.q ? 'true' : undefined}>
            <span className="dk-miss-q">{m.q}</span>
            <span className="muted small dk-miss-n">×{m.n}</span>
            <Button size="sm" disabled={!!busy} aria-label={`${t('docs.missAdd')}: ${m.q}`} onClick={() => onAct(m.q, 'question')}>{t('docs.missAdd')}</Button>
            <Button size="sm" variant="ghost" disabled={!!busy} aria-label={`${t('docs.missDismiss')}: ${m.q}`}
              onClick={() => onAct(m.q, 'dismiss')}>{t('docs.missDismiss')}</Button>
          </li>
        ))}
      </ul>
      {error ? <Aviso tone="error" title={error} /> : null}
    </Card>
  )
}

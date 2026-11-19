import { useEffect, useRef, useState } from 'react'
import { Chip, Skeleton, fmtAgo, uiText } from '@camaron/ui'
import { useStore } from '../hooks.js'
import { Icon } from '../icons.jsx'
import { repoCard } from '../repo.js'
import { Failed } from '../parts.jsx'
import { lang, t } from '../i18n.js'

// The repos under the Summary's stats: GET app/repos as cards, each opening that repo's page. It reads again when a job
// ends, as the Summary does.
export function RepoCardsView({ data, now = Date.now() }) {
  const words = (k) => uiText(k, lang())
  const n = data.repos.length
  return (
    <section className="dk-rc" aria-labelledby="rc-title">
      <div className="dk-rc-head">
        <h2 id="rc-title" className="eyebrow">{t('rc.title')}</h2>
        <span className="muted small">{data.at ? t('rc.count', { n, ago: fmtAgo(data.at, now, words) }) : `${n} repos · ${t('rp.noHealth')}`}</span>
        <span className="dk-grow" />
        <a className="small" href="#/quality">{t('rc.health')}</a>
      </div>
      <div className="dk-rc-grid">
        {data.repos.map((row, i) => {
          const c = repoCard(row, t, now)
          const facts = [['rc.sonar', c.sonar.text, c.sonar.gateState], ['rc.libs', c.libs.text, c.libs.tone], ['rc.wiki', c.wiki, null], ['rc.docs', c.docs.text, c.docs.tone]]
          return (
            <a key={row.name} className="dk-tile dk-rc-card" href={c.href} style={{ '--i': i }}>
              <div className="dk-tile-h">
                <h3>{c.name}</h3>
                <span className="dk-grow" />
                <Chip state={c.stateTone}>{c.state}</Chip>
              </div>
              {c.stack ? <p className="dk-rc-stack small"><Icon name="language" /><span>{c.stack}</span></p> : null}
              <dl className="dk-rc-facts">
                {facts.map(([k, text, tone]) => (
                  <div key={k}><dt>{t(k)}</dt><dd className={tone ? `dk-rc-${tone}` : undefined}>{text}</dd></div>))}
              </dl>
              <span className="dk-tile-to">{t('rc.open')}</span>
            </a>
          )
        })}
      </div>
    </section>
  )
}

export default function RepoCards({ srv, jobs }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const { running } = useStore(jobs)
  const load = () => srv.get('app/repos').then((d) => { setData(d); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  const was = useRef(running.length)
  useEffect(() => {
    if (running.length < was.current) load()
    was.current = running.length
  }, [running.length])
  if (error) return <Failed title={t('rc.failed')} detail={error} onRetry={() => { setError(''); load() }} />
  if (!data) return <Skeleton lines={3} />
  return data.repos.length ? <RepoCardsView data={data} /> : null
}

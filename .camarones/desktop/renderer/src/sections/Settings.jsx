import { useEffect, useState } from 'react'
import { Aviso, Skeleton } from '@camaron/ui'
import { useCmd, useHash } from '../hooks.js'
import { Failed } from '../parts.jsx'
import { tokenNotice, tokenPrefill, viewOf } from '../nav.js'
import { Place } from '../Place.jsx'
import Commands from './Commands.jsx'
import { GuideCard, Kit, Repos, SessionSettings, Setup, Tokens, Uninstall } from './Machine.jsx'
import { Plugins, Skills, Trust } from './SettingsTeam.jsx'
import { t } from '../i18n.js'

// This machine and the team's config as tabs: General (guide, setup, sessions, repos), Tokens (the OS keychain), Skills,
// Plugins, Trust (what arrived with the team's repo and awaits approval; its count rides on the tab) and Kit.
export function SettingsView({ view, m, error = '', pending = 0, fill, srv, jobs, app, reload = () => {}, tick = 0, onSkillsChange, onRetry }) {
  const p = { srv, jobs, m, reload }
  return (
    <Place section="settings" view={view} badges={{ trust: pending }}>
      {view === 'general' ? (<>
        <GuideCard />
        {error ? <Failed title={t('mc.failed')} detail={error} onRetry={onRetry} /> : null}
        {!m && !error ? <Skeleton lines={6} /> : null}
        {m ? (<><Setup {...p} /><SessionSettings {...p} /><Repos {...p} /></>) : null}
        <Commands srv={srv} jobs={jobs} section="settings" />
      </>)
        : view === 'tokens' ? (<>
          {tokenNotice(fill) ? <Aviso tone="warn" title={t(tokenNotice(fill), { host: fill.host })} /> : null}
          <Tokens key={`${fill.host}|${fill.kind}`} srv={srv} host={fill.host} kind={fill.kind} />
        </>)
        : view === 'skills' ? <Skills srv={srv} jobs={jobs} onChange={onSkillsChange} />
        : view === 'plugins' ? <Plugins srv={srv} jobs={jobs} />
        : view === 'trust' ? <Trust srv={srv} jobs={jobs} tick={tick} onChange={onSkillsChange} />
        : (<>
          {error ? <Failed title={t('mc.failed')} detail={error} onRetry={onRetry} /> : null}
          {m ? <Kit {...p} app={app} /> : error ? null : <Skeleton lines={3} />}
          <Uninstall srv={srv} jobs={jobs} app={app} />
        </>)}
    </Place>
  )
}

export default function Settings({ srv, jobs, app }) {
  const [m, setM] = useState(null)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)
  const hash = useHash()
  const list = useCmd(srv, jobs, { quiet: true })
  const load = () => srv.get('app/machine').then((x) => { setM(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  useEffect(() => { list.run('trust', { json: true }) }, [tick])
  const pending = list.job?.result?.pending?.length || 0
  return <SettingsView view={viewOf(hash, 'settings')} m={m} error={error} pending={pending} fill={tokenPrefill(hash)} srv={srv} jobs={jobs} app={app}
    reload={load} tick={tick} onSkillsChange={() => setTick((n) => n + 1)} onRetry={() => { setError(''); load() }} />
}

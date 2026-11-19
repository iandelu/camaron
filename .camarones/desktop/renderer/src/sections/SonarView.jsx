import { Fragment, useEffect, useRef, useState } from 'react'
import { Button, Chip, EmptyState, Skeleton, fmtAgo, sonarConnectHash, uiText } from '@camaron/ui'
import { useCmd, useHash } from '../hooks.js'
import { repoHref, repoOf, withRepo } from '../nav.js'
import { estimate, filterSonar, sonarRows, sourceCounts } from '../sonar.js'
import { lang, t } from '../i18n.js'

const COLS = ['sq.repo', 'sq.source', 'sq.gate', 'sq.coverage', 'sq.bugs', 'sq.vulns', 'sq.debt']

export function SonarTable({ snapshot, repo, source, open, onRepo, onSource, onOpen, onRefresh, refreshing, now }) {
  const l = lang()
  const words = (k) => uiText(k, l)
  const all = sonarRows(snapshot, words, now)
  if (!snapshot) {
    return <EmptyState title={t('sq.none')} action={<Button size="sm" href="#/quality">{t('sq.noneGo')}</Button>} />
  }
  const counts = sourceCounts(all)
  const rows = filterSonar(all, { repo, source })
  const pick = (v) => onSource(source === v ? '' : v)
  return (<>
    <div className="row dk-sq-filters">
      <label className="dk-sq-field"><span className="muted small">{t('sq.repo')}</span>
        <select className="cu-input" value={repo} onChange={(e) => onRepo(e.target.value)}>
          <option value="">{t('sq.all')}</option>
          {all.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
        </select></label>
      <div className="dk-seg" role="group" aria-label={t('sq.source')}>
        <button type="button" className={source === '' ? 'on' : ''} aria-pressed={source === ''} onClick={() => onSource('')}>{t('sq.sources')}</button>
        <button type="button" className={source === 'sonar' ? 'on' : ''} aria-pressed={source === 'sonar'} onClick={() => pick('sonar')}>{`${t('sq.sonar')} · ${counts.sonar}`}</button>
        <button type="button" className={source === 'estimated' ? 'on' : ''} aria-pressed={source === 'estimated'} onClick={() => pick('estimated')}>{`${t('sq.estimated')} · ${counts.estimated}`}</button>
      </div>
      <span className="dk-grow"></span>
      <span className="muted small">{t('sq.read', { ago: fmtAgo(snapshot.at, now, words) })}</span>
      <Button size="sm" variant="ghost" disabled={refreshing} onClick={onRefresh}>{t('sq.again')}</Button>
    </div>
    <div className="dk-scroll dk-sq-box">
      <table className="dk-table">
        <thead><tr>{COLS.map((k) => <th key={k} scope="col">{t(k)}</th>)}</tr></thead>
        <tbody>{rows.map((r) => (
          <Fragment key={r.name}>
            <tr>
              <td><a href={repoHref(r.name)}><b>{r.name}</b></a></td>
              <td>{r.source === 'sonar' ? (
                <>{r.link ? <a href={r.link} target="_blank" rel="noreferrer">{t('sq.open') + ' ↗'}</a> : t('sq.sonar')}
                  {r.error ? <div className="muted small">{r.error}</div> : null}</>)
                : r.source === 'estimated' ? (
                  <button type="button" className="dk-link" aria-expanded={open === r.name} onClick={() => onOpen(open === r.name ? '' : r.name)}>
                    {open === r.name ? t('sq.hide') : t('sq.show')}</button>)
                  : r.unread ? <span><Chip state="warn">{t('sq.unread')}</Chip> <span className="muted small">{r.error}</span></span>
                    : <span className="muted small">{t('sq.notCloned')}</span>}</td>
              <td>{r.gateState ? <Chip state={r.gateState}>{r.gate}</Chip> : r.gate}</td>
              <td>{r.coverage}{r.coverageNote ? <div className="muted small">{r.coverageNote}</div> : null}</td>
              <td>{r.bugs}</td>
              <td>{r.vulns}</td>
              <td>{r.debt}</td>
            </tr>
            {open === r.name && r.source === 'estimated' ? <tr className="dk-sq-est"><td colSpan={COLS.length}><Estimate snapshot={snapshot} row={r} /></td></tr> : null}
          </Fragment>))}</tbody>
      </table>
    </div>
    <p className="muted small">{t('sq.wins')}</p>
  </>)
}

function Estimate({ snapshot, row }) {
  const e = estimate(snapshot, row.name)
  return (
    <div className="dk-sq-panel">
      <div className="row"><b>{t('sq.estTitle', { repo: row.name })}</b><Chip>{t('sq.estBadge')}</Chip></div>
      <div className="dk-sq-figs">
        <div><span className="muted small">{t('sq.estCoverage')}</span>
          <b>{e.coverage ? `${e.coverage.percent} %` : t('sq.estNoReport')}</b>
          {e.coverage ? <span className="muted small">{[t('sq.estReport'), e.coverage.at.slice(0, 10)].filter(Boolean).join(' · ')}</span> : null}</div>
        <div><span className="muted small">{t('sq.estLibs')}</span><b>{e.vulns.total}</b>
          <a className="small" href={withRepo('quality/libs', row.name)}>{t('sq.estLibsGo', { high: e.vulns.high })}</a></div>
        <div><span className="muted small">{t('sq.estStale')}</span><b>{e.stale}</b>
          <a className="small" href={withRepo('docs/wikis', row.name)}>{t('sq.estStaleGo')}</a></div>
        <div><span className="small">{t('sq.estCannot')}</span></div>
      </div>
      <div className="row"><Button size="sm" href={sonarConnectHash(e.host)}>{t('sq.connect')}</Button>
        <span className="muted small">{t('sq.connectWhy')}</span></div>
    </div>
  )
}

export default function SonarView({ srv, jobs }) {
  const hash = useHash()
  const [snap, setSnap] = useState(undefined)
  const [repo, setRepo] = useState(repoOf(hash))
  const [source, setSource] = useState('')
  const [open, setOpen] = useState('')
  const build = useCmd(srv, jobs, { quiet: true })
  const busy = useRef(false)
  const load = () => srv.get('health').then((d) => setSnap(d.snapshot), () => setSnap(null))
  useEffect(() => { load() }, [])
  useEffect(() => { setRepo(repoOf(hash)) }, [hash])
  const refresh = async () => {
    if (busy.current) return
    busy.current = true
    try { await build.run('health', { refresh: true }); await load() } finally { busy.current = false }
  }
  if (snap === undefined) return <Skeleton lines={5} />
  return <SonarTable snapshot={snap} repo={repo} source={source} open={open} onRepo={setRepo} onSource={setSource} onOpen={setOpen}
    onRefresh={refresh} refreshing={build.running} now={Date.now()} />
}

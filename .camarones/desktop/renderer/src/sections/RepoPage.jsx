import { useEffect, useState } from 'react'
import { Bars, Button, Chip, EmptyState, HBars, SegBar, Skeleton, Sparkline, fmtAgo, gateState, gateWord, sourceWord, stateWord,
  uiText } from '@camaron/ui'
import { fmtDebt } from '@camaron/ui/health.js'
import { ADR_BASE } from '../adr.js'
import { openPortal } from '../docs.js'
import { Icon } from '../icons.jsx'
import { Failed } from '../parts.jsx'
import { ROLES, activityBars, docsParts, libsRows, sonarTile, tileLinks, workParts } from '../repo.js'
import { StatusChip, chipOf } from './adr/Read.jsx'
import { lang, t } from '../i18n.js'

// A repo's page (#/flow/repo/<name>): GET app/repo as a bento of tiles, every figure read without AI. Each tile that has
// a window links to it filtered to the repo; what lives in the portal opens in the browser (onPortal).

const OUT = ' ↗'   // R4: the pictograph belongs to the view, never to a string
const GATES = ['OK', 'WARN', 'ERROR']
const WORK = { todo: 'rp.todo', doing: 'rp.doing', review: 'rp.inReview', done: 'rp.done', blocked: 'rp.blocked' }

const words = (k) => uiText(k, lang())
// git's dates (head, the last commit) are epoch seconds; the snapshot's are ISO.
const iso = (at) => (typeof at === 'number' ? new Date(at * 1000).toISOString() : at)
const num = (n) => (typeof n === 'number' && Number.isFinite(n) ? new Intl.NumberFormat(lang(), { maximumFractionDigits: 1 }).format(n) : '—')
const pct = (n) => (typeof n === 'number' ? `${num(n)} %` : '—')
const day = (at) => (Number.isNaN(Date.parse(at)) ? ''
  : new Intl.DateTimeFormat(lang(), { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(at)))
const listed = (parts) => parts.map((p) => `${p.label} ${p.n}`).join(', ')

function Shell({ children }) {
  return (
    <div className="dk-page dk-rp">
      <a className="dk-back" href="#/flow">{t('rp.back')}</a>
      {children}
    </div>
  )
}

function Tile({ as: Tag = 'section', span, i, id, icon, title, aside = null, children, ...rest }) {
  return (
    <Tag className={`dk-tile ${span}`} style={{ '--i': i }} aria-labelledby={id} {...rest}>
      <div className="dk-tile-h">
        <span className="dk-tile-i"><Icon name={icon} /></span>
        <h2 id={id}>{title}</h2>
        {aside ? <><span className="dk-grow" />{aside}</> : null}
      </div>
      {children}
    </Tag>
  )
}

function Header({ data, now }) {
  const { name, cloned, state, head, at } = data
  const stack = cloned ? (data.stack || []).filter((p) => ROLES.includes(p.role)) : []
  const meta = cloned ? [
    head ? <span key="branch">{`${t('rp.branch')} `}<code>{head.branch}</code></span> : null,
    head?.at ? <span key="commit">{t('rp.lastCommit', { ago: fmtAgo(iso(head.at), now, words) })}</span> : null,
    at ? <span key="health">{t('rp.health', { ago: fmtAgo(at, now, words) })}</span> : null,
  ].filter(Boolean) : []
  return (
    <section className="dk-tile s12" style={{ '--i': 0 }} aria-labelledby="rp-name">
      <div className="dk-rp-head">
        <h1 id="rp-name" className="t-impact">{name}</h1>
        <Chip state={state}>{stateWord('code', state, words)}</Chip>
        <span className="dk-grow" />
        {meta.length ? <span className="muted small dk-rp-meta">{meta}</span> : null}
      </div>
      {!cloned ? <p className="small">{t('rp.notCloned')}</p> : null}
      {stack.length ? (<>
        <ul className="dk-rp-stack">
          {stack.map((p, i) => (
            <li key={`${p.role}-${p.label}`} className="dk-rp-pill" style={{ '--i': i }}>
              <span className="dk-rp-pill-i"><Icon name={p.role} /></span>
              <span><span className="dk-rp-role">{t('rp.role.' + p.role)}</span><b>{p.label}</b></span>
            </li>))}
        </ul>
        <p className="muted small">{t('rp.stackNote')}</p>
      </>) : null}
    </section>
  )
}

// With no checkout here the Sonar and library figures are unknown (the server's zeros are not a clean state), and
// building a snapshot would not change that: the tile says so and still opens its window.
function NotCloned({ to, ...head }) {
  return (
    <Tile as="a" {...head}>
      <p className="muted small">{t('sq.notCloned')}</p>
      <span className="dk-tile-to">{to}</span>
    </Tile>
  )
}

function SonarTile({ cloned, sonar, trend, href }) {
  const head = { span: 's4', i: 1, id: 'rp-sonar', icon: 'sonar', title: t('rp.sonar') }
  if (!cloned) return <NotCloned {...head} href={href} to={t('rp.toSonar')} />
  if (!sonar) return (
    <Tile {...head}>
      <p className="muted small">{t('rp.noHealth')}</p>
      <div className="dk-tile-foot"><Button size="sm" href="#/quality">{t('rp.noHealthGo')}</Button></div>
    </Tile>
  )
  const s = sonarTile(sonar, trend)
  const server = s.source === 'sonar'
  const aside = !server ? <Chip>{t('rp.estimated')}</Chip>
    : GATES.includes(s.gate) ? <Chip state={gateState(s.gate)}>{gateWord(s.gate, words)}</Chip> : null
  const from = sonar.coverageSource && sonar.coverageSource !== 'sonar' ? sourceWord(sonar.coverageSource, words) : ''
  const k = s.points.length
  return (
    <Tile as="a" href={href} {...head} aside={aside}>
      <div className="dk-rp-big">
        <b className="t-impact">{pct(s.coverage)}</b>
        <span className="muted small">{[t('rp.coverage'), from].filter(Boolean).join(' · ')}</span>
        {s.delta !== null
          ? <span className="small">{t('rp.delta', { sign: s.delta > 0 ? '+' : s.delta < 0 ? '−' : '', n: num(Math.abs(s.delta)), k })}</span>
          : null}
      </div>
      {k >= 2
        ? <Sparkline values={s.points} label={t('rp.trendLabel', { k, from: num(s.points[0]), to: num(s.points[k - 1]) })}
            tips={trend.map((p) => [day(p.at), pct(p.coverage)].filter(Boolean).join(' · '))} />
        : k === 1 ? <p className="muted small">{t('rp.trendFew')}</p> : null}
      {server ? (
        <dl className="dk-rp-kv">
          <div><dt>{t('sq.bugs')}</dt><dd>{num(sonar.bugs)}</dd></div>
          <div><dt>{t('sq.vulns')}</dt><dd>{num(sonar.vulnerabilities)}</dd></div>
          <div><dt>{t('sq.debt')}</dt><dd>{fmtDebt(sonar.debtMinutes)}</dd></div>
        </dl>) : null}
      <span className="dk-tile-to">{t('rp.toSonar')}</span>
    </Tile>
  )
}

function ActivityTile({ activity, now }) {
  const bars = activityBars(activity, lang())
  const aside = activity
    ? <span className="muted small">{t(activity.people === 1 ? 'rp.activitySum1' : 'rp.activitySum', { n: activity.total, p: activity.people })}</span>
    : null
  const last = activity?.last
  return (
    <Tile span="s8" i={2} id="rp-activity" icon="activity" title={t('rp.activity')} aside={aside}>
      {bars ? (<>
        <Bars values={bars.values} tips={bars.tips} label={t('rp.activityLabel', { n: activity.total, max: Math.max(0, ...bars.values) })} />
        <div className="dk-rp-months" aria-hidden="true">{bars.months.map((m, i) => <span key={i}>{m}</span>)}</div>
        {last ? <p className="muted small">{t('rp.last', { subject: last.subject, author: last.author, ago: fmtAgo(iso(last.at), now, words) })}</p> : null}
      </>) : <p className="muted small">{t('rp.noGit')}</p>}
    </Tile>
  )
}

function LibsTile({ cloned, libs, href }) {
  if (!cloned) return <NotCloned span="s6" i={3} id="rp-libs" icon="libs" title={t('rp.libs')} href={href} to={t('rp.toLibs')} />
  const l = lang()
  const rows = libsRows(libs).map((r) => {
    const sev = words(`hb.sev.${r.key}`)
    return { ...r, sev, label: sev.charAt(0).toLocaleUpperCase(l) + sev.slice(1) }
  })
  const n = rows.reduce((sum, r) => sum + r.n, 0)
  const tone = rows[0].n + rows[1].n ? 'bad' : rows[2].n ? 'warn' : undefined
  const aside = !libs?.scanned ? null
    : n ? <Chip state={tone}>{n === 1 ? t('rp.libsVulns1') : t('rp.libsVulns', { n })}</Chip>
      : <Chip state="ok">{t('rp.libsClean')}</Chip>
  const of = [typeof libs?.total === 'number' ? t('rp.libsOf', { n: libs.total }) : '',
    typeof libs?.outdated === 'number' ? t('rp.libsNewer', { n: libs.outdated }) : ''].filter(Boolean).join(' · ')
  return (
    <Tile as="a" href={href} span="s6" i={3} id="rp-libs" icon="libs" title={t('rp.libs')} aside={aside}>
      {libs?.scanned
        ? <HBars rows={rows} label={t('rp.libsLabel', { list: rows.map((r) => `${r.sev} ${r.n}`).join(', ') })} />
        : <p className="muted small">{t('rp.libsNever')}</p>}
      {of ? <p className="muted small">{of}</p> : null}
      <span className="dk-tile-to">{t('rp.toLibs')}</span>
    </Tile>
  )
}

function DocsTile({ docs, wiki, href, onPortal }) {
  const parts = docsParts(docs).map((p) => ({ ...p, label: t(`rp.${p.key}`) }))
  const toCheck = (docs?.suspect || 0) + (docs?.stale || 0)
  return (
    <Tile span="s6" i={4} id="rp-docs" icon="docs" title={t('rp.docs')}>
      {docs?.total ? (<>
        <div className="dk-rp-big"><b className="t-impact">{docs.total}</b><span className="muted small">{t('rp.docsPages')}</span></div>
        <SegBar parts={parts} label={t('rp.docsLabel', { n: docs.total, list: listed(parts) })} />
      </>) : <p className="muted small">{t('rp.noDocs')}</p>}
      <div className="dk-tile-foot">
        <a href={href}>{wiki?.pages ? t('rp.wiki', { n: wiki.pages }) : t('rp.wikiNone')}</a>
        <span className="dk-grow" />
        {toCheck ? <Button size="sm" variant="ghost" onClick={() => onPortal('#/review')}>{t('rp.review', { n: toCheck }) + OUT}</Button> : null}
      </div>
    </Tile>
  )
}

const Arrow = () => (
  <span className="dk-rp-arrow" aria-hidden="true">
    <svg viewBox="0 0 22 12" width="22" height="12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"
      strokeLinejoin="round" focusable="false"><path d="M1 6h19" /><path d="m15 1 5 5-5 5" /></svg>
  </span>
)

// Callers · arrow · this repo · arrow · callees, as boxes; a side with no element is left out with its arrow.
function MiniC4({ c4 }) {
  const titles = (nodes) => nodes.map((n) => n.title).join(', ') || '—'
  let i = 0
  const side = (nodes) => <div className="dk-rp-c4-col">{nodes.map((n) => <div key={n.fqn} className="dk-rp-node" style={{ '--i': i++ }}>{n.title}</div>)}</div>
  const callers = c4.in.length ? <>{side(c4.in)}<Arrow /></> : null
  const me = (
    <div className="dk-rp-c4-col me">
      <div className="dk-rp-node me" style={{ '--i': i++ }}><b>{c4.title}</b><span>{[c4.technology, t('rp.me')].filter(Boolean).join(' · ')}</span></div>
    </div>
  )
  const callees = c4.out.length ? <><Arrow />{side(c4.out)}</> : null
  return (
    <div className="dk-rp-c4" role="img" aria-label={t('rp.c4Label', { repo: c4.title, callers: titles(c4.in), callees: titles(c4.out) })}>
      {callers}{me}{callees}
    </div>
  )
}

function ArchTile({ name, c4, graph, onPortal }) {
  const hasGraph = typeof graph === 'number'
  return (
    <Tile span="s7" i={5} id="rp-arch" icon="arch" title={t('rp.arch')}>
      {c4 ? <MiniC4 c4={{ ...c4, in: c4.in || [], out: c4.out || [] }} /> : <p className="muted small">{t('rp.noC4')}</p>}
      <div className="dk-tile-foot">
        {hasGraph ? <span className="muted small">{t('rp.nodes', { n: num(graph) })}</span> : null}
        <span className="dk-grow" />
        {c4 ? <Button size="sm" variant="ghost" onClick={() => onPortal('#/c4')}>{t('rp.viewC4') + OUT}</Button> : null}
        {hasGraph
          ? <Button size="sm" variant="ghost" onClick={() => onPortal(`#/code/${encodeURIComponent(name)}/graph`)}>{t('rp.viewGraph') + OUT}</Button>
          : null}
      </div>
    </Tile>
  )
}

function WorkTile({ work, adrs, links }) {
  const parts = workParts(work).map((p) => ({ ...p, label: t(WORK[p.key]) }))
  const total = work?.total || 0
  const aside = total ? <span className="muted small">{total === 1 ? t('rp.cards1') : t('rp.cards', { n: total })}</span> : null
  return (
    <Tile span="s5" i={6} id="rp-work" icon="work" title={t('rp.work')} aside={aside}>
      {total ? <SegBar parts={parts} label={t('rp.workLabel', { list: listed(parts) })} /> : null}
      {adrs.length ? (
        <ul className="dk-rp-adrs">
          {adrs.map((a) => (
            <li key={a.id} className="dk-rp-adr">
              <code className="muted">{a.id}</code>
              <a href={`${ADR_BASE}/${encodeURIComponent(a.id)}`}>{a.title}</a>
              <StatusChip chip={chipOf(a)} />
            </li>))}
        </ul>) : null}
      {!total && !adrs.length ? <p className="muted small">{t('rp.noWork')}</p> : null}
      <div className="dk-tile-foot">
        <a href={links.board}>{t('rp.toBoard')}</a>
        <a href={links.decisions}>{t('rp.toDecisions')}</a>
      </div>
    </Tile>
  )
}

export function RepoBento({ data, now, onPortal }) {
  const links = tileLinks(data.name)
  return (
    <Shell>
      <div className="dk-bento">
        <Header data={data} now={now} />
        <SonarTile cloned={data.cloned} sonar={data.sonar} trend={data.trend || []} href={links.sonar} />
        <ActivityTile activity={data.activity} now={now} />
        <LibsTile cloned={data.cloned} libs={data.libs} href={links.libs} />
        <DocsTile docs={data.docs} wiki={data.wiki} href={links.wikis} onPortal={onPortal} />
        <ArchTile name={data.name} c4={data.c4} graph={data.graph} onPortal={onPortal} />
        <WorkTile work={data.work} adrs={data.adrs || []} links={links} />
      </div>
    </Shell>
  )
}

// name null: the address names no plain repo, so nothing is asked. A 404 is a repo the project does not have.
export default function RepoPage({ srv, app, name }) {
  const [got, setGot] = useState({})
  const load = () => srv.get('app/repo', { name }).then((data) => setGot({ data }),
    (e) => setGot(e.status === 404 ? { missing: true } : { error: e.message }))
  useEffect(() => { if (name) load() }, [name])
  if (!name || got.missing) {
    return <div className="dk-page"><EmptyState title={t('rp.unknown')} action={<Button size="sm" href="#/flow">{t('rp.back')}</Button>} /></div>
  }
  if (got.error) return <Shell><Failed title={t('rp.failed')} detail={got.error} onRetry={() => { setGot({}); load() }} /></Shell>
  if (!got.data) return <Shell><Skeleton lines={6} lang={lang()} /></Shell>
  return <RepoBento data={got.data} now={Date.now()} onPortal={(hash) => openPortal(app, location.origin, hash)} />
}

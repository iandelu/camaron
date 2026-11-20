import { barScale, hbarWidths, segmentParts, sparkGeometry } from './charts.js'

const W = 240
const H = 56

export function Sparkline({ values, label, tips = [], width = W, height = H }) {
  const g = sparkGeometry(values, { width, height })
  if (!g) return null
  const last = g.points.at(-1)
  return (
    <svg className="cu-spark" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <line className="cu-spark-axis" x1="0" x2={width} y1={height - 1} y2={height - 1} />
      <path className="cu-spark-area" d={g.area} />
      <path className="cu-spark-line" d={g.line} />
      <circle className="cu-spark-dot" cx={last.x} cy={last.y} r="3" />
      {g.points.map((p, i) => (
        <circle key={i} className="cu-spark-hit" cx={p.x} cy={p.y} r="8">
          <title>{tips[i]}</title>
        </circle>
      ))}
    </svg>
  )
}

export function Bars({ values, label, tips = [], top = true }) {
  const { max, heights } = barScale(values)
  return (
    <div className="cu-bars" role="img" aria-label={label}>
      {top && <span className="cu-bars-grid" aria-hidden="true"><span>{max}</span></span>}
      <div className="cu-bars-plot">
        {heights.map((h, i) => (
          <span key={i} className="cu-bars-col" title={tips[i]} data-tip={tips[i]}>
            <span className="cu-bars-bar" style={{ height: `${h}%`, '--i': i }} />
          </span>
        ))}
      </div>
      <span className="cu-bars-zero" aria-hidden="true">0</span>
    </div>
  )
}

const toneClass = (p) => (p.tone ? `cu-tone-${p.tone}` : p.ordinal ? `cu-ord-${p.ordinal}` : 'cu-tone-series')

export function SegBar({ parts, label }) {
  const segs = segmentParts(parts)
  return (
    <div className="cu-seg" role="img" aria-label={label}>
      <div className="cu-seg-track">
        {segs.map((p, i) => (
          <span key={p.key} className={`cu-seg-part ${toneClass(p)}`} style={{ flex: `${p.n} 1 0`, '--i': i }} title={`${p.label}: ${p.n}`} />
        ))}
      </div>
      <ul className="cu-legend">
        {segs.map((p) => (
          <li key={p.key}><span className={`cu-legend-swatch ${toneClass(p)}`} />{p.label}<span className="cu-legend-n">{p.n}</span></li>
        ))}
      </ul>
    </div>
  )
}

export function HBars({ rows, label }) {
  return (
    <div className="cu-hbars" role="img" aria-label={label}>
      {hbarWidths(rows).map((r, i) => (
        <div key={r.key} className="cu-hbars-row" title={`${r.label}: ${r.n}`}>
          <span className="cu-hbars-label">{r.label}</span>
          <span className="cu-hbars-track">
            <span className={`cu-hbars-fill ${r.tone ? `cu-tone-${r.tone}` : 'cu-tone-series'}`} style={{ width: `${r.pct}%`, '--i': i }} />
          </span>
          <span className="cu-hbars-n">{r.n}</span>
        </div>
      ))}
    </div>
  )
}

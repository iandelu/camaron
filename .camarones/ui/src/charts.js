const finite = (v) => Number.isFinite(v)
const round = (n) => Math.round(n * 10) / 10

export function sparkGeometry(values, { width = 240, height = 56, pad = 6 } = {}) {
  if (values.filter(finite).length < 2 || !values.every(finite)) return null
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = hi - lo
  const inner = height - 2 * pad
  const points = values.map((v, i) => ({
    x: round(pad + (i * (width - 2 * pad)) / (values.length - 1)),
    y: round(span === 0 ? height / 2 : pad + inner - ((v - lo) / span) * inner),
    v,
  }))
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${p.x} ${p.y}`).join(' ')
  const area = `${line} L${points.at(-1).x} ${height - pad} L${points[0].x} ${height - pad} Z`
  return { points, line, area }
}

export function barScale(values) {
  const clean = values.map((v) => (finite(v) && v > 0 ? v : 0))
  const max = Math.max(0, ...clean)
  return { max, heights: clean.map((v) => (max ? round((v / max) * 100) : 0)) }
}

export function segmentParts(parts) {
  const kept = parts.filter((p) => p.n > 0)
  const total = kept.reduce((sum, p) => sum + p.n, 0)
  return total ? kept.map((p) => ({ ...p, pct: round((p.n / total) * 100) })) : []
}

export function hbarWidths(rows) {
  const max = Math.max(0, ...rows.map((r) => r.n))
  return rows.map((r) => ({ ...r, pct: max ? round((r.n / max) * 100) : 0 }))
}

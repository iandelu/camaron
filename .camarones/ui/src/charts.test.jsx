import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Bars, HBars, SegBar, Sparkline } from './index.js'

const html = (node) => renderToStaticMarkup(node)

test('Sparkline draws nothing under two values', () => {
  expect(html(<Sparkline values={[1]} label="x" />)).toBe('')
})

test('Sparkline is a labelled image with a tip on every point', () => {
  const out = html(<Sparkline values={[70, 78]} label="Score 70 to 78" tips={['w1: 70', 'w2: 78']} />)
  expect(out).toContain('role="img"')
  expect(out).toContain('aria-label="Score 70 to 78"')
  expect(out.match(/<title>/g)).toHaveLength(2)
  expect(out).toContain('<title>w1: 70</title>')
  expect(out).toContain('cu-spark-line')
})

test('Bars has a column per value, each with its tip and height', () => {
  const out = html(<Bars values={[1, 3]} label="Commits" tips={['mon: 1', 'tue: 3']} />)
  expect(out.match(/class="cu-bars-col"/g)).toHaveLength(2)
  expect(out).toContain('title="mon: 1"')
  expect(out).toContain('data-tip="tue: 3"')
  expect(out).toContain('height:33.3')
  expect(out).toContain('height:100%')
  expect(out).toContain('aria-label="Commits"')
})

test('SegBar legends its parts and tones them', () => {
  const out = html(<SegBar label="Gates" parts={[{ key: 'a', n: 3, label: 'Passing', tone: 'ok' }, { key: 'b', n: 1, label: 'Warning', tone: 'warn' }]} />)
  expect(out).toContain('Passing')
  expect(out).toContain('Warning')
  expect(out).toContain('class="cu-seg-part cu-tone-ok"')
  expect(out).toContain('cu-legend')
})

test('HBars shows each row label, number and width', () => {
  const out = html(<HBars label="Languages" rows={[{ key: 'j', label: 'Java', n: 1 }, { key: 'k', label: 'Kotlin', n: 2 }]} />)
  expect(out).toContain('Java')
  expect(out).toContain('Kotlin')
  expect(out).toContain('width:50%')
  expect(out).toContain('>2<')
})

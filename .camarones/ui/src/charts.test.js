import { expect, test } from 'vitest'
import { barScale, hbarWidths, segmentParts, sparkGeometry } from './charts.js'

test('sparkGeometry needs two finite values', () => {
  expect(sparkGeometry([70])).toBeNull()
  expect(sparkGeometry([70, NaN])).toBeNull()
})

test('sparkGeometry maps the series into the padded box', () => {
  const g = sparkGeometry([70, 78], { width: 100, height: 50, pad: 5 })
  expect(g.points).toEqual([{ x: 5, y: 45, v: 70 }, { x: 95, y: 5, v: 78 }])
  expect(g.line).toMatch(/^M/)
  expect(g.area).toMatch(/Z$/)
})

test('a flat series sits mid-height', () => {
  expect(sparkGeometry([3, 3]).points[0].y).toBe(28)
})

test('barScale is a percent of the max', () => {
  expect(barScale([2, 4, 0])).toEqual({ max: 4, heights: [50, 100, 0] })
  expect(barScale([0, 0]).heights).toEqual([0, 0])
  expect(barScale([-1, NaN, 2]).heights).toEqual([0, 0, 100])
})

test('segmentParts drops empty parts and gives each its share', () => {
  expect(segmentParts([{ key: 'a', n: 3 }, { key: 'b', n: 0 }, { key: 'c', n: 1 }]))
    .toEqual([{ key: 'a', n: 3, pct: 75 }, { key: 'c', n: 1, pct: 25 }])
  expect(segmentParts([{ key: 'a', n: 0 }])).toEqual([])
})

test('hbarWidths is a percent of the largest', () => {
  expect(hbarWidths([{ key: 'h', n: 1 }, { key: 'm', n: 2 }]).map((r) => r.pct)).toEqual([50, 100])
})

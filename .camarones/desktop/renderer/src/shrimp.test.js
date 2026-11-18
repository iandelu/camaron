import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import { shrimpMarkup } from './shrimp.js'

// The favicon is the one drawing of the shrimp: the animated one is its markup, inlined (CAMARON.md > Icons).
const favicon = readFileSync(new URL('../../../portal/app/public/favicon.svg', import.meta.url), 'utf-8')
const CLASSES = ['shrimp-antennae', 'shrimp-tail', 'shrimp-eye']
const dOf = (svg) => [...svg.matchAll(/\sd="([^"]*)"/g)].map((m) => m[1])
const sha = (text) => createHash('sha256').update(text).digest('hex').slice(0, 10)

// Every element of the favicon as it was before the class names, path data as a hash: nothing in it may change
// except by adding a `class`, or `scripts/icons.py` would draw another icon.
const ORIGINAL = [
  'svg xmlns=http://www.w3.org/2000/svg viewBox=0 0 64 64',
  'rect width=64 height=64 rx=14 fill=#0a0a0a',
  'g fill=none stroke=#ff8a5b stroke-width=1.5 stroke-linecap=round',
  'path d#1963dc1b5d',
  'path d#441c958cc8',
  'path d#ec7ce88d34',
  'g fill=#ff8a5b stroke=#0a0a0a stroke-width=1.3 stroke-linejoin=round',
  'g transform=translate(31.7 48.5)',
  'ellipse cy=-5 rx=3 ry=5.8 transform=rotate(227.7)',
  'ellipse cy=-5 rx=3 ry=5.8 transform=rotate(311.7)',
  'ellipse cy=-5 rx=3 ry=5.8 transform=rotate(269.7)',
  'path d#a63657b5f5',
  'path d#2383a74cdf stroke=#0a0a0a stroke-width=1.5 stroke-linecap=round',
  'circle cx=19.2 cy=25.5 r=1.9 fill=#0a0a0a',
]

const elements = (svg) => [...svg.matchAll(/<(\w+)((?:\s+[\w:-]+="[^"]*")*)\s*\/?>/g)].map(([, tag, attrs]) => {
  const all = [...attrs.matchAll(/([\w:-]+)="([^"]*)"/g)].map(([, k, v]) => [k, v])
  const sig = [tag, ...all.filter(([k]) => k !== 'class').map(([k, v]) => (k === 'd' ? `d#${sha(v)}` : `${k}=${v}`))].join(' ')
  return { sig, cls: all.find(([k]) => k === 'class')?.[1] }
})

test('the favicon only gained class names: the same elements, attributes and path data as before', () => {
  expect(elements(favicon).map((e) => e.sig)).toEqual(ORIGINAL)
})

test('each class sits once, on its own part of the drawing', () => {
  for (const name of CLASSES) expect(favicon.match(new RegExp(`class="${name}"`, 'g'))).toHaveLength(1)
  const classed = Object.fromEntries(elements(favicon).filter((e) => e.cls).map((e) => [e.cls, e.sig]))
  expect(Object.keys(classed).sort()).toEqual([...CLASSES].sort())
  expect(classed['shrimp-antennae']).toBe('g fill=none stroke=#ff8a5b stroke-width=1.5 stroke-linecap=round')
  expect(classed['shrimp-tail']).toBe('g transform=translate(31.7 48.5)')
  expect(classed['shrimp-eye']).toBe('circle cx=19.2 cy=25.5 r=1.9 fill=#0a0a0a')
})

test('the markup is the favicon\'s paths, whole: no second drawing', () => {
  const out = shrimpMarkup(favicon)
  expect(dOf(favicon)).toHaveLength(5)
  for (const d of dOf(favicon)) expect(out).toContain(`d="${d}"`)
  expect(dOf(out)).toEqual(dOf(favicon))
  expect(out.match(/<ellipse/g)).toHaveLength(3)
  expect(out).toMatch(/<circle class="shrimp-eye" cx="19.2" cy="25.5" r="1.9"/)
})

test('it is the inner markup, without the ink tile', () => {
  const out = shrimpMarkup(favicon)
  expect(out).not.toMatch(/<svg|<\/svg>/)
  expect(out).not.toContain('<rect')
  expect(out.startsWith('<g')).toBe(true)
  expect(out.endsWith('/>')).toBe(true)
})

test('the two colours come from the theme tokens, not hex', () => {
  const out = shrimpMarkup(favicon)
  expect(out).not.toMatch(/#ff8a5b|#0a0a0a/i)
  expect(out).not.toMatch(/#[0-9a-f]{3,8}\b/i)
  expect(out).toContain('stroke="var(--color-aurora-coral)"')
  expect(out).toContain('fill="var(--color-aurora-coral)"')
  expect(out).toContain('stroke="var(--color-canvas)"')
  expect(out).toContain('fill="var(--color-canvas)"')
})

test('the class names reach the markup', () => {
  const out = shrimpMarkup(favicon)
  for (const name of CLASSES) expect(out).toContain(`class="${name}"`)
})

test('anything that is not an svg gives nothing', () => {
  expect(shrimpMarkup('')).toBe('')
  expect(shrimpMarkup('<p>no drawing</p>')).toBe('')
})

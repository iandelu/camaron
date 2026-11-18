import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { DocsIcon } from './DocsIcons.jsx'

const NAMES = ['none', 'generating', 'fresh', 'stale', 'old', 'failed', 'blocked', 'docs', 'wikis', 'c4', 'read', 'review', 'search', 'ci']
const draw = (name) => renderToStaticMarkup(<DocsIcon name={name} />)

test.each(NAMES)('%s is one inline svg, hidden from readers, in the text colour', (name) => {
  const out = draw(name)
  expect(out.match(/<svg/g)).toHaveLength(1)
  expect(out).toContain('class="dk-ico"')
  expect(out).toContain('viewBox="0 0 24 24"')
  expect(out).toContain('aria-hidden="true"')
  expect(out).toContain('stroke="currentColor"')
  expect(out).toContain('fill="none"')
  expect(out).not.toContain('fill="#')
  expect(out).toMatch(/<(path|circle|rect|line|polyline)\b/)
})

test('each name draws its own icon', () => {
  expect(new Set(NAMES.map(draw)).size).toBe(NAMES.length)
})

test('an unknown name draws nothing', () => {
  expect(draw('x')).toBe('')
  expect(draw(undefined)).toBe('')
})

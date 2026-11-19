import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// The app's own CSS takes every colour from the theme and keeps the focus ring of the shared kit (ui/src/ui.css).
const css = readFileSync(new URL('./app.css', import.meta.url), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')
const rule = (sel) => css.match(new RegExp(`${sel.replace(/[.>]/g, (c) => '\\' + c)}\\s*\\{([^}]*)\\}`))[1]
const px = (body, prop) => parseFloat((body.match(new RegExp(`(?:^|[\\s;])${prop}:\\s*([\\d.]+)rem`)) || [0, 0])[1]) * 16

test('no raw colours', () => {
  expect(css.match(/#[0-9a-f]{3,8}\b|rgba?\(\s*\d/gi) ?? []).toEqual([])
})

// WCAG 2.4.7: a rule that drops the outline gives the focus another visible mark (a border or a shadow) itself.
test('nothing hides the focus', () => {
  for (const [, sel, body] of css.matchAll(/([^{}]+)\{([^}]*outline:\s*(?:none|0)\b[^}]*)\}/g)) {
    expect(sel, sel.trim()).toMatch(/:focus/)
    expect(body, sel.trim()).toMatch(/box-shadow|border/)
  }
})

test('the hints and the palette do not move for who asked for less motion', () => {
  expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.dk-hint\s*\{\s*transition:\s*none/)
})

// WCAG 2.5.8: the sidebar links, the projects of the rail, the folds and the labelled checkboxes are 24 px or more.
test.each([['.dk-nav', 'min-height'], ['.dk-proj', 'height'], ['.dk-fold > summary', 'min-height'], ['.dk-check', 'min-height'],
  ['.dk-unit-main > a', 'min-height'], ['.dk-back', 'min-height']])(
  '%s is a 24 px target', (sel, prop) => {
    expect(px(rule(sel), prop)).toBeGreaterThanOrEqual(24)
  })

// main (d2c94ca): the system draws the window controls over the header, so the header drags the window and leaves
// them their room (macOS traffic lights left, Windows / Linux right); the hub's bar does the same.
test.each(['.dk-top', '.dk-titlebar'])('%s is the window\'s title bar', (sel) => {
  const body = rule(sel)
  expect(body).toMatch(/-webkit-app-region:\s*drag/)
  expect(body).toMatch(/padding:[^;]*env\(titlebar-area-width[^;]*env\(titlebar-area-x/)
  const noDrag = css.match(new RegExp(sel.replace('.', '\\.') + ' :is\\(([^)]*)\\)\\s*\\{([^}]*)\\}'))
  expect(noDrag?.[1]).toContain('button')
  expect(noDrag?.[2]).toMatch(/-webkit-app-region:\s*no-drag/)
})

// The Board takes the whole window, however wide, and its columns reach the bottom of it.
test('a full page has no width cap and fills the height', () => {
  expect(rule('.dk-page.full')).toMatch(/max-width:\s*none/)
  expect(rule('.dk-page.full')).toMatch(/min-height:\s*100%/)
})

// The Libraries scan: its bar and its tick stand still for who asked for less motion, and the check rests drawn, so
// nothing waits invisible for an animation.
test('the scan\'s bar and tick do not move for who asked for less motion, and the check rests drawn', () => {
  const reduced = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'))
  expect(reduced).toMatch(/\.dk-tick \*[^{]*\{\s*animation:\s*none/)
  expect(reduced).toMatch(/\.dk-bar i[^{]*\{[^}]*animation:\s*none/)
  expect(rule('.dk-tick-check')).toMatch(/stroke-dashoffset:\s*0\b/)
})

// The review lives inside Docs: presenting takes the Docs page (the one that holds the review) to the whole height and
// hides its title, the team strip and the tabs, so only the review stays on screen; the review's parts keep their gap.
test('presenting a review hides the Docs chrome around it and keeps the height chain', () => {
  const exact = (sel) => css.match(new RegExp(sel.replace(/[.*+?^${}()|[\]\\>]/g, '\\$&') + '\\s*\\{([^}]*)\\}'))?.[1] ?? ''
  const page = exact('.dk-page:has(.dk-present)')
  expect(page).toMatch(/flex:\s*1/)
  expect(page).toMatch(/min-height:\s*0/)
  const hidden = css.match(/\.dk-page:has\(\.dk-present\)\s*>\s*:is\(([^)]*(?:\([^)]*\))?[^)]*)\)\s*\{([^}]*)\}/)
  expect(hidden?.[2]).toMatch(/display:\s*none/)
  for (const sel of ['h1', '[data-tour="docs-team"]', '.dk-guide-tabs']) expect(hidden?.[1]).toContain(sel)
  expect(css).not.toMatch(/\.dk-present \.dk-page\b/)
  expect(rule('.dk-rv-screen')).toMatch(/display:\s*flex[\s\S]*flex-direction:\s*column/)
})

// An at-rule's blocks (balanced braces), each with where it sits in the stylesheet and its body.
const blocks = (at) => {
  const out = []
  for (let i = css.indexOf(at); i !== -1; i = css.indexOf(at, i + 1)) {
    const open = css.indexOf('{', i)
    let depth = 1
    let j = open + 1
    for (; depth && j < css.length; j++) depth += css[j] === '{' ? 1 : css[j] === '}' ? -1 : 0
    out.push({ start: i, end: j, body: css.slice(open + 1, j - 1) })
  }
  return out
}

// The repo page: its tiles, stack pills and C4 boxes rise only for who did not ask for less motion, by moving and fading.
test('the repo page moves only inside prefers-reduced-motion: no-preference, by transform and opacity alone', () => {
  const motion = blocks('@media (prefers-reduced-motion: no-preference)')
  const inside = motion.map((b) => b.body).join('\n')
  const outside = motion.reduceRight((s, b) => s.slice(0, b.start) + s.slice(b.end), css)
  expect(inside).toMatch(/(?:^|[\s,}])\.dk-tile\s*\{[^}]*animation:/)
  for (const [, sel, body] of outside.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (/\.dk-(tile|rp-)/.test(sel)) expect(body, sel.trim()).not.toMatch(/(?:^|[\s;])(?:animation|transition|transform)[\w-]*\s*:/)
  }
  const names = new Set([...inside.matchAll(/\.dk-(?:tile|rp-[\w-]+)[^{]*\{[^}]*animation:\s*([\w-]+)/g)].map((m) => m[1]))
  expect(names.size).toBeGreaterThan(0)
  for (const name of names) {
    const frames = blocks(`@keyframes ${name} `).map((b) => b.body).join('')
    expect(frames, name).not.toBe('')
    for (const [, prop] of frames.matchAll(/([\w-]+)\s*:/g)) expect(['transform', 'opacity'], `${name}: ${prop}`).toContain(prop)
  }
})

test('the bento is a 12-column grid that becomes one column under 1000 px', () => {
  expect(rule('.dk-bento')).toMatch(/display:\s*grid/)
  expect(rule('.dk-bento')).toMatch(/grid-template-columns:\s*repeat\(12,\s*minmax\(0,\s*1fr\)\)/)
  const narrow = blocks('@media (max-width: 1000px)').map((b) => b.body).join('\n')
  expect(narrow).toMatch(/\.dk-bento\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/)
  expect(narrow).toMatch(/\.dk-tile[^{]*\{[^}]*grid-column:\s*1\s*\/\s*-1/)
})

test('a repo card in the Summary grid takes no 12-column bento span', () => {
  expect(css).toMatch(/\.dk-rc-grid\s*>\s*\.dk-tile\s*\{[^}]*grid-column:\s*auto/)
})

test('the Wikis stack is a full-width column: the 14 rem width belongs to the Machine stack input only', () => {
  expect(css).not.toMatch(/\.dk-stack\s*\{[^}]*\bwidth:/)
  expect(css).toMatch(/\.dk-stack-in\s*\{[^}]*width:\s*14rem/)
  expect(readFileSync(new URL('./sections/Machine.jsx', import.meta.url), 'utf-8')).toContain('dk-stack-in')
})

test('the repo chip leaves a gap before its clear control', () => {
  expect(css).toMatch(/\.dk-bd-repo-x\s*\{[^}]*margin-inline-start/)
})

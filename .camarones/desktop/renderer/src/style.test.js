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

// Docs lays its wikis out in a grid of its own: Machine's stack input shares the old `.dk-stack` name, so that class
// keeps only its width and never leaks into another layout.
test('the Docs wikis are a responsive grid and .dk-stack is only a width', () => {
  expect(rule('.dk-wikis')).toMatch(/repeat\(auto-fill,\s*minmax\(18rem,\s*1fr\)\)/)
  expect(css).not.toMatch(/\.dk-stack\s*\{[^}]*display/)
})

// The Libraries scan: its bar and its tick stand still for who asked for less motion, and the check rests drawn, so
// nothing waits invisible for an animation.
test('the scan\'s bar and tick do not move for who asked for less motion, and the check rests drawn', () => {
  const reduced = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'))
  expect(reduced).toMatch(/\.dk-tick \*[^{]*\{\s*animation:\s*none/)
  expect(reduced).toMatch(/\.dk-bar i[^{]*\{[^}]*animation:\s*none/)
  expect(rule('.dk-tick-check')).toMatch(/stroke-dashoffset:\s*0\b/)
})

// The wiki cards: they rise in one after another, the one that runs pulses and glows (on a pseudo-element, so the
// pulse never replaces the card's own rise), a finished one pops its icon in, and all of it stands still for who asked
// for less motion. A long repo name cannot push the card out of its grid track.
test('the wiki cards\' motion is staggered, tone-driven and off for who asked for less motion', () => {
  expect(css).toMatch(/\.dk-wikis > \*\s*\{[^}]*animation:\s*dk-rise[^}]*animation-delay:\s*calc\(var\(--i,\s*0\)\s*\*\s*40ms\)/)
  expect(css).toMatch(/\.dk-wiki\.is-generating\s*\{[^}]*--tone:\s*var\(--color-aurora-amber\)/)
  expect(css).toMatch(/\.dk-wiki\.is-generating \.dk-ico\s*\{[^}]*animation:\s*dk-glow/)
  expect(css).toMatch(/\.dk-wiki\.is-done \.dk-ico\s*\{[^}]*animation:\s*dk-tick-pop/)
  expect(css).toMatch(/\.dk-wiki\s*\{[^}]*min-width:\s*0/)
  const reduced = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'))
  expect(reduced).toMatch(/\.dk-wikis > \*[^{]*\.dk-wiki\.is-generating::after[^{]*\.dk-wiki\.is-generating \.dk-ico[^{]*\.dk-wiki\.is-done \.dk-ico[^{]*\{\s*animation:\s*none/)
})

// What moves moves only by transform or opacity (CAMARON.md). The running card's ring is static on its pseudo-element and the
// pseudo-element fades in and out; the Board's `dk-pulse` animates a box-shadow and stays the Board's.
test('the running wiki card pulses by opacity alone, over a static ring', () => {
  const after = css.match(/\.dk-wiki\.is-generating::after\s*\{([^}]*)\}/)[1]
  const name = after.match(/animation:\s*([\w-]+)/)[1]
  expect(name).not.toBe('dk-pulse')
  expect(after).toMatch(/box-shadow:\s*0 0 0 4px color-mix\(in srgb, var\(--tone\) 30%, transparent\)/)
  const body = css.match(new RegExp(`@keyframes ${name}\\s*\\{((?:[^{}]|\\{[^}]*\\})*)\\}`))[1]
  const props = [...body.matchAll(/\{([^}]*)\}/g)].flatMap(([, decls]) => [...decls.matchAll(/([\w-]+)\s*:/g)].map((m) => m[1]))
  expect(props.length).toBeGreaterThan(0)
  expect(new Set(props)).toEqual(new Set(['opacity']))
})

// The shrimp (sections/Shrimp.jsx): its three motions move by transform or opacity alone and stand still for who asked
// for less motion. The tail's group carries a `translate(…)` attribute that a CSS `transform` replaces, so the flick
// repeats that translate: it must stay the favicon's own.
const keyframes = (name) => css.match(new RegExp(`@keyframes ${name}\\s*\\{((?:[^{}]|\\{[^}]*\\})*)\\}`))?.[1] ?? ''
const declared = (body) => [...body.matchAll(/\{([^}]*)\}/g)].flatMap(([, decls]) => [...decls.matchAll(/([\w-]+)\s*:/g)].map((m) => m[1]))

test.each(['dk-shrimp-sway', 'dk-shrimp-flick', 'dk-shrimp-dot'])('%s moves by transform and opacity alone', (name) => {
  const props = declared(keyframes(name))
  expect(props.length).toBeGreaterThan(0)
  expect(props.filter((p) => !['transform', 'opacity'].includes(p))).toEqual([])
})

test('each shrimp state runs its own motion, and none of them runs for who asked for less', () => {
  expect(css).toMatch(/\.dk-shrimp\.thinking \.shrimp-antennae\s*\{[^}]*animation:\s*dk-shrimp-sway 1\.6s ease-in-out infinite/)
  expect(css).toMatch(/\.dk-shrimp\.answering \.shrimp-tail\s*\{[^}]*animation:\s*dk-shrimp-flick \.5s ease-in-out infinite/)
  expect(css).toMatch(/\.dk-shrimp-dots i\s*\{[^}]*animation:\s*dk-shrimp-dot 1\.2s ease-in-out infinite/)
  expect(css).not.toMatch(/\.dk-shrimp\.idle[^{]*\{[^}]*animation/)
  const reduced = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'))
  expect(reduced).toMatch(
    /\.dk-shrimp\.thinking \.shrimp-antennae[^{]*\.dk-shrimp\.answering \.shrimp-tail[^{]*\.dk-shrimp-dots i[^{]*\{\s*animation:\s*none/)
})

// A motion that starts or ends away from the drawing's pose snaps when its state begins and ends: both rest at no turn at 0%
// and 100%, the swing happens in between.
test.each(['dk-shrimp-sway', 'dk-shrimp-flick'])('%s starts and ends at the favicon\'s pose', (name) => {
  const body = keyframes(name)
  const rest = body.match(/(?:^|\})\s*0%,\s*100%\s*\{([^}]*)\}/)
  expect(rest, name).not.toBeNull()
  expect(rest[1]).toMatch(/transform:\s*(?:translate\([^)]*\)\s*)?rotate\(0deg\)\s*;?\s*$/)
  const turns = [...body.matchAll(/rotate\((-?[\d.]+)deg\)/g)].map((m) => Number(m[1]))
  expect(Math.min(...turns)).toBeLessThan(0)
  expect(Math.max(...turns)).toBeGreaterThan(0)
})

// The part of an answer not revealed yet keeps its room (hidden, not removed), so the answer never grows while it fills in.
test('the unrevealed rest of an answer is hidden but keeps its place', () => {
  expect(rule('.dk-answer-rest')).toMatch(/visibility:\s*hidden/)
  expect(rule('.dk-answer-rest')).not.toMatch(/display:\s*none/)
})

test('the tail flicks about the apex of its fan, the translate the favicon gives its group', () => {
  const favicon = readFileSync(new URL('../../../portal/app/public/favicon.svg', import.meta.url), 'utf-8')
  const [, x, y] = favicon.match(/class="shrimp-tail"\s+transform="translate\(([\d.]+) ([\d.]+)\)"/)
  const turns = [...keyframes('dk-shrimp-flick').matchAll(/transform:\s*([^;}]*)/g)].map((m) => m[1].trim())
  expect(turns.length).toBeGreaterThan(1)
  for (const t of turns) expect(t).toMatch(new RegExp(`^translate\\(${x}px,\\s*${y}px\\)\\s+rotate\\(`))
  expect(css).toMatch(/\.shrimp-tail\s*\{[^}]*transform-origin:\s*0 0/)
})

test('the shrimp is sized in rem and its dots take their colour from the theme', () => {
  expect(px(rule('.dk-shrimp'), 'width')).toBeGreaterThan(0)
  expect(px(rule('.dk-shrimp'), 'height')).toBeGreaterThan(0)
  expect(rule('.dk-shrimp-dots i')).toMatch(/background:\s*var\(--color-ink-dim\)/)
})

// The spec puts the thinking dots above the head, over the drawing's own box, not beside it; for who asked for less motion
// they go, and the label alone says the state.
test('the dots rise above the shrimp and go for who asked for less motion', () => {
  expect(rule('.dk-shrimp-box')).toMatch(/position:\s*relative/)
  expect(rule('.dk-shrimp-dots')).toMatch(/position:\s*absolute/)
  expect(rule('.dk-shrimp-dots')).toMatch(/bottom:\s*100%/)
  const reduced = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'))
  expect(reduced).toMatch(/\.dk-shrimp-dots\s*\{\s*display:\s*none/)
})

// The Docs chat (sections/DocsChat.jsx): beside the page, a column of its own that the page's grid gives room to; in a narrow
// window a drawer over the page. It rises in by transform and opacity, and stands still for who asked for less motion.
const narrowChat = () => css.match(/@media \(max-width: 68rem\)\s*\{((?:[^{}]|\{[^}]*\})*)\}/)[1].match(/\.dk-chat\s*\{([^}]*)\}/)[1]
test('the chat is a column beside the page and a drawer in a narrow window, and rises in only for who wants motion', () => {
  expect(rule('.dk-docs.with-chat')).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)\s+24rem/)
  expect(rule('.dk-docs > .dk-page')).toMatch(/min-width:\s*0/)
  expect(rule('.dk-chat')).toMatch(/animation:\s*dk-rise\b/)
  expect(rule('.dk-chat')).toMatch(/width:\s*24rem/)
  expect(rule('.dk-chat-list')).toMatch(/overflow-y:\s*auto/)
  expect(rule('.dk-chat-list')).toMatch(/min-height:\s*0/)
  const narrow = css.match(/@media \(max-width: 68rem\)\s*\{((?:[^{}]|\{[^}]*\})*)\}/)[1]
  const drawer = narrowChat()
  expect(drawer).toMatch(/width:\s*min\(24rem,\s*100vw\)/)
  expect(drawer).toMatch(/background:\s*var\(--color-canvas-elevated\)/)
  const z = +drawer.match(/z-index:\s*(\d+)/)[1]
  expect(z).toBeGreaterThan(+rule('.dk-term-max').match(/z-index:\s*(\d+)/)[1])
  expect(z).toBeLessThan(+rule('.dk-tour').match(/z-index:\s*(\d+)/)[1])
  expect(narrow).toMatch(/\.dk-docs\.with-chat\s*\{\s*grid-template-columns:\s*minmax\(0,\s*1fr\)/)
  const reduced = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'))
  expect(reduced).toMatch(/\.dk-chat\s*\{\s*animation:\s*none/)
})

// The panel takes its rectangle from the main pane (the --dk-main anchor, as the maximised terminal does), never from a sum of
// the shell's sizes: the jobs panel opens and closes under the pane and the pane is what is left. Docked, it keeps the pane's
// padding as its margin; as a drawer it is the pane's right edge, so it never covers the title bar, the jobs bar or the status bar.
test('the chat panel is sized and placed by the main pane, docked and as a drawer', () => {
  const chat = [...css.matchAll(/([^{}]*)\{([^}]*)\}/g)].filter(([, sel]) => /\.dk-chat(?![\w-])/.test(sel)).map(([, , body]) => body)
  expect(chat.length).toBeGreaterThan(2)
  for (const body of chat) {
    expect(body).not.toMatch(/11\.25rem/)
    expect(body).not.toMatch(/calc\(\s*100s?vh/)
  }
  expect(css).toMatch(/\.dk-main\s*\{[^}]*anchor-name:\s*--dk-main/)
  const docked = rule('.dk-chat')
  expect(docked).toMatch(/position:\s*fixed/)
  expect(docked).toMatch(/position-anchor:\s*--dk-main/)
  expect(docked).toMatch(/inset:\s*anchor\(top\)\s+anchor\(right\)\s+anchor\(bottom\)\s+auto/)
  expect(docked).not.toMatch(/(?:^|[\s;])(?:min-)?height:/)
  const drawer = narrowChat()
  expect(drawer).not.toMatch(/(?:^|[\s;])(?:position|position-anchor|inset|top|right|bottom|height):/)   // the pane's rectangle, as docked
  expect(drawer).toMatch(/margin:\s*0/)
})

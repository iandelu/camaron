---
name: Camarón
description: Many repos, one clear story. Local documentation you can explore, review and trust.
colors:
  printers-ink: "#0a0a0a"
  warm-paper: "#fafaf7"
  paper-raised: "#ffffff"
  ink-soft: "#4a4a4a"
  ink-dim: "#6b6b6b"
  rule: "rgba(10, 10, 10, 0.08)"
  signal-violet: "#6d28d9"
  state-good: "#166534"
  state-warn: "#92400e"
  state-bad: "#b91c1c"
  shrimp-coral: "#ff8a5b"
  aurora-cyan: "#6ec8ff"
  aurora-violet: "#b89aff"
  aurora-pink: "#ff9ec4"
  aurora-amber: "#ffb56b"
typography:
  display:
    fontFamily: "Big Shoulders, Arial Narrow, Impact, sans-serif"
    fontSize: "clamp(2rem, 4vw, 3.5rem)"
    fontWeight: 600
    lineHeight: 0.95
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Big Shoulders, Arial Narrow, Impact, sans-serif"
    fontSize: "2.6rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.45rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    letterSpacing: "0.08em"
  mono:
    fontFamily: "ui-monospace, SF Mono, Menlo, Monaco, Cascadia Code, Consolas, monospace"
    fontSize: "0.8125rem"
    fontWeight: 500
  wordmark:
    fontFamily: "Big Shoulders, Arial Narrow, Impact, sans-serif"
    fontSize: "1.45rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.01em"
rounded:
  chico: "3px"
  control: "4px"
  tarjeta: "6px"
components:
  button-primary:
    backgroundColor: "{colors.printers-ink}"
    textColor: "{colors.paper-raised}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-secondary:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.printers-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-secondary-hover:
    backgroundColor: "{colors.warm-paper}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.state-bad}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-sm:
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "32px"
  input:
    backgroundColor: "{colors.warm-paper}"
    textColor: "{colors.printers-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "40px"
  chip:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.chico}"
    padding: "0 8px"
    height: "24px"
  card:
    backgroundColor: "{colors.paper-raised}"
    rounded: "{rounded.tarjeta}"
    padding: "16px 18px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.chico}"
    padding: "0 12px"
    height: "36px"
  nav-item-active:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.printers-ink}"
  kbd:
    backgroundColor: "{colors.warm-paper}"
    textColor: "{colors.ink-dim}"
    typography: "{typography.mono}"
    rounded: "{rounded.chico}"
    height: "20px"
---

# Design System: Camarón

## Overview

**Creative North Star: "The Ink Console"**

Near-black ink on warm paper, at a console's density. Camarón's two surfaces, the portal where people read and the
desktop app where they operate, share one theme (`.camarones/ui/theme/tokens.css`) and one component kit
(`.camarones/ui`). Hierarchy comes from space, 1px rules and type weight, not from colour or shadow. The accent is not
a hue: it is the highest-contrast ink the canvas allows, so a primary action reads as a solid black block in light
mode and a solid paper block in dark mode.

Colour speaks only about state. Green, amber and red appear next to the word they qualify (confirmed, stale, failed),
and the one chromatic voice outside state is Signal Violet: links, the focus ring and informational labels. The aurora
colours are weather, not ink: soft radial washes behind the Home hero and an amber glow while something is running.
Motion happens only when something changes, with transform and opacity alone.

Big Shoulders, a condensed impact face, carries the wordmark and page titles; Inter carries everything people read
and operate. The look started from Cofundo's visual language, adapted for Camarón in
`.claude/skills/cofundo-design-system/CAMARON.md`; this file records what ships today.

**Key Characteristics:**

- Ink on warm paper, light theme canonical, dark theme derived with the same token names.
- Console density: `-sm` and meta sizes in views; display sizes only on the Home hero.
- Nearly square corners: 3px, 4px, 6px. Nothing rounder.
- Flat at rest; shadows only for what floats.
- State colour always beside its word; text at 4.5:1 in both themes.
- No icon system: text glyphs, with a short list of approved inline-SVG exceptions.
- Fonts self-hosted, no third-party requests.

## Colors

A monochrome ink system with one violet signal, three state colours and a five-colour aurora kept off the text.

### Primary

- **Printer's Ink** (`printers-ink`): the accent and the main text colour. Fills primary buttons, the selected project
  in the desktop rail and the active marker of the docs tree. In dark mode it flips to paper (`#f2f1ec`) and its
  partner `--color-on-accent` flips to `#121211`.
- **Signal Violet** (`signal-violet`): links, the one focus ring, informational chips and labels, number highlighting
  in code. It is the only accent that is a hue, and it never fills a surface. Dark: `#b9a3ff`.

### Tertiary

- **Shrimp Coral** (`shrimp-coral`): the shrimp in the favicon and the desktop icons. It also joins the aurora
  wash on the Home hero. Never text.
- **Aurora Cyan, Violet, Pink, Amber** (`aurora-*`): radial washes behind the Home hero (`.aurora-bg`, mixed at half
  strength in dark mode through `--aurora-strength`). Amber also marks live work in the desktop app: a wiki that is
  generating, a scan's current repo, a progress bar's glow. Never text.

### Neutral

- **Warm Paper** (`warm-paper`): the canvas of both apps, and the field background. Dark: `#121211`.
- **Paper Raised** (`paper-raised`): cards, chips, secondary buttons, the active desktop nav item. Dark: `#1b1b19`.
- **Ink Soft** (`ink-soft`): secondary text, ghost buttons, chip text. Dark: `#c4c3bd`.
- **Ink Dim** (`ink-dim`): meta, breadcrumbs, table headers, kbd, the draft state. Dark: `#9a9993`.
- **Rule** (`rule`): every border and divider, 1px. Dark: `rgba(242, 241, 236, 0.1)`.
- The portal mixes one more tone from these, the panel (`color-mix(in oklch, ink 5%, canvas)`), for hovered and
  selected rows in the docs tree.

### State

- **State Good** (`state-good`, dark `#6fcf8f`): confirmed pages, passing checks.
- **State Warn** (`state-warn`, dark `#f0b36b`): needs reconfirmation, stale generated blocks, warnings.
- **State Bad** (`state-bad`, dark `#ff8f8f`): failures, vulnerable libraries, danger buttons.

### Named Rules

**The Ink-Not-Hue Rule.** The accent is the highest-contrast ink, not a colour. Primary actions are solid ink; a hue
never marks importance.

**The State-Wears-Its-Word Rule.** A state colour never stands alone. The dot, the 3px rail or the coloured chip text
always sits beside the word that names the state.

**The Aurora-Is-Weather Rule.** Aurora colours are backgrounds and glows only, never text. On the aurora wash, muted
text steps up from Ink Dim to Ink Soft to keep 4.5:1.

## Typography

**Display Font:** Big Shoulders (with Arial Narrow, Impact)
**Body Font:** Inter (with ui-sans-serif, system-ui, Segoe UI, Roboto)
**Label/Mono Font:** ui-monospace (SF Mono, Menlo, Cascadia Code, Consolas)

**Character:** A condensed poster face for names and titles over a neutral workhorse sans. The impact face makes
every page title feel like a label on a drawer; Inter keeps the dense console legible.

### Hierarchy

- **Display** (600, `clamp(2rem, 4vw, 3.5rem)`, 0.95): the Home hero title only. The larger `--text-display-lg` and
  `-xl` tokens exist but no view uses them.
- **Headline** (600, 2.6rem, 1): the title of every portal page and the architecture view, in Big Shoulders.
- **Title** (600, 1.45rem, 1.3, −0.025em): section headings inside a doc page, with a rule above them. Doc h3 is
  1.15rem, h4 1rem.
- **Body** (400, 1.0625rem, 1.6): portal reading text, in a 48rem column (64rem for wide pages).
- **Body small** (400, 0.9375rem, 1.5): the desktop app's base size, buttons, fields and the tabs of a board.
- **Label** (600, 0.6875rem, 0.08em, uppercase): eyebrows, the group titles of the docs tree and the outline.
- **Mono** (500, 0.8125rem): figures, versions, file paths, commands, keyboard keys.
- **Wordmark** (700, 1.45rem): «camarón», lowercase, with the project name stacked under it in label size and Ink Dim.

### Named Rules

**The Console Density Rule.** Views use body-small, meta (0.8125rem) and micro (0.6875rem). Display sizes belong to
the Home hero and to the desktop ADR review's presentation mode (`P` to enter), nowhere else.

**The Figures-in-Mono Rule.** Counts, versions, costs and paths are set in mono, so numbers line up and read as data.

## Layout

**Portal.** A sticky 3.5rem top bar (canvas at 88% with a 10px backdrop blur), then three columns: the docs tree
(17rem), the page, and the outline (14rem), capped at 96rem. The reading column is 48rem; diagrams break out of it up
to 76rem so a wide flow reads without zooming. Viewers (C4, code graph) drop the outline and take the full width. Home
and zone covers keep the zone list but hide the docs tree. Breakpoints at 1200px (outline goes), 900px (the tree
becomes a drawer behind a scrim) and 640px.

**Desktop app.** A window-filling grid modelled on VS Code and Linear: the title bar (3.5rem, draggable), a 4rem rail
of project tiles, a 13rem list of sections, the content, a jobs panel docked under the content, and a 1.75rem status
bar. It narrows at 68rem and 900px.

**Rhythm.** No spacing tokens; the code repeats a small rem scale: 0.25, 0.5, 0.75, 1, 1.25rem for gaps and padding,
2.25 to 3rem for the portal's page padding. Grids use `auto-fit` with a `minmax(15rem, 1fr)` floor for tiles.

## Elevation & Depth

Flat by default. Depth comes from tonal layering (Warm Paper → Paper Raised → the panel tint) and 1px Rule borders.
Shadows exist only for things that float over the page: menus and the command palette, hovered floating cards,
modals. State is drawn with inset strokes rather than lift: a 3px inset rail in a state colour on a vulnerable library
row or a stale wiki, an inset 1px ring on the active nav item.

### Shadow Vocabulary

- **Menu** (`--sombra-menu: 0 12px 28px -18px rgba(0, 0, 0, 0.35)`): dropdowns, the palette, popovers.
- **Hover** (`--sombra-hover: 0 24px 48px -24px rgba(10, 10, 10, 0.18)`): a floating card under the pointer.
- **Modal** (`--sombra-modal: 0 40px 80px -24px rgba(10, 10, 10, 0.4)`): dialogs.
- Dark mode deepens all three (0.5 to 0.7 black).

### Named Rules

**The Space-Before-Shadow Rule.** Resting surfaces never cast a shadow. If two areas need separating, use space or a
1px rule first.

## Shapes

Nearly square. Three radii carry the whole system: 3px for small parts (chips, kbd, nav items, inline code), 4px for
controls (buttons, fields, the project tiles), 6px for cards and dialogs. `tokens.test.js` keeps every radius token at
6px or less; the token named `--radius-pildora` keeps its name for old rules but holds 4px. Circles appear only as
status dots. Borders are 1px Rule; a dashed border means "empty" or "draft" (empty states, the draft trust pill, the
add-project tile).

Known drift: a few legacy portal rules in `portal/app/src/portal.css` still draw 99px pills (`.pill`, `.count`,
`.chip`, the generated-block badge), the docs-tree links use 7px and the banner 8px. They predate the square rule and
are not a pattern to copy.

## Components

**Character: tactile and confident.** Controls are firm, generously sized (40px default) and answer every
interaction: hover shifts the surface, press gives a small scale (0.98) in the portal, focus draws one unmistakable
violet ring, busy keeps full opacity while its label shimmers. The shared `.cu-btn` does not yet have the press
response the portal's buttons have.

### Buttons

- **Shape:** nearly square (4px), 40px tall; small variant 32px.
- **Primary:** solid Printer's Ink with Paper Raised text, 0 16px padding, body-small 500. Hover drops to 88% opacity.
- **Secondary (default):** Paper Raised with a 1px Rule border and ink text; hover shifts to Warm Paper.
- **Ghost:** transparent, Ink Soft text, no border.
- **Danger:** transparent with a `currentColor` border in State Bad.
- **Focus / Disabled / Busy:** the shared 2px Signal Violet ring at 2px offset; disabled at 50% opacity with a
  not-allowed cursor; busy (`aria-busy`) stays at full opacity with a progress cursor.

### Chips

- **Style:** 24px tall, 3px corners, Paper Raised with a 1px Rule border, meta size in Ink Soft.
- **State:** `--ok`, `--warn`, `--bad` and `--info` variants change only the text colour; the chip's word is the state.

### Cards / Containers

- **Corner Style:** 6px.
- **Background:** Paper Raised on Warm Paper.
- **Shadow Strategy:** none at rest (see Elevation).
- **Border:** 1px Rule.
- **Internal Padding:** 1rem × 1.1rem, with a 0.75rem gap between children.
- **Notices** (`cu-aviso`) use the same frame at 4px with a coloured title; **empty states** use a dashed border, a
  title, one line of explanation and always a way out.

### Inputs / Fields

- **Style:** 40px tall, Warm Paper fill (one step below the card), 1px Rule, 4px corners, body-small.
- **Label:** meta 500 in ink above the field; the matching CLI flag can sit beside it in mono micro.
- **Focus:** the shared Signal Violet ring.

### Navigation

- **Desktop sections:** 36px rows, 3px corners, Ink Soft text; hover lifts to Paper Raised; active is Paper Raised,
  ink, weight 500 and an inset 1px Rule ring. Section groups are introduced by label-style eyebrows.
- **Desktop rail:** 40px project tiles with their initials; the open project is solid ink, adding a project is a
  dashed tile.
- **Portal docs tree:** muted links that turn ink on hover; the current page gets the panel tint, weight 600 and a 2px
  ink bar on its left edge. Each page shows its trust dot (filled green confirmed, filled amber needs reconfirmation,
  hollow outline draft).
- **Breadcrumbs** head every view in both apps, meta size in Ink Dim, the current page in ink.

### Trust Pill (signature)

The page header's trust state, the product's core promise made visible. Confirmed: State Good text with a border
mixed 35% toward green. Draft: Ink Dim text with a dashed border. Needs reconfirmation: State Warn text with a 40%
amber border. Freshness icons (fresh, changed, missing, unchecked) sit beside it as inline SVG, always next to their
word.

### Health Tile (signature)

Quality at a glance: a 6px card with a 3px left border in the state colour, its name, the state word in that colour
and figures in mono at 1.35rem.

### Thinking Label (signature)

While an agent works, its label shimmers: a band of full ink swept across Ink Dim (or Signal Violet inside an info
chip), 1.4s linear. Both ends are text colours at 4.5:1, so the word reads at every frame; under reduced motion it
stands still.

## Do's and Don'ts

### Do:

- **Do** take every value from `.camarones/ui/theme/tokens.css` (`--color-*`, `--text-*`, `--consola-radio-*`,
  `--sombra-*`, `--ease-*`, `--duration-*`); views never hold a raw colour.
- **Do** keep text at 4.5:1 in both themes, and step muted text up to Ink Soft on the aurora wash.
- **Do** put the state's word beside every state colour: dot, rail, chip or tile.
- **Do** use the one focus ring: 2px solid Signal Violet, 2px offset.
- **Do** keep corners at 3px (small parts), 4px (controls) and 6px (cards, dialogs).
- **Do** give every control at least a 24px target; default buttons and fields are 40px.
- **Do** move only `transform` and `opacity`, with `--ease-out-soft` and 200 / 400 / 800ms, and stand still under
  `prefers-reduced-motion`.
- **Do** serve fonts from `.camarones/ui/theme/fonts/` and nothing from a CDN.

### Don't:

- **Don't** draw 99px pills or radii above 6px; the legacy `.pill`, `.count` and `.chip` rules are drift.
- **Don't** set text in an aurora colour or in Shrimp Coral.
- **Don't** use display sizes outside the Home hero and the ADR presentation mode.
- **Don't** give resting cards a shadow.
- **Don't** add an icon set or let emoji stand in for words; inline SVG only in the exceptions listed in `CAMARON.md`.
- **Don't** draw the shrimp a second time: the favicon (`portal/app/public/favicon.svg`) is the one drawing of the
  mark.
- **Don't** tell a state by colour alone.

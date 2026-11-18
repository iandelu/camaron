// The animated shrimp is the favicon's own markup (CAMARON.md > Icons), so it is read, never redrawn: the inner
// markup, minus the ink tile, with the favicon's two colours swapped for the theme's tokens.
const TOKENS = { '#ff8a5b': 'var(--color-aurora-coral)', '#0a0a0a': 'var(--color-canvas)' }

export const shrimpMarkup = (svg) => {
  const inner = /<svg\b[^>]*>([\s\S]*)<\/svg>/.exec(svg)?.[1] ?? ''
  return inner
    .replace(/<rect\b[^>]*\/>/g, '')
    .replace(/#(?:ff8a5b|0a0a0a)\b/gi, (hex) => TOKENS[hex.toLowerCase()])
    .trim()
}

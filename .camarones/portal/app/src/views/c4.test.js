import { expect, test } from 'vitest'
import { splitElements, viewFile } from './c4.js'

test('what still needs review stays open; what a person confirmed folds away', () => {
  const els = [
    { fqn: 'a', draft: true, confirmed: false },
    { fqn: 'b', draft: false, confirmed: true },
    { fqn: 'c', draft: false, confirmed: false },
    { fqn: 'd', draft: true, confirmed: true },
  ]
  const { pending, confirmed } = splitElements(els)
  expect(pending.map((e) => e.fqn)).toEqual(['a', 'c', 'd'])
  expect(confirmed.map((e) => e.fqn)).toEqual(['b'])
  expect(splitElements([])).toEqual({ pending: [], confirmed: [] })
})

test("a view's file reads where the model lives: docs/architecture, or the repo folder workspace.yaml names", () => {
  expect(viewFile({}, 'views.c4')).toBe('architecture/views.c4')
  expect(viewFile({ c4Source: null }, 'repos/api.c4')).toBe('architecture/repos/api.c4')
  expect(viewFile({ c4Source: 'nasa:docs/04-architecture' }, 'views.c4')).toBe('nasa:docs/04-architecture/views.c4')
  expect(viewFile({ c4Source: 'nasa:.' }, 'views.c4')).toBe('nasa:views.c4')
})

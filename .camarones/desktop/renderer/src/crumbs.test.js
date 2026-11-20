import { expect, test } from 'vitest'
import { crumbs } from './crumbs.js'

const es = { 'nav.docs': 'Docs', 'nav.decisions': 'Decisiones', 'nav.flow': 'Flujo', 'nav.plan': 'Plan', 'nav.board': 'Tablero', 'adr.new': 'Nuevo ADR' }
const t = (k) => es[k] ?? k

test('breadcrumbs follow the place, its view and the ADR', () => {
  expect(crumbs({ hash: '#/docs/decisions/0012', project: 'petclinic', t })).toEqual([
    { label: 'petclinic', href: '#/flow' }, { label: 'Docs', href: '#/docs' },
    { label: 'Decisiones', href: '#/docs/decisions' }, { label: 'ADR 0012' }])
  expect(crumbs({ hash: '#/docs/decisions', project: 'p', t })).toEqual([{ label: 'p', href: '#/flow' }, { label: 'Docs', href: '#/docs' }, { label: 'Decisiones' }])
  expect(crumbs({ hash: '#/flow', project: 'p', t })).toEqual([{ label: 'p', href: '#/flow' }, { label: 'Flujo' }])
  expect(crumbs({ hash: '#/flow/plan', project: 'p', t })).toEqual([{ label: 'p', href: '#/flow' }, { label: 'Flujo', href: '#/flow' }, { label: 'Plan' }])
  expect(crumbs({ hash: '#/board', project: '', t })).toEqual([{ label: '…', href: '#/flow' }, { label: 'Tablero' }])
  expect(crumbs({ hash: '#/flow/repo/api', project: 'p', t })).toEqual([{ label: 'p', href: '#/flow' }, { label: 'Flujo', href: '#/flow' }, { label: 'api' }])
})

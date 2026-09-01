import assert from 'node:assert/strict'
import test from 'node:test'
import type { RoutePreset } from '../src/bridge/contracts.ts'
import { matrixEntries, matrixRouteOrder, zeroEntry } from '../src/components/routing-matrix-model.ts'

const routes: RoutePreset[] = Array.from({ length: 9 }, (_, index) => ({
  routeId: String(index + 1),
  label: `Route ${index + 1}`,
  relativeDestination: `Destination/${index + 1}`,
  category: null,
  genre: null,
}))

test('matrix preserves the physical numpad order', () => {
  assert.deepEqual(matrixRouteOrder, ['7', '8', '9', '4', '5', '6', '1', '2', '3'])
  assert.deepEqual(matrixEntries(routes, null, null, null).map((entry) => entry.route.routeId), matrixRouteOrder)
})

test('matrix is visible but idle without a selected track', () => {
  const entries = matrixEntries(routes, null, null, null)
  assert.ok(entries.every((entry) => entry.state === 'idle'))
  assert.equal(zeroEntry(null).state, 'holding')
  assert.equal(zeroEntry(null).hint, 'Select a track first')
})

test('selected track enables routes and active route wins over recent state', () => {
  const entries = matrixEntries(routes, 'track-1', '5', '3')
  assert.ok(entries.filter((entry) => !['5', '3'].includes(entry.route.routeId)).every((entry) => entry.state === 'available'))
  assert.equal(entries.find((entry) => entry.route.routeId === '5')?.state, 'active')
  assert.equal(matrixEntries(routes, 'track-1', null, '3').find((entry) => entry.route.routeId === '3')?.state, 'recent')
  assert.equal(zeroEntry('track-1').state, 'holding')
  assert.equal(zeroEntry('track-1').hint, 'Drop here to route')
})

test('empty route labels are explicit instead of pretending to be available', () => {
  const emptyRoutes = routes.map((route) => route.routeId === '8' ? { ...route, label: '' } : route)
  const entry = matrixEntries(emptyRoutes, 'track-1', null, null).find((item) => item.route.routeId === '8')
  assert.equal(entry?.state, 'unassigned')
  assert.equal(entry?.displayLabel, 'Unassigned')
})

test('destination conflicts expose a blocked route state', () => {
  const entry = matrixEntries(routes, 'track-1', null, null, '5').find((item) => item.route.routeId === '5')
  assert.equal(entry?.state, 'blocked')
})

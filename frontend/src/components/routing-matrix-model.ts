import type { RoutePreset } from '../bridge/contracts'

export const matrixRouteOrder = ['7', '8', '9', '4', '5', '6', '1', '2', '3'] as const

export type MatrixRouteState = 'idle' | 'available' | 'active' | 'recent' | 'blocked' | 'unassigned'

export type MatrixEntry = {
  route: RoutePreset
  state: MatrixRouteState
  displayLabel: string
  hint: string
}

export type ZeroEntry = {
  state: 'holding'
  displayLabel: 'Current Crate'
  hint: 'Select a track first' | 'Drop here to route'
}

export function matrixEntries(routes: RoutePreset[], selectedTrackId: string | null, activeRouteId: string | null, recentRouteId: string | null, blockedRouteId: string | null = null): MatrixEntry[] {
  const byId = new Map(routes.map((route) => [route.routeId, route]))
  return matrixRouteOrder.map((routeId) => {
    const route = byId.get(routeId) ?? {
      routeId,
      label: '',
      relativeDestination: '',
      category: null,
      genre: null,
    }
    const configured = Boolean(route.label.trim() && route.relativeDestination.trim())
    const state: MatrixRouteState = !configured
      ? 'unassigned'
      : blockedRouteId === routeId
        ? 'blocked'
      : activeRouteId === routeId
        ? 'active'
        : recentRouteId === routeId
          ? 'recent'
          : selectedTrackId
            ? 'available'
            : 'idle'
    return {
      route,
      state,
      displayLabel: configured ? route.label : 'Unassigned',
      hint: selectedTrackId ? `Assign to Route ${routeId} · Press ${routeId}` : `Select a track to assign to Route ${routeId}`,
    }
  })
}

export function zeroEntry(selectedTrackId: string | null): ZeroEntry {
  return {
    state: 'holding',
    displayLabel: 'Current Crate',
    hint: selectedTrackId ? 'Drop here to route' : 'Select a track first',
  }
}

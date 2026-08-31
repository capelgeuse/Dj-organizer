import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import type { BridgeReady, BridgeRequest, BridgeResponse, ConfigSnapshot, LibrarySummary, MoveResult } from './contracts'

let requestSequence = 0

function requestId(): string {
  requestSequence += 1
  return `ui-${Date.now()}-${requestSequence}`
}

async function request<T>(command: string, payload: Record<string, unknown> = {}): Promise<T> {
  const request: BridgeRequest = { id: requestId(), command, payload }
  const raw = await invoke<string>('bridge_request', { request: JSON.stringify(request) })
  const response = JSON.parse(raw) as BridgeResponse<T>
  if (!response.ok || response.data === null) {
    throw new Error(response.error?.message ?? 'Local bridge request failed.')
  }
  return response.data
}

export function ping(): Promise<BridgeReady> {
  return request<BridgeReady>('ping')
}

export function loadLibrary(root?: string, sortField?: LibrarySummary['sort']['field'], sortDirection?: LibrarySummary['sort']['direction']): Promise<LibrarySummary> {
  return request<LibrarySummary>('load_library', {
    ...(root ? { root } : {}),
    ...(sortField ? { sortField } : {}),
    ...(sortDirection ? { sortDirection } : {}),
  })
}

export function getConfig(): Promise<ConfigSnapshot> {
  return request<ConfigSnapshot>('get_config')
}

export function setRoot(root: string): Promise<{ root: string; configPath: string }> {
  return request<{ root: string; configPath: string }>('set_root', { root })
}

export function setRoutes(routes: import('./contracts').RoutePreset[]): Promise<{ routes: import('./contracts').RoutePreset[] }> {
  return request<{ routes: import('./contracts').RoutePreset[] }>('set_routes', { routes })
}

export function setRoutePath(routeId: string, path: string, label?: string): Promise<{ routes: import('./contracts').RoutePreset[] }> {
  return request<{ routes: import('./contracts').RoutePreset[] }>('set_route_path', { routeId, path, label })
}

export async function pickDirectory(): Promise<string | null> {
  const selected = await open({ directory: true, multiple: false, title: 'Choose your local music root' })
  return typeof selected === 'string' ? selected : null
}

export function moveTrack(trackId: string, routeId: string): Promise<MoveResult> {
  return request<MoveResult>('move_track', { trackId, routeId })
}

export function shutdownBridge(): Promise<{ shuttingDown: boolean }> {
  return request<{ shuttingDown: boolean }>('shutdown')
}

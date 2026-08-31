export type BridgeError = {
  code: string
  message: string
  retryable: boolean
}

export type BridgeResponse<T> = {
  id: string
  ok: boolean
  data: T | null
  error: BridgeError | null
}

export type TrackRecord = {
  trackId: string
  sourcePath: string
  relativePath: string
  name: string
  title: string | null
  artist: string | null
  bpm: number | null
  genre: string | null
  durationSeconds: number | null
  artworkUri: string | null
}

export type LibrarySummary = {
  root: string
  totalTracks: number
  returnedTracks: number
  hasMore: boolean
  sort: {
    field: 'name' | 'title' | 'artist' | 'bpm' | 'genre' | 'duration'
    direction: 'asc' | 'desc'
  }
  tracks: TrackRecord[]
}

export type BridgeReady = {
  ready: boolean
  protocolVersion: number
}

export type MoveResult = {
  status: 'moved' | 'destination_exists' | 'invalid_route' | 'source_missing' | 'failed' | 'cancelled'
  trackId: string
  sourcePath: string
  destinationPath: string | null
  operationId: string | null
  error: BridgeError | null
}

export type RoutePreset = {
  routeId: string
  label: string
  relativeDestination: string
  category: string | null
  genre: string | null
}

export type ConfigSnapshot = {
  root: string
  routes: RoutePreset[]
  configPath: string
}

export type BridgeRequest = {
  id: string
  command: string
  payload: Record<string, unknown>
}

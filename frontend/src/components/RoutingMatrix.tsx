import { useMemo, useState } from 'react'
import type { RoutePreset } from '../bridge/contracts'
import { matrixEntries, zeroEntry } from './routing-matrix-model'

type RoutingMatrixProps = {
  routes: RoutePreset[]
  selectedTrackId: string | null
  activeRouteId: string | null
  recentRouteId: string | null
  blockedRouteId: string | null
  disabled: boolean
  draggingTrackId: string | null
  onRoute: (routeId: string, trackId?: string) => void
  onConfigure: () => void
}

function detailFor(route: RoutePreset): string {
  return route.category ?? route.genre ?? (route.relativeDestination || 'Not assigned')
}

export function RoutingMatrix({ routes, selectedTrackId, activeRouteId, recentRouteId, blockedRouteId, disabled, draggingTrackId, onRoute, onConfigure }: RoutingMatrixProps) {
  const entries = useMemo(() => matrixEntries(routes, selectedTrackId, activeRouteId, recentRouteId, blockedRouteId), [activeRouteId, blockedRouteId, recentRouteId, routes, selectedTrackId])
  const zero = zeroEntry(selectedTrackId)
  const rows = [entries.slice(0, 3), entries.slice(3, 6), entries.slice(6, 9)]
  const [dragOverRouteId, setDragOverRouteId] = useState<string | null>(null)

  function dropTrack(event: React.DragEvent<HTMLButtonElement>) {
    event.preventDefault()
    setDragOverRouteId(null)
    const trackId = event.dataTransfer.getData('text/plain') || draggingTrackId
    if (trackId) onRoute(event.currentTarget.dataset.routeId ?? '', trackId)
  }

  return (
    <section className="routing-matrix" aria-labelledby="routing-matrix-title">
      <div className="routing-matrix-heading">
        <div>
          <p className="eyebrow">DJ UTILITY</p>
          <h3 id="routing-matrix-title">Routing Matrix</h3>
        </div>
        <span className={`routing-selection ${selectedTrackId ? 'has-selection' : ''}`}>{selectedTrackId ? 'READY' : 'IDLE'}</span>
      </div>
      <p className="routing-matrix-copy">Physical numpad map · click, press 1–9, or drag a track onto a route.</p>
      <div className="routing-matrix-grid" aria-label="Numpad routing destinations">
        {rows.map((row, rowIndex) => (
          <div className="routing-matrix-row" key={rowIndex}>
            {row.map((entry) => (
              <button
                className={`routing-slot routing-slot-${entry.state} ${dragOverRouteId === entry.route.routeId && draggingTrackId ? 'routing-slot-drop-target' : ''}`}
                data-route-id={entry.route.routeId}
                disabled={disabled || entry.state === 'unassigned' || entry.state === 'blocked' || !selectedTrackId}
                key={entry.route.routeId}
                aria-keyshortcuts={entry.route.routeId}
                aria-pressed={entry.state === 'active'}
                aria-label={`${entry.displayLabel}, Route ${entry.route.routeId}, ${entry.state}`}
                onClick={() => onRoute(entry.route.routeId)}
                onDragOver={(event) => { if (!disabled && entry.state !== 'unassigned') { event.preventDefault(); setDragOverRouteId(entry.route.routeId) } }}
                onDragLeave={() => { if (dragOverRouteId === entry.route.routeId) setDragOverRouteId(null) }}
                onDrop={dropTrack}
                title={entry.hint}
                type="button"
              >
                <span className="routing-slot-number">{entry.route.routeId}</span>
                <span className="routing-slot-copy"><strong>{entry.displayLabel}</strong><small>{detailFor(entry.route)}</small></span>
                <span className="routing-slot-state">{entry.state}</span>
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className="routing-holding" onDragOver={(event) => { event.preventDefault() }}>
        <span className="routing-slot-number">0</span>
        <span className="routing-slot-copy"><strong>{zero.displayLabel}</strong><small>Unsorted Queue · holding area</small></span>
        <span className="routing-slot-state">{zero.hint}</span>
      </div>
      <div className="routing-matrix-footer">
        <span>{draggingTrackId ? 'Drop target active' : 'Routes stay visible when idle'}</span>
        <button type="button" className="route-configure-button" onClick={onConfigure} disabled={disabled}>Customize routes</button>
      </div>
    </section>
  )
}

import type { RoutePreset } from '../bridge/contracts'

type RoutePadProps = {
  routes: RoutePreset[]
  selectedTrackId: string | null
  disabled: boolean
  onRoute: (routeId: string) => void
  onConfigure: () => void
}

export function RoutePad({ routes, selectedTrackId, disabled, onRoute, onConfigure }: RoutePadProps) {
  return (
    <section className="route-pad" aria-labelledby="route-pad-title">
      <div className="route-heading"><span id="route-pad-title">Numpad routes</span><small>{selectedTrackId ? 'Move selected track' : 'Select a track first'}</small></div>
      <div className="route-grid">
        {routes.map((route) => <button key={route.routeId} type="button" onClick={() => onRoute(route.routeId)} disabled={disabled || !selectedTrackId} aria-label={`Move selected track to ${route.label}`}><strong>{route.routeId}</strong><span>{route.label}</span></button>)}
      </div>
      <button type="button" className="route-configure-button" onClick={onConfigure} disabled={disabled}>Customize folders</button>
    </section>
  )
}

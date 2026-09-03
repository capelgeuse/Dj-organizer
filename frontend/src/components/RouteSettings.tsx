import { useState } from 'react'
import { pickDirectory, setRoutePath, setRoutes } from '../bridge/desktop-bridge'
import type { RoutePreset } from '../bridge/contracts'

type RouteSettingsProps = {
  routes: RoutePreset[]
  disabled: boolean
  onRoutesChanged: (routes: RoutePreset[]) => void
}

export function RouteSettings({ routes, disabled, onRoutesChanged }: RouteSettingsProps) {
  const [draft, setDraft] = useState(routes)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)


  function update(routeId: string, field: 'label' | 'relativeDestination', value: string) {
    setDraft((current) => current.map((route) => route.routeId === routeId ? { ...route, [field]: value } : route))
  }

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const result = await setRoutes(draft)
      setDraft(result.routes)
      onRoutesChanged(result.routes)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save route settings.')
    } finally {
      setSaving(false)
    }
  }

  async function chooseFolder(route: RoutePreset) {
    setError(null)
    try {
      const selected = await pickDirectory()
      if (!selected) return
      setSaving(true)
      const result = await setRoutePath(route.routeId, selected, route.label)
      setDraft(result.routes)
      onRoutesChanged(result.routes)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not set the route folder.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="route-settings" aria-labelledby="route-settings-title">
      <div className="route-settings-heading"><div><p className="eyebrow">ROUTE SETTINGS</p><h3 id="route-settings-title">Configure Numpad 1–9</h3></div><span>Each key moves directly to one folder</span></div>
      <div className="route-settings-list">
        {draft.map((route) => <div className="route-setting" key={route.routeId}>
          <strong>{route.routeId}</strong>
          <input value={route.label} onChange={(event) => update(route.routeId, 'label', event.target.value)} aria-label={`Label for route ${route.routeId}`} disabled={disabled || saving} />
          <input value={route.relativeDestination} onChange={(event) => update(route.routeId, 'relativeDestination', event.target.value)} aria-label={`Destination for route ${route.routeId}`} disabled={disabled || saving} />
          <button type="button" onClick={() => void chooseFolder(route)} disabled={disabled || saving}>Choose folder</button>
        </div>)}
      </div>
      {error && <p className="route-settings-error" role="alert">{error}</p>}
      <button type="button" className="secondary-button" onClick={() => void save()} disabled={disabled || saving}>{saving ? 'Saving…' : 'Save route labels'}</button>
    </section>
  )
}

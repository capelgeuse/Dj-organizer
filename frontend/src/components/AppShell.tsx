import type { ReactNode } from 'react'

type AppShellProps = {
  bridgeStatus: 'checking' | 'ready' | 'offline'
  previewMode: boolean
  root: string
  onSettings: () => void
  onChangeRoot: () => void
  children: ReactNode
}

export function AppShell({ bridgeStatus, previewMode, root, onSettings, onChangeRoot, children }: AppShellProps) {
  const label = bridgeStatus === 'checking' ? 'Connecting' : bridgeStatus === 'ready' ? 'Bridge Connected' : 'Local Preview'
  return (
    <main className="app-shell" aria-label="CapelHouse local desktop application">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">CH</span>
          <span className="brand-name">CapelHouse</span>
        </div>
        <div className="topbar-breadcrumb" aria-label="Current location"><span>Library</span><b>›</b><strong>Unsorted</strong></div>
        <div className="topbar-actions">
          <div className="root-control"><span className="root-control-label">ROOT</span><span className="root-control-value" title={root}>{previewMode ? 'Local preview' : root || 'No root selected'}</span><button type="button" onClick={onChangeRoot} disabled={bridgeStatus !== 'ready'}>{root && !previewMode ? 'Change' : 'Choose'}</button></div>
          <span className={`status-chip status-chip-${bridgeStatus}`} role="status"><span className="status-dot" aria-hidden="true" />{label}</span>
          <button type="button" className="topbar-icon" onClick={onSettings} aria-label="Open settings">⚙</button>
          <span className="window-controls" aria-hidden="true"><i>−</i><i>□</i><i>×</i></span>
        </div>
      </header>
      {children}
    </main>
  )
}

import type { ReactNode } from 'react'

type AppShellProps = {
  bridgeStatus: 'checking' | 'ready' | 'offline'
  children: ReactNode
}

export function AppShell({ bridgeStatus, children }: AppShellProps) {
  const label = bridgeStatus === 'checking' ? 'Checking bridge' : bridgeStatus === 'ready' ? 'Bridge ready' : 'Bridge not connected'
  return (
    <main className="app-shell" aria-label="CapelHouse local desktop application">
      <header className="app-header">
        <div>
          <p className="eyebrow">CAPELHOUSE / LOCAL DESKTOP</p>
          <h1>Music organizer</h1>
          <p className="subtitle">React + Vite UI · Python remains the local authority</p>
        </div>
        <span className={`status-chip status-chip-${bridgeStatus}`} role="status"><span className="status-dot" aria-hidden="true" />{label}</span>
      </header>
      {children}
      <footer className="app-footer"><span>OFFLINE-FIRST · LOCAL FILESYSTEM · NO REMOTE SERVICE</span><span>Layer A contracts · MVP workflow</span></footer>
    </main>
  )
}

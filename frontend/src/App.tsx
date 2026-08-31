import './App.css'

const destinations = Array.from({ length: 9 }, (_, index) => index + 1)

function App() {
  return (
    <main className="app-shell" aria-label="CapelHouse local desktop application">
      <header className="app-header">
        <div>
          <p className="eyebrow">CAPELHOUSE / LOCAL DESKTOP</p>
          <h1>Music organizer</h1>
          <p className="subtitle">React + Vite UI shell · Python remains the local authority</p>
        </div>
        <span className="status-chip status-chip-warning" role="status">
          <span className="status-dot" aria-hidden="true" />
          Bridge not connected
        </span>
      </header>

      <section className="setup-panel" aria-labelledby="setup-title">
        <div>
          <p className="eyebrow">FIRST CONNECTION</p>
          <h2 id="setup-title">Choose a local music root</h2>
          <p className="body-copy">
            The desktop bridge will load the real library here. No music is uploaded and no browser window is required.
          </p>
        </div>
        <button className="primary-button" type="button" disabled>
          Connect local bridge
        </button>
      </section>

      <section className="workspace-preview" aria-label="Library workspace preview">
        <div className="queue-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">UNSORTED QUEUE</p>
              <h2>Library waiting for bridge</h2>
            </div>
            <span className="count-badge">— tracks</span>
          </div>
          <div className="empty-state">
            <span className="empty-icon" aria-hidden="true">♪</span>
            <strong>No library loaded</strong>
            <span>Python will provide metadata, artwork and the sorted queue.</span>
          </div>
        </div>

        <aside className="control-panel" aria-label="Keyboard and route controls">
          <p className="eyebrow">CONTROL MAP</p>
          <div className="control-row"><kbd>W</kbd><span>Previous song</span></div>
          <div className="control-row"><kbd>S</kbd><span>Next song</span></div>
          <div className="control-row"><kbd>A</kbd><span>Rewind 5 seconds</span></div>
          <div className="control-row"><kbd>D</kbd><span>Fast-forward 5 seconds</span></div>
          <div className="route-heading"><span>Numpad routes</span><small>Configured destinations</small></div>
          <div className="route-grid">
            {destinations.map((destination) => <button key={destination} type="button" disabled>{destination}</button>)}
          </div>
        </aside>
      </section>

      <footer className="app-footer">
        <span>OFFLINE-FIRST · LOCAL FILESYSTEM · NO REMOTE SERVICE</span>
        <span>Layer A contracts ready · P0 complete</span>
      </footer>
    </main>
  )
}

export default App

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { getConfig, moveTrack, pickDirectory, ping, scanLibrary, setRoot as persistRoot, undoLastMove } from './bridge/desktop-bridge'
import type { LibrarySummary, MoveResult, RoutePreset, TrackRecord } from './bridge/contracts'
import { AppShell } from './components/AppShell'
import { AudioControls } from './components/AudioControls'
import { RouteSettings } from './components/RouteSettings'
import { RoutingMatrix } from './components/RoutingMatrix'
import { SortMenu } from './components/SortMenu'
import { TrackRow } from './components/TrackRow'

type BridgeStatus = 'checking' | 'ready' | 'offline'

const fallbackRoutes: RoutePreset[] = Array.from({ length: 9 }, (_, index) => ({
  routeId: String(index + 1),
  label: `Route ${index + 1}`,
  relativeDestination: 'Needs Review/{bpmBucket}',
  category: null,
  genre: null,
}))

const defaultSort: LibrarySummary['sort'] = { field: 'name', direction: 'asc' }

function App() {
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus>('checking')
  const [root, setRoot] = useState('')
  const [routes, setRoutes] = useState<RoutePreset[]>(fallbackRoutes)
  const [routeSettingsOpen, setRouteSettingsOpen] = useState(false)
  const [summary, setSummary] = useState<LibrarySummary | null>(null)
  const [sort, setSort] = useState<LibrarySummary['sort']>(defaultSort)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<{ completed: number; total: number } | null>(null)
  const [playing, setPlaying] = useState(false)
  const [lastMove, setLastMove] = useState<MoveResult | null>(null)
  const [activeRouteId, setActiveRouteId] = useState<string | null>(null)
  const [blockedRouteId, setBlockedRouteId] = useState<string | null>(null)
  const [draggingTrackId, setDraggingTrackId] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const scanAbortRef = useRef<AbortController | null>(null)

  const selectedTrack: TrackRecord | null = useMemo(
    () => summary?.tracks[selectedIndex] ?? null,
    [selectedIndex, summary],
  )

  useEffect(() => {
    let mounted = true
    ping()
      .then(async () => {
        const config = await getConfig()
        if (!mounted) return
        setBridgeStatus('ready')
        setRoot(config.root)
        setRoutes(config.routes)
      })
      .catch(() => { if (mounted) setBridgeStatus('offline') })
    return () => { mounted = false }
  }, [])

  const refreshLibrary = useCallback(async (rootValue: string, sortValue: LibrarySummary['sort']) => {
    const controller = new AbortController()
    scanAbortRef.current = controller
    setProgress({ completed: 0, total: 0 })
    try {
      const next = await scanLibrary(rootValue.trim() || undefined, sortValue, setProgress, controller.signal)
      setSummary(next)
      setSelectedIndex(next.tracks.length ? 0 : -1)
      setPlaying(false)
      audioRef.current?.pause()
    } finally {
      scanAbortRef.current = null
      setProgress(null)
    }
  }, [])

  async function handleLoadLibrary() {
    setLoading(true)
    setError(null)
    try {
      const nextRoot = root.trim()
      if (nextRoot) await persistRoot(nextRoot)
      await refreshLibrary(nextRoot, sort)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load the local library.')
      setSummary(null)
      setSelectedIndex(-1)
    } finally {
      setLoading(false)
    }
  }

  async function handlePickDirectory() {
    try {
      const selected = await pickDirectory()
      if (selected) setRoot(selected)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not open the native folder picker.')
    }
  }

  function cancelScan() {
    scanAbortRef.current?.abort()
  }

  const handleMove = useCallback(async (routeId: string, trackId = selectedTrack?.trackId) => {
    if (!trackId) return
    setLoading(true)
    setError(null)
    try {
      const result = await moveTrack(trackId, routeId)
      if (result.status !== 'moved') {
        if (result.status === 'destination_exists') setBlockedRouteId(routeId)
        setError(result.error?.message ?? `Move failed: ${result.status}`)
        return
      }
      setBlockedRouteId(null)
      setActiveRouteId(routeId)
      setLastMove(result)
      await refreshLibrary('', sort)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not move the selected track.')
    } finally {
      setLoading(false)
    }
  }, [refreshLibrary, selectedTrack?.trackId, sort])

  async function handleUndo() {
    if (!lastMove) return
    setLoading(true)
    setError(null)
    try {
      const result = await undoLastMove()
      if (result.status !== 'moved') {
        setError(result.error?.message ?? `Undo failed: ${result.status}`)
        return
      }
      setLastMove(null)
      setActiveRouteId(null)
      await refreshLibrary('', sort)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not undo the last move.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSort(field: LibrarySummary['sort']['field'], direction: LibrarySummary['sort']['direction']) {
    const nextSort = { field, direction }
    setSort(nextSort)
    if (!summary || bridgeStatus !== 'ready') return
    setLoading(true)
    setError(null)
    try {
      await refreshLibrary('', nextSort)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not sort the local library.')
    } finally {
      setLoading(false)
    }
  }

  const selectTrack = useCallback((index: number) => {
    setSelectedIndex(index)
    setActiveRouteId(null)
    setBlockedRouteId(null)
    setPlaying(false)
    audioRef.current?.pause()
  }, [])

  function togglePlayback() {
    if (!selectedTrack || !audioRef.current) return
    if (playing) audioRef.current.pause()
    else void audioRef.current.play().catch(() => setError('This track could not be played by the local audio engine.'))
  }

  useEffect(() => {
    function handleKeyboard(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      if (!target || target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      if (!summary?.tracks.length || bridgeStatus !== 'ready') return
      if (event.code === 'KeyW') {
        event.preventDefault()
        selectTrack(Math.max(0, selectedIndex - 1))
      } else if (event.code === 'KeyS') {
        event.preventDefault()
        selectTrack(Math.min(summary.tracks.length - 1, selectedIndex + 1))
      } else if (event.code === 'KeyA' || event.code === 'KeyD') {
        event.preventDefault()
        const audio = audioRef.current
        if (audio) audio.currentTime = Math.max(0, audio.currentTime + (event.code === 'KeyA' ? -5 : 5))
      } else {
        const match = event.code.match(/^Numpad([1-9])$/)
        if (match && !loading) {
          event.preventDefault()
          void handleMove(match[1])
        }
      }
    }
    window.addEventListener('keydown', handleKeyboard)
    return () => window.removeEventListener('keydown', handleKeyboard)
  }, [bridgeStatus, handleMove, loading, selectTrack, selectedIndex, summary])

  return (
    <AppShell bridgeStatus={bridgeStatus}>
      <section className="setup-panel" aria-labelledby="setup-title">
        <div>
          <p className="eyebrow">LOCAL LIBRARY</p>
          <h2 id="setup-title">Choose a music root</h2>
          <p className="body-copy">Python scans and organizes the real filesystem. Audio and metadata stay local.</p>
        </div>
        <div className="root-form">
          <label htmlFor="music-root">Root path</label>
          <div>
            <input id="music-root" value={root} onChange={(event) => setRoot(event.target.value)} placeholder="C:\\Music\\Unsorted" disabled={bridgeStatus !== 'ready'} />
            <button type="button" className="secondary-button" onClick={() => void handlePickDirectory()} disabled={bridgeStatus !== 'ready'}>Browse</button>
            <button className="primary-button" type="button" onClick={() => void handleLoadLibrary()} disabled={bridgeStatus !== 'ready' || loading}>
              {loading ? 'Working…' : 'Load library'}
            </button>
            {progress && <button type="button" className="secondary-button" onClick={cancelScan}>Cancel scan ({progress.completed}/{progress.total || '…'})</button>}
          </div>
        </div>
        {progress && <div className="progress-panel" role="status"><span>Scanning local metadata</span><progress max={progress.total || undefined} value={progress.total ? progress.completed : undefined} /><small>{progress.completed}/{progress.total || '…'} tracks</small></div>}
      </section>

      {error && <p className="error-banner" role="alert">{error}</p>}
      {lastMove && <p className="success-banner" role="status">Moved locally to {lastMove.destinationPath}<button type="button" onClick={() => void handleUndo()} disabled={loading}>Undo</button></p>}

      <section className="workspace-preview" aria-label="Music library workspace">
        <div className="queue-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">UNSORTED QUEUE</p>
              <h2>{summary ? `${summary.totalTracks} tracks in scope` : 'Library waiting for bridge'}</h2>
            </div>
            <div className="queue-toolbar">
              <span className="count-badge">{summary ? `${summary.returnedTracks} shown` : '— tracks'}</span>
              <SortMenu sort={summary?.sort ?? sort} onChange={(field, direction) => void handleSort(field, direction)} />
            </div>
          </div>
          {summary?.tracks.length ? (
            <div className="track-list" aria-label="Loaded local tracks">
              {summary.tracks.map((track, index) => <TrackRow key={track.trackId} track={track} selected={index === selectedIndex} playing={index === selectedIndex && playing} onSelect={() => selectTrack(index)} onTogglePlay={togglePlayback} onDragStart={setDraggingTrackId} onDragEnd={() => setDraggingTrackId(null)} />)}
            </div>
          ) : (
            <div className="empty-state">
              <span className="empty-icon" aria-hidden="true">♪</span>
              <strong>{summary ? 'No audio files found' : 'No library loaded'}</strong>
              <span>{summary ? 'Choose a root containing local audio files.' : 'Load a local root to begin sorting.'}</span>
            </div>
          )}
        </div>

        <aside className="control-panel" aria-label="Keyboard, player and route controls">
          <p className="eyebrow">CONTROL MAP</p>
          <div className="control-row"><kbd>W</kbd><span>Previous song</span></div>
          <div className="control-row"><kbd>S</kbd><span>Next song</span></div>
          <div className="control-row"><kbd>A</kbd><span>Rewind 5 seconds</span></div>
          <div className="control-row"><kbd>D</kbd><span>Fast-forward 5 seconds</span></div>
          <AudioControls track={selectedTrack} audioRef={audioRef} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
          <RoutingMatrix routes={routes} selectedTrackId={selectedTrack?.trackId ?? null} activeRouteId={activeRouteId} recentRouteId={lastMove ? activeRouteId : null} blockedRouteId={blockedRouteId} draggingTrackId={draggingTrackId} disabled={bridgeStatus !== 'ready' || loading} onRoute={(routeId, trackId) => void handleMove(routeId, trackId)} onConfigure={() => setRouteSettingsOpen((open) => !open)} />
          {routeSettingsOpen && <RouteSettings routes={routes} disabled={bridgeStatus !== 'ready' || loading} onRoutesChanged={setRoutes} />}
        </aside>
      </section>
    </AppShell>
  )
}

export default App

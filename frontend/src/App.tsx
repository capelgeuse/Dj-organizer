import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { getConfig, moveTrack, pickDirectory, ping, scanLibrary, setRoot as persistRoot, undoLastMove } from './bridge/desktop-bridge'
import type { LibrarySummary, MoveResult, RoutePreset, TrackRecord } from './bridge/contracts'
import { AppShell } from './components/AppShell'
import { AudioControls } from './components/AudioControls'
import { RouteSettings } from './components/RouteSettings'
import { RoutingMatrix } from './components/RoutingMatrix'
import { SortMenu } from './components/SortMenu'
import { TrackArtwork } from './components/TrackArtwork'
import { TrackRow } from './components/TrackRow'

type BridgeStatus = 'checking' | 'ready' | 'offline'
type InspectorTab = 'info' | 'files' | 'notes'
type MoveIntent = { routeId: string; trackId?: string }

function reportPlaybackFailure(cause: unknown, setError: (message: string) => void) {
  if (cause instanceof DOMException && cause.name === 'AbortError') return
  setError('This track could not be played by the local audio engine.')
}

type PreviewTrackInfo = {
  key: string
  added: string
  album: string
  tags: string[]
  rating: number
  tone: number
}

const fallbackRoutes: RoutePreset[] = Array.from({ length: 9 }, (_, index) => ({
  routeId: String(index + 1),
  label: ['Deck A', 'Deck B', 'Deck C', 'Bass', 'Melody', 'FX', 'Stems', 'Drums', 'Acapella'][index],
  relativeDestination: ['Deck A', 'Deck B', 'Deck C', 'Bass', 'Melody', 'FX', 'Stems', 'Drums', 'Acapella'][index],
  category: ['Deck A', 'Deck B', 'Deck C', 'Bass', 'Melody', 'FX', 'Stems', 'Drums', 'Acapella'][index],
  genre: null,
}))

const defaultSort: LibrarySummary['sort'] = { field: 'name', direction: 'asc' }

const previewSeed: Array<[string, string, string, number, string, number]> = [
  ['Night Drive', 'Kessoncoda', 'Electronic', 124, '8A', 304],
  ['Reverie (Extended Mix)', 'HAAi', 'House', 128, '10B', 367],
  ['Pacific State', '808 State', 'House', 125, '11A', 421],
  ['Keep Moving', 'The Blessed Madonna', 'Disco', 121, '9B', 278],
  ['Orange Evening', 'Floating Points', 'Electronica', 118, '7A', 333],
  ['On My Mind', 'Jorja Smith', 'R&B', 110, '6A', 252],
  ['Losing My Mind', 'DJ Seinfeld', 'Lo-Fi House', 126, '2A', 391],
  ['Black Sands', 'Bonobo', 'Downtempo', 96, '5A', 299],
  ['Atlas', 'Bicep', 'Breaks', 132, '8B', 348],
  ['Dawn Chorus', 'Thom Yorke', 'Ambient', 104, '4A', 286],
  ['Late Night Feelings', 'Róisín Murphy', 'Nu Disco', 115, '3B', 312],
  ['Everything In Its Right Place', 'Radiohead', 'Alternative', 102, '1A', 251],
]

const previewInfo = new Map<string, PreviewTrackInfo>(previewSeed.map(([, , , , key], index) => [
  `preview-${index + 1}`,
  {
    key,
    added: `${String(18 - (index % 12)).padStart(2, '0')} Aug 2026`,
    album: ['Outer Edges', 'Put Your Head Up', 'Ninja Tune Selects', 'Good Life', 'Crush', 'Lost & Found'][index % 6],
    tags: [['warmup', 'vocal'], ['peak', 'new'], ['classic'], ['disco', 'feel good'], ['leftfield'], ['vocal', 'r&b']][index % 6],
    rating: [4, 5, 4, 3, 5, 4][index % 6],
    tone: (index % 6) + 1,
  },
]))

const previewTracks: TrackRecord[] = previewSeed.map(([title, artist, genre, bpm, , duration], index) => ({
  trackId: `preview-${index + 1}`,
  sourcePath: '',
  relativePath: `${String(index + 1).padStart(2, '0')} - ${title}.mp3`,
  name: `${title}.mp3`,
  title,
  artist,
  bpm,
  genre,
  durationSeconds: duration,
  artworkUri: null,
}))

const previewLibrary: LibrarySummary = {
  root: 'LOCAL PREVIEW',
  totalTracks: previewTracks.length,
  returnedTracks: previewTracks.length,
  hasMore: false,
  sort: defaultSort,
  tracks: previewTracks,
}

function displayTitle(track: TrackRecord): string {
  return track.title ?? track.name.replace(/\.[^.]+$/, '')
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—'
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.round(seconds % 60).toString().padStart(2, '0')
  return `${minutes}:${remainder}`
}

function infoFor(track: TrackRecord, index: number): PreviewTrackInfo {
  return previewInfo.get(track.trackId) ?? {
    key: '—',
    added: '—',
    album: track.genre ?? 'Unknown album',
    tags: track.genre ? [track.genre.toLowerCase()] : [],
    rating: 0,
    tone: (index % 6) + 1,
  }
}

function sortedPreviewTracks(tracks: TrackRecord[], sort: LibrarySummary['sort']): TrackRecord[] {
  const valueFor = (track: TrackRecord): string | number => {
    if (sort.field === 'bpm') return track.bpm ?? -1
    if (sort.field === 'duration') return track.durationSeconds ?? -1
    return (track[sort.field] ?? track.name ?? '').toString().toLocaleLowerCase()
  }
  return [...tracks].sort((left, right) => {
    const a = valueFor(left)
    const b = valueFor(right)
    const compared = typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b))
    return sort.direction === 'asc' ? compared : -compared
  })
}

function App() {
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus>('checking')
  const [previewMode, setPreviewMode] = useState(false)
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
  const [recentRouteId, setRecentRouteId] = useState<string | null>(null)
  const [blockedRouteId, setBlockedRouteId] = useState<string | null>(null)
  const [draggingTrackId, setDraggingTrackId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [compactView, setCompactView] = useState(false)
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('info')
  const [rating, setRating] = useState(0)
  const [tags, setTags] = useState<string[]>([])
  const audioRef = useRef<HTMLAudioElement>(null)
  const autoplaySelectionRef = useRef(false)
  const scanAbortRef = useRef<AbortController | null>(null)
  const moveQueueRef = useRef<MoveIntent[]>([])
  const moveQueueRunningRef = useRef(false)
  const summaryRef = useRef<LibrarySummary | null>(null)
  const selectedIndexRef = useRef(-1)

  const selectedTrack: TrackRecord | null = useMemo(
    () => summary?.tracks[selectedIndex] ?? null,
    [selectedIndex, summary],
  )
  const selectedTrackInfo = selectedTrack ? infoFor(selectedTrack, selectedIndex) : null

  const visibleTracks = useMemo(() => {
    if (!summary) return []
    const query = searchQuery.trim().toLocaleLowerCase()
    if (!query) return summary.tracks.map((track, index) => ({ track, index }))
    return summary.tracks
      .map((track, index) => ({ track, index }))
      .filter(({ track }) => [track.title, track.name, track.artist, track.genre].some((value) => value?.toLocaleLowerCase().includes(query)))
  }, [searchQuery, summary])

  useEffect(() => {
    let mounted = true
    ping()
      .then(async () => {
        const config = await getConfig()
        if (!mounted) return
        setBridgeStatus('ready')
        setPreviewMode(false)
        setRoot(config.root)
        setRoutes(config.routes)
        setSummary(null)
        setSelectedIndex(-1)
      })
      .catch(() => {
        if (!mounted) return
        setBridgeStatus('offline')
        setPreviewMode(true)
        setRoot('Local preview · Tauri bridge not detected')
        setSummary(previewLibrary)
        setSelectedIndex(0)
      })
    return () => { mounted = false }
  }, [])

  const refreshLibrary = useCallback(async (rootValue: string, sortValue: LibrarySummary['sort'], preferredIndex = 0, autoplay = false) => {
    const controller = new AbortController()
    scanAbortRef.current = controller
    setProgress({ completed: 0, total: 0 })
    try {
      const next = await scanLibrary(rootValue.trim() || undefined, sortValue, setProgress, controller.signal)
      const nextIndex = next.tracks.length ? Math.min(preferredIndex, next.tracks.length - 1) : -1
      summaryRef.current = next
      selectedIndexRef.current = nextIndex
      setSummary(next)
      autoplaySelectionRef.current = autoplay && nextIndex >= 0
      setSelectedIndex(nextIndex)
      setPlaying(false)
      audioRef.current?.pause()
      return next
    } finally {
      scanAbortRef.current = null
      setProgress(null)
    }
  }, [])

  async function handleLoadLibrary() {
    if (bridgeStatus !== 'ready') return
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
    if (bridgeStatus !== 'ready') return
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

  const drainMoveQueue = useCallback(async () => {
    if (moveQueueRunningRef.current) return
    moveQueueRunningRef.current = true
    try {
      while (moveQueueRef.current.length) {
        const intent = moveQueueRef.current.shift()
        if (!intent) continue
        const currentIndex = selectedIndexRef.current
        const trackId = intent.trackId ?? summaryRef.current?.tracks[currentIndex]?.trackId
        if (!trackId) continue
        setError(null)
        setActiveRouteId(intent.routeId)
        audioRef.current?.pause()
        setPlaying(false)
        try {
          const result = await moveTrack(trackId, intent.routeId)
          if (result.status !== 'moved') {
            if (result.status === 'destination_exists') setBlockedRouteId(intent.routeId)
            setError(result.error?.message ?? `Move failed: ${result.status}`)
            continue
          }
          setBlockedRouteId(null)
          setRecentRouteId(intent.routeId)
          setLastMove(result)
          await refreshLibrary('', sort, Math.max(0, currentIndex), true)
        } catch (cause) {
          setError(cause instanceof Error ? cause.message : 'Could not move the selected track.')
        } finally {
          setActiveRouteId(null)
        }
      }
    } finally {
      moveQueueRunningRef.current = false
    }
  }, [refreshLibrary, sort])

  const handleMove = useCallback((routeId: string, trackId?: string) => {
    if (bridgeStatus !== 'ready') return
    moveQueueRef.current.push({ routeId, ...(trackId ? { trackId } : {}) })
    void drainMoveQueue()
  }, [bridgeStatus, drainMoveQueue])

  async function handleUndo() {
    if (!lastMove || bridgeStatus !== 'ready') return
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
      setRecentRouteId(null)
      await refreshLibrary('', sort)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not undo the last move.')
    } finally {
      setLoading(false)
    }
  }

  function handleSort(field: LibrarySummary['sort']['field'], direction: LibrarySummary['sort']['direction']) {
    const nextSort = { field, direction }
    setSort(nextSort)
    if (!summary) return
    if (bridgeStatus !== 'ready') {
      setSummary((current) => current ? { ...current, sort: nextSort, tracks: sortedPreviewTracks(current.tracks, nextSort) } : current)
      return
    }
    setLoading(true)
    setError(null)
    void refreshLibrary('', nextSort).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : 'Could not sort the local library.')
    }).finally(() => setLoading(false))
  }

  const selectTrack = useCallback((index: number) => {
    selectedIndexRef.current = index
    autoplaySelectionRef.current = true
    setSelectedIndex(index)
    setActiveRouteId(null)
    setBlockedRouteId(null)
    setPlaying(previewMode)
    const nextInfo = summary ? infoFor(summary.tracks[index], index) : null
    setRating(nextInfo?.rating ?? 0)
    setTags(nextInfo?.tags ?? [])
    if (index === selectedIndex && !previewMode) {
      void audioRef.current?.play().catch((cause: unknown) => reportPlaybackFailure(cause, setError))
      autoplaySelectionRef.current = false
    }
  }, [previewMode, selectedIndex, summary])

  useEffect(() => {
    summaryRef.current = summary
    selectedIndexRef.current = selectedIndex
  }, [selectedIndex, summary])

  useEffect(() => {
    if (!autoplaySelectionRef.current || previewMode || !selectedTrack) return
    audioRef.current?.load()
  }, [previewMode, selectedTrack])

  const playPendingSelection = useCallback(() => {
    if (!autoplaySelectionRef.current || !selectedTrack) return
    autoplaySelectionRef.current = false
    if (previewMode) {
      setPlaying(true)
      return
    }
    const audio = audioRef.current
    if (!audio) return
    void audio.play().catch((cause: unknown) => reportPlaybackFailure(cause, setError))
  }, [previewMode, selectedTrack])

  const togglePlayback = useCallback(() => {
    if (!selectedTrack) return
    if (previewMode) {
      setPlaying((current) => !current)
      return
    }
    if (!audioRef.current) return
    if (playing) audioRef.current.pause()
    else void audioRef.current.play().catch((cause: unknown) => reportPlaybackFailure(cause, setError))
  }, [playing, previewMode, selectedTrack])

  useEffect(() => {
    function handleKeyboard(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      if (!target || target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      if (!summary?.tracks.length || bridgeStatus !== 'ready') return
      if (event.code === 'Space') {
        event.preventDefault()
        togglePlayback()
      } else if (event.code === 'KeyW') {
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
        if (event.code === 'Numpad0') {
          event.preventDefault()
          return
        }
        const match = event.code.match(/^Numpad([1-9])$/)
        const route = match ? routes.find((item) => item.routeId === match[1]) : null
        const routeConfigured = route && route.label.trim() && route.relativeDestination.trim()
        if (match && routeConfigured && blockedRouteId !== match[1]) {
          event.preventDefault()
          void handleMove(match[1])
        }
      }
    }
    window.addEventListener('keydown', handleKeyboard)
    return () => window.removeEventListener('keydown', handleKeyboard)
  }, [blockedRouteId, bridgeStatus, handleMove, loading, routes, selectTrack, selectedIndex, summary, togglePlayback])

  return (
    <AppShell bridgeStatus={bridgeStatus} previewMode={previewMode} root={root} onChangeRoot={() => void handlePickDirectory()} onSettings={() => setRouteSettingsOpen((open) => !open)}>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {lastMove && <p className="success-banner" role="status">Moved locally to {lastMove.destinationPath}<button type="button" onClick={() => void handleUndo()} disabled={loading}>Undo</button></p>}

      <section className="workspace" aria-label="Music library workspace">
        <aside className="sidebar" aria-label="Library navigation">
          <div className="sidebar-section">
            <div className="sidebar-heading"><span className="eyebrow">LIBRARY</span><button type="button" className="icon-button" aria-label="Add library">＋</button></div>
            <button type="button" className="sidebar-link sidebar-link-active"><span className="nav-icon">◈</span><span>Unsorted</span><strong>{summary?.totalTracks ?? 0}</strong></button>
            <button type="button" className="sidebar-link"><span className="nav-icon">▤</span><span>All tracks</span><strong>—</strong></button>
            <button type="button" className="sidebar-link"><span className="nav-icon">◷</span><span>Recently added</span><strong>12</strong></button>
          </div>
          <div className="sidebar-section">
            <div className="sidebar-heading"><span className="eyebrow">CRATES</span><button type="button" className="icon-button" aria-label="Add crate">＋</button></div>
            {['Warmup', 'Peak Time', 'House', 'Needs Review'].map((crate, index) => <button type="button" className="sidebar-link" key={crate}><span className={`crate-dot crate-dot-${index + 1}`} /><span>{crate}</span><strong>{[24, 18, 43, 9][index]}</strong></button>)}
          </div>
          <div className="sidebar-section sidebar-tags">
            <div className="sidebar-heading"><span className="eyebrow">TAGS</span><button type="button" className="icon-button" aria-label="Add tag">＋</button></div>
            <div className="tag-list"><button type="button" className="tag-link"><i className="tag-dot tag-dot-red" />Peak</button><button type="button" className="tag-link"><i className="tag-dot tag-dot-blue" />Vocal</button><button type="button" className="tag-link"><i className="tag-dot tag-dot-purple" />Leftfield</button><button type="button" className="tag-link"><i className="tag-dot tag-dot-gold" />New</button></div>
          </div>
          <div className="sidebar-footer"><span className="mini-status" /><span>{previewMode ? 'Preview data only' : 'Offline-first library'}</span><button type="button" className="icon-button" onClick={() => setRouteSettingsOpen((open) => !open)} aria-label="Open settings">⚙</button></div>
        </aside>

        <section className={`queue-panel ${compactView ? 'queue-panel-compact' : ''}`} aria-label="Unsorted queue">
          <header className="queue-header">
            <div>
              <div className="breadcrumb"><span>LIBRARY</span><b>›</b><span>UNSORTED</span></div>
              <div className="queue-title-row"><h1>Unsorted Queue</h1><span className="queue-count">{summary ? summary.totalTracks : '—'} tracks</span></div>
              <p className="queue-subtitle">{previewMode ? 'Local preview collection · bridge actions disabled' : summary ? `${summary.returnedTracks} tracks in current scope` : 'Choose a local root to load your collection'}</p>
            </div>
            <div className="queue-header-actions"><button type="button" className="header-icon-button" aria-label="More queue options">•••</button><button type="button" className="header-icon-button" aria-label="Queue settings" onClick={() => setRouteSettingsOpen((open) => !open)}>⚙</button></div>
          </header>
          <div className="queue-toolbar">
            <div className="toolbar-group"><button type="button" className="toolbar-button toolbar-button-accent" onClick={() => void handleLoadLibrary()} disabled={bridgeStatus !== 'ready' || loading}><span>＋</span> Scan</button><button type="button" className="toolbar-button" onClick={() => void handleLoadLibrary()} disabled={bridgeStatus !== 'ready' || loading}>↻ Rescan</button><button type="button" className="toolbar-button" disabled title="Auto Tags is available in the native desktop bridge">✦ Auto Tags</button>{progress && <button type="button" className="toolbar-button toolbar-cancel-button" onClick={cancelScan}>Cancel {progress.completed}/{progress.total || '…'}</button>}</div>
            <div className="toolbar-group toolbar-group-right"><label className="search-box" htmlFor="track-search"><span aria-hidden="true">⌕</span><input id="track-search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search tracks…" /></label><button type="button" className={`toolbar-button ${showFilters ? 'toolbar-button-active' : ''}`} onClick={() => setShowFilters((visible) => !visible)}>☷ Filters</button><button type="button" className={`toolbar-button ${compactView ? 'toolbar-button-active' : ''}`} onClick={() => setCompactView((compact) => !compact)}>▦ View</button><SortMenu sort={summary?.sort ?? sort} onChange={handleSort} /></div>
          </div>
          {showFilters && <div className="filter-strip"><span>FILTERS</span><button type="button" onClick={() => setSearchQuery('House')}>House</button><button type="button" onClick={() => setSearchQuery('Vocal')}>Vocal</button><button type="button" onClick={() => setSearchQuery('')}>Clear</button></div>}
          <div className="table-head" role="row"><span>#</span><span>TRACK</span><span>ARTIST</span><span>BPM</span><span>KEY</span><span>TIME</span><span>ADDED</span></div>
          {visibleTracks.length ? <div className="track-list" aria-label="Loaded local tracks">{visibleTracks.map(({ track, index }) => { const details = infoFor(track, index); return <TrackRow key={track.trackId} track={track} rowNumber={index + 1} trackKey={details.key} added={details.added} artworkTone={details.tone} selected={index === selectedIndex} playing={index === selectedIndex && playing} compact={compactView} onSelect={() => selectTrack(index)} onTogglePlay={togglePlayback} onDragStart={setDraggingTrackId} onDragEnd={() => setDraggingTrackId(null)} /> })}</div> : <div className="empty-state"><span className="empty-icon" aria-hidden="true">♪</span><strong>{summary ? 'No matching tracks' : 'Your library is ready when you are'}</strong><span>{summary ? 'Try a different search or clear the active filters.' : bridgeStatus === 'ready' ? 'Choose a local music folder to scan your unsorted tracks.' : 'The native bridge is unavailable. A sample collection is shown in Local Preview.'}</span>{!summary && bridgeStatus === 'ready' && <div className="onboarding-card"><label htmlFor="music-root">LOCAL MUSIC FOLDER</label><div><input id="music-root" value={root} onChange={(event) => setRoot(event.target.value)} placeholder="C:\\Music\\Unsorted" /><button type="button" className="secondary-button" onClick={() => void handlePickDirectory()}>Browse</button><button type="button" className="primary-button" onClick={() => void handleLoadLibrary()} disabled={loading}>{loading ? 'Scanning…' : 'Load library'}</button></div></div>}</div>}
          <div className="queue-footer"><span>{summary ? `${visibleTracks.length} of ${summary.totalTracks} tracks` : 'Waiting for a local library'}</span><span>{summary?.hasMore ? 'More tracks available' : summary ? 'All tracks loaded' : 'No files scanned'}</span></div>
        </section>

        <aside className="inspector" aria-label="Track inspector">
          <div className="inspector-tabs" role="tablist" aria-label="Inspector views">{(['info', 'files', 'notes'] as InspectorTab[]).map((tab) => <button type="button" role="tab" aria-selected={inspectorTab === tab} className={inspectorTab === tab ? 'inspector-tab inspector-tab-active' : 'inspector-tab'} onClick={() => setInspectorTab(tab)} key={tab}>{tab === 'info' ? 'Info' : tab === 'files' ? 'Files' : 'Notes'}</button>)}</div>
          {selectedTrack && inspectorTab === 'info' && selectedTrackInfo && <div className="inspector-content">
            <div className={`inspector-cover artwork-tone-${selectedTrackInfo.tone}`}><TrackArtwork track={selectedTrack} playing={playing} artworkTone={selectedTrackInfo.tone} onTogglePlay={togglePlayback} /></div>
            <div className="inspector-track-title"><h2>{displayTitle(selectedTrack)}</h2><p>{selectedTrack.artist ?? 'Artist unknown'}</p><span>{selectedTrackInfo.album}</span></div>
            <div className="metadata-grid"><div><span>BPM</span><strong>{selectedTrack.bpm ?? '—'}</strong></div><div><span>KEY</span><strong>{selectedTrackInfo.key}</strong></div><div><span>TIME</span><strong>{formatDuration(selectedTrack.durationSeconds)}</strong></div><div><span>GENRE</span><strong>{selectedTrack.genre ?? '—'}</strong></div></div>
            <div className="rating-row"><span className="inspector-label">RATING</span><div className="stars" aria-label={`Rating ${rating} out of 5`}>{[1, 2, 3, 4, 5].map((star) => <button type="button" className={star <= rating ? 'star star-on' : 'star'} key={star} onClick={() => setRating(star)} aria-label={`Rate ${star} out of 5`}>★</button>)}</div></div>
            <div className="inspector-tags"><div className="inspector-label-row"><span className="inspector-label">TAGS</span><button type="button" className="text-button" onClick={() => setTags((current) => current.includes('new') ? current : [...current, 'new'])}>＋ Add tag</button></div><div className="inspector-tag-list">{tags.map((tag) => <span className="inspector-tag" key={tag}>{tag}<button type="button" aria-label={`Remove ${tag} tag`} onClick={() => setTags((current) => current.filter((item) => item !== tag))}>×</button></span>)}</div></div>
            <RoutingMatrix routes={routes} selectedTrackId={selectedTrack.trackId} selectedTrackLabel={displayTitle(selectedTrack)} activeRouteId={activeRouteId} recentRouteId={recentRouteId} blockedRouteId={blockedRouteId} draggingTrackId={draggingTrackId} disabled={bridgeStatus !== 'ready'} onRoute={(routeId, trackId) => handleMove(routeId, trackId)} onConfigure={() => setRouteSettingsOpen((open) => !open)} />
            {routeSettingsOpen && <RouteSettings routes={routes} disabled={bridgeStatus !== 'ready' || loading} onRoutesChanged={setRoutes} />}
          </div>}
          {selectedTrack && inspectorTab === 'files' && <div className="inspector-content inspector-file-view"><span className="inspector-label">SOURCE FILE</span><code>{selectedTrack.sourcePath || selectedTrack.relativePath}</code><span className="inspector-label">RELATIVE PATH</span><code>{selectedTrack.relativePath}</code><p>File paths are read from the local bridge and remain authoritative in the native desktop shell.</p></div>}
          {selectedTrack && inspectorTab === 'notes' && <div className="inspector-content inspector-notes"><span className="inspector-label">NOTES</span><textarea placeholder="Add a note about this track…" aria-label="Track notes" /><small>Notes are a local preview-only UI field until persistence is added to the bridge contract.</small></div>}
          {!selectedTrack && <div className="inspector-empty"><span className="empty-icon" aria-hidden="true">◌</span><strong>Select a track</strong><span>Track metadata and routing controls will appear here.</span></div>}
        </aside>
      </section>

      <AudioControls key={selectedTrack?.trackId ?? 'empty-player'} track={selectedTrack} audioRef={audioRef} playing={playing} preview={previewMode} onTogglePlay={togglePlayback} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onReadyToPlay={playPendingSelection} />
    </AppShell>
  )
}

export default App

import type { TrackRecord } from '../bridge/contracts'
import { TrackArtwork } from './TrackArtwork'

type TrackRowProps = {
  track: TrackRecord
  rowNumber: number
  trackKey: string
  added: string
  artworkTone?: number
  compact?: boolean
  selected: boolean
  playing: boolean
  onSelect: () => void
  onTogglePlay: () => void
  onDragStart: (trackId: string) => void
  onDragEnd: () => void
}

export function TrackRow({ track, rowNumber, trackKey, added, artworkTone, compact = false, selected, playing, onSelect, onTogglePlay, onDragStart, onDragEnd }: TrackRowProps) {
  return (
    <article className={`track-row ${selected ? 'track-row-selected' : ''} ${compact ? 'track-row-compact' : ''}`} draggable onClick={onSelect} onDragStart={(event) => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', track.trackId); onDragStart(track.trackId) }} onDragEnd={onDragEnd} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect() } }} role="button" tabIndex={0} aria-pressed={selected}>
      <span className="track-row-number">{String(rowNumber).padStart(2, '0')}</span>
      <span className="track-main-cell"><TrackArtwork track={track} playing={playing} artworkTone={artworkTone} onTogglePlay={onTogglePlay} /><span className="track-copy"><strong>{track.title ?? track.name}</strong><small>{track.genre ?? 'Unknown album'}</small></span></span>
      <span className="track-artist-cell">{track.artist ?? 'Artist unknown'}</span>
      <span className="track-data track-bpm">{track.bpm ?? '—'}</span>
      <span className="track-data track-key">{trackKey}</span>
      <span className="track-data track-duration">{track.durationSeconds === null ? '—' : `${Math.floor(track.durationSeconds / 60)}:${String(Math.round(track.durationSeconds % 60)).padStart(2, '0')}`}</span>
      <span className="track-data track-added">{added}</span>
    </article>
  )
}

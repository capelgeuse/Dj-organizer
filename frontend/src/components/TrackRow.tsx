import type { TrackRecord } from '../bridge/contracts'
import { TrackArtwork } from './TrackArtwork'

type TrackRowProps = {
  track: TrackRecord
  selected: boolean
  playing: boolean
  onSelect: () => void
  onTogglePlay: () => void
  onDragStart: (trackId: string) => void
  onDragEnd: () => void
}

export function TrackRow({ track, selected, playing, onSelect, onTogglePlay, onDragStart, onDragEnd }: TrackRowProps) {
  return (
    <article className={`track-row ${selected ? 'track-row-selected' : ''}`} draggable onClick={onSelect} onDragStart={(event) => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', track.trackId); onDragStart(track.trackId) }} onDragEnd={onDragEnd} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect() } }} role="button" tabIndex={0} aria-pressed={selected}>
      <TrackArtwork track={track} playing={playing} onTogglePlay={onTogglePlay} />
      <span className="track-copy">
        <strong>{track.title ?? track.name}</strong>
        <span>{track.artist ?? 'Artist unknown'}</span>
        <small>{track.bpm ?? 'BPM —'} · {track.genre ?? 'Genre unknown'} · {track.durationSeconds ? `${Math.round(track.durationSeconds)}s` : 'Duration —'}</small>
      </span>
    </article>
  )
}

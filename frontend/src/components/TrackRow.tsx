import type { TrackRecord } from '../bridge/contracts'
import { TrackArtwork } from './TrackArtwork'

type TrackRowProps = {
  track: TrackRecord
  selected: boolean
  playing: boolean
  onSelect: () => void
  onTogglePlay: () => void
}

export function TrackRow({ track, selected, playing, onSelect, onTogglePlay }: TrackRowProps) {
  return (
    <article className={`track-row ${selected ? 'track-row-selected' : ''}`} onClick={onSelect} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect() } }} role="button" tabIndex={0} aria-pressed={selected}>
      <TrackArtwork track={track} playing={playing} onTogglePlay={onTogglePlay} />
      <span className="track-copy">
        <strong>{track.title ?? track.name}</strong>
        <span>{track.artist ?? 'Artist unknown'}</span>
        <small>{track.bpm ?? 'BPM —'} · {track.genre ?? 'Genre unknown'} · {track.durationSeconds ? `${Math.round(track.durationSeconds)}s` : 'Duration —'}</small>
      </span>
    </article>
  )
}

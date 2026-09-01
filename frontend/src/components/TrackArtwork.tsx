import { convertFileSrc, isTauri } from '@tauri-apps/api/core'
import type { TrackRecord } from '../bridge/contracts'

type TrackArtworkProps = {
  track: TrackRecord
  playing: boolean
  onTogglePlay: () => void
  artworkTone?: number
}

function localUri(path: string | null): string | null {
  if (!path || !isTauri()) return null
  return convertFileSrc(path)
}

export function TrackArtwork({ track, playing, onTogglePlay, artworkTone = 1 }: TrackArtworkProps) {
  const artwork = localUri(track.artworkUri)
  return (
    <span className={`track-artwork artwork-tone-${artworkTone}`}>
      {artwork ? <img src={artwork} alt="" /> : <span className="artwork-placeholder" aria-hidden="true"><i /><b>♪</b></span>}
      {playing && <span className="track-play-overlay"><button type="button" onClick={(event) => { event.stopPropagation(); onTogglePlay() }} aria-label={`Pause ${track.title ?? track.name}`}>Ⅱ</button></span>}
    </span>
  )
}

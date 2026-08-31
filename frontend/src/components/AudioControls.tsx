import { convertFileSrc, isTauri } from '@tauri-apps/api/core'
import type { RefObject } from 'react'
import type { TrackRecord } from '../bridge/contracts'

type AudioControlsProps = {
  track: TrackRecord | null
  audioRef: RefObject<HTMLAudioElement | null>
  onPlay: () => void
  onPause: () => void
  onEnded: () => void
}

export function AudioControls({ track, audioRef, onPlay, onPause, onEnded }: AudioControlsProps) {
  const source = track && isTauri() ? convertFileSrc(track.sourcePath) : undefined
  return (
    <section className="audio-controls" aria-label="Audio playback">
      <div className="audio-controls-heading">
        <span className="eyebrow">PLAYER</span>
        <strong>{track ? track.title ?? track.name : 'No track selected'}</strong>
      </div>
      <audio ref={audioRef} key={track?.trackId ?? 'empty'} controls preload="metadata" src={source} onPlay={onPlay} onPause={onPause} onEnded={onEnded} />
      <p>Audio stays local to the desktop shell; binaries never cross JSON IPC.</p>
    </section>
  )
}

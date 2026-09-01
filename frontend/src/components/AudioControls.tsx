import { convertFileSrc, isTauri } from '@tauri-apps/api/core'
import { useState, type RefObject } from 'react'
import type { TrackRecord } from '../bridge/contracts'
import { TrackArtwork } from './TrackArtwork'

type AudioControlsProps = {
  track: TrackRecord | null
  audioRef: RefObject<HTMLAudioElement | null>
  playing: boolean
  preview: boolean
  onTogglePlay: () => void
  onPlay: () => void
  onPause: () => void
  onEnded: () => void
}

function timeLabel(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}

const waveform = [22, 38, 15, 50, 29, 64, 44, 75, 31, 56, 86, 47, 24, 68, 40, 91, 55, 30, 72, 46, 26, 60, 36, 79, 43, 67, 28, 52, 20, 44, 31, 58, 24, 70, 39, 54, 18, 45, 28, 63, 35, 76, 42, 55, 22, 48, 33, 66]

export function AudioControls({ track, audioRef, playing, preview, onTogglePlay, onPlay, onPause, onEnded }: AudioControlsProps) {
  const source = track && isTauri() ? convertFileSrc(track.sourcePath) : undefined
  const duration = track?.durationSeconds ?? 0
  const [position, setPosition] = useState(0)
  const [volume, setVolume] = useState(72)


  function seek(amount: number) {
    const audio = audioRef.current
    if (audio) audio.currentTime = Math.max(0, Math.min(audio.duration || duration, audio.currentTime + amount))
    setPosition((current) => Math.max(0, Math.min(duration, current + amount)))
  }

  return (
    <footer className="audio-controls" aria-label="Audio playback">
      <audio ref={audioRef} className="audio-engine" key={track?.trackId ?? 'empty'} preload="metadata" src={source} onTimeUpdate={(event) => setPosition(event.currentTarget.currentTime)} onPlay={onPlay} onPause={onPause} onEnded={onEnded} />
      <div className="player-transport"><button type="button" className="player-transport-button" onClick={() => seek(-5)} disabled={!track} aria-label="Previous cue">|‹</button><button type="button" className="player-transport-button" onClick={() => seek(-5)} disabled={!track} aria-label="Rewind five seconds">‹</button><button type="button" className="player-play-button" onClick={onTogglePlay} disabled={!track} aria-label={playing ? 'Pause track' : 'Play track'}>{playing ? 'Ⅱ' : '▶'}</button><button type="button" className="player-transport-button" onClick={() => seek(5)} disabled={!track} aria-label="Fast forward five seconds">›</button><button type="button" className="player-transport-button" onClick={() => seek(5)} disabled={!track} aria-label="Next cue">›|</button></div>
      <div className="player-track"><div className="player-artwork">{track ? <TrackArtwork track={track} playing={false} artworkTone={1} onTogglePlay={onTogglePlay} /> : <span>♪</span>}</div><div className="player-track-copy"><strong>{track ? track.title ?? track.name : 'Nothing selected'}</strong><span>{track?.artist ?? (preview ? 'Local preview collection' : 'Select a track to begin')}</span></div></div>
      <div className="player-waveform" aria-label="Waveform preview">{waveform.map((height, index) => <i key={index} style={{ height: `${height}%` }} className={index / waveform.length < (duration ? position / duration : 0) ? 'waveform-past' : ''} />)}</div>
      <span className="player-time">{timeLabel(position)} <b>/</b> {timeLabel(duration)}</span>
      <div className="player-volume"><span aria-hidden="true">⌁</span><input aria-label="Volume" type="range" min="0" max="100" value={volume} onChange={(event) => setVolume(Number(event.target.value))} /></div>
      <button type="button" className="player-cue" disabled={!track}>CUE</button><button type="button" className="player-add" disabled={!track}>＋ TAG</button>
    </footer>
  )
}

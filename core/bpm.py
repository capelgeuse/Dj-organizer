"""Optional local BPM analysis fallback."""
from __future__ import annotations

from pathlib import Path

try:
    import librosa
except ImportError:
    librosa = None


def analyse_bpm(path: Path) -> float | None:
    if librosa is None:
        return None
    try:
        if path.stat().st_size < 128:
            return None
        audio, sample_rate = librosa.load(str(path), sr=None, mono=True, duration=90)
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sample_rate)
        value = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)
        return round(value, 2) if value > 0 else None
    except Exception:
        return None

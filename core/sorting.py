"""Deterministic sorting and BPM fallback helpers."""
from __future__ import annotations

from architecture.contracts import SortDirection, SortField, TrackRecord


def bpm_bucket(bpm: float | None) -> str:
    if bpm is None or bpm <= 0:
        return "BPM UNKNOWN"
    start = int(bpm // 4) * 4
    return f"{start}-{start + 3} BPM"


def sort_tracks(tracks: list[TrackRecord], field: SortField, direction: SortDirection) -> list[TrackRecord]:
    def value_key(track: TrackRecord) -> tuple[bool, object, str]:
        value: object | None = {
            SortField.NAME: track.name,
            SortField.TITLE: track.title,
            SortField.ARTIST: track.artist,
            SortField.BPM: track.bpm,
            SortField.GENRE: track.genre,
            SortField.DURATION: track.duration_seconds,
        }[field]
        return value is None, value.casefold() if isinstance(value, str) else (value if value is not None else 0), track.relative_path.casefold()

    known = [track for track in tracks if value_key(track)[0] is False]
    unknown = [track for track in tracks if value_key(track)[0] is True]
    known.sort(key=value_key, reverse=direction is SortDirection.DESCENDING)
    unknown.sort(key=lambda track: track.relative_path.casefold())
    return known + unknown

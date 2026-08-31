"""Filesystem scope and deterministic intake scanning."""
from __future__ import annotations

import hashlib
from threading import Event
from pathlib import Path
from typing import Callable, Iterable

from architecture.contracts import TrackRecord
from core.metadata import read_metadata

AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"})


class ScanCancelled(Exception):
    """Raised when a scan is cancelled before its next track is read."""


def track_id_for(relative_path: Path) -> str:
    digest = hashlib.sha1(relative_path.as_posix().casefold().encode("utf-8")).hexdigest()
    return f"track-{digest[:16]}"


def _normalise_prefix(value: str) -> tuple[str, ...]:
    parts = [part.strip() for part in value.replace("\\", "/").split("/") if part.strip()]
    return tuple(part for part in parts if not part.startswith("{"))


class LibraryScope:
    def __init__(self, root: Path, excluded_prefixes: Iterable[str] = ()):
        self.root = root.expanduser().resolve()
        self.excluded_prefixes = tuple(_normalise_prefix(prefix) for prefix in excluded_prefixes)

    def ensure_valid(self) -> None:
        if not self.root.is_dir():
            raise NotADirectoryError(str(self.root))

    def _is_excluded(self, relative_path: Path) -> bool:
        parts = tuple(relative_path.parts[:-1])
        if not parts:
            return False
        if parts[0].casefold() == "unsorted":
            return any(parts[: len(prefix)] == prefix for prefix in self.excluded_prefixes if prefix)
        return True

    def paths(self) -> list[Path]:
        self.ensure_valid()
        candidates: list[Path] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.casefold() not in AUDIO_EXTENSIONS:
                continue
            relative = path.relative_to(self.root)
            if not self._is_excluded(relative):
                candidates.append(path)
        return candidates

    def tracks(self, progress: Callable[[int, int], None] | None = None, cancel: Event | None = None) -> list[TrackRecord]:
        records: list[TrackRecord] = []
        paths = self.paths()
        total = len(paths)
        for index, path in enumerate(paths, start=1):
            if cancel is not None and cancel.is_set():
                raise ScanCancelled()
            relative = path.relative_to(self.root)
            metadata = read_metadata(path)
            records.append(TrackRecord(
                track_id=track_id_for(relative),
                source_path=str(path),
                relative_path=relative.as_posix(),
                name=path.name,
                title=metadata["title"],
                artist=metadata["artist"],
                bpm=metadata["bpm"],
                genre=metadata["genre"],
                duration_seconds=metadata["durationSeconds"],
                artwork_uri=metadata["artworkUri"],
            ))
            if progress is not None:
                progress(index, total)
        return records

    def find(self, track_id: str) -> TrackRecord | None:
        return next((track for track in self.tracks() if track.track_id == track_id), None)

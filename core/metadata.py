"""Small, dependency-optional metadata adapter."""
from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

try:
    from mutagen import File as open_metadata
except ImportError:
    open_metadata = None


class Metadata(TypedDict):
    title: str | None
    artist: str | None
    bpm: float | None
    genre: str | None
    durationSeconds: float | None
    artworkUri: str | None
    metadataError: str | None


def _value(tags: Any, names: tuple[str, ...]) -> str | None:
    if not tags:
        return None
    for name in names:
        value = tags.get(name)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _bpm(tags: Any) -> float | None:
    value = _value(tags, ("bpm", "TBPM", "tbpm", "tempo"))
    if value is None:
        return None
    try:
        return round(float(value.replace(",", ".")), 2)
    except ValueError:
        return None


def _artwork_path(path: Path) -> str | None:
    for stem in ("cover", "folder", "front", path.stem):
        for extension in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = path.parent / f"{stem}{extension}"
            if candidate.is_file():
                return str(candidate)
    return None


def read_metadata(path: Path) -> Metadata:
    result: Metadata = {
        "title": None,
        "artist": None,
        "bpm": None,
        "genre": None,
        "durationSeconds": None,
        "artworkUri": _artwork_path(path),
        "metadataError": None,
    }
    if open_metadata is None:
        result["metadataError"] = "METADATA_DEPENDENCY_UNAVAILABLE"
        return result
    try:
        audio = open_metadata(str(path), easy=True)
        raw = open_metadata(str(path))
        tags = getattr(audio, "tags", None) if audio else None
        raw_tags = getattr(raw, "tags", None) if raw else tags
        info = getattr(raw, "info", None) if raw else None
        result["title"] = _value(tags or raw_tags, ("title", "TIT2"))
        result["artist"] = _value(tags or raw_tags, ("artist", "TPE1", "albumartist", "TPE2"))
        result["genre"] = _value(tags or raw_tags, ("genre", "TCON"))
        result["bpm"] = _bpm(tags or raw_tags)
        duration = getattr(info, "length", None)
        result["durationSeconds"] = round(float(duration), 3) if duration else None
    except (OSError, TypeError, ValueError) as error:
        result["metadataError"] = type(error).__name__
    return result

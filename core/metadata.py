"""Small, dependency-optional metadata adapter."""
from __future__ import annotations

import hashlib
import os
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


def _cache_embedded_artwork(path: Path, raw: Any) -> str | None:
    pictures = list(getattr(raw, "pictures", []) or [])
    if not pictures:
        return None
    picture = pictures[0]
    data = getattr(picture, "data", None)
    if not isinstance(data, (bytes, bytearray)) or not data:
        return None
    mime = str(getattr(picture, "mime", "image/jpeg"))
    extension = {"image/png": ".png", "image/webp": ".webp"}.get(mime, ".jpg")
    digest = hashlib.sha256(str(path).encode("utf-8") + bytes(data)).hexdigest()
    configured_cache = os.environ.get("CAPELHOUSE_ARTWORK_DIR")
    cache_root = Path(configured_cache) if configured_cache else Path.home() / ".capelhouse" / "artwork"
    target = cache_root / f"{digest}{extension}"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file():
            target.write_bytes(bytes(data))
        return str(target)
    except OSError:
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
        if result["artworkUri"] is None:
            result["artworkUri"] = _cache_embedded_artwork(path, raw)
    except Exception as error:
        result["metadataError"] = type(error).__name__
    return result

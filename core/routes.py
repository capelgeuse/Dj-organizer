"""Route validation and destination resolution."""
from __future__ import annotations

import re
from pathlib import Path

from architecture.contracts import RoutePreset, TrackRecord
from core.sorting import bpm_bucket

_INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*]')


def _safe_component(value: str, fallback: str) -> str:
    value = value.strip() or fallback
    if value in {".", ".."} or _INVALID_WINDOWS_CHARS.search(value):
        raise ValueError(f"INVALID_ROUTE_COMPONENT:{value}")
    return value


def resolve_destination(route: RoutePreset, track: TrackRecord) -> Path:
    genre = _safe_component(route.genre or track.genre or "Unknown", "Unknown")
    category = _safe_component(route.category or "Needs Review", "Needs Review")
    values = {
        "genre": genre,
        "category": category,
        "bpmBucket": bpm_bucket(track.bpm),
        "bpm": str(int(track.bpm)) if track.bpm is not None else "UNKNOWN",
    }
    relative = route.relative_destination.format(**values)
    destination = Path(relative)
    if destination.is_absolute() or any(part in {"", ".", ".."} for part in destination.parts):
        raise ValueError("INVALID_ROUTE")
    return destination


def destination_prefixes(routes: list[RoutePreset]) -> list[str]:
    prefixes: list[str] = []
    for route in routes:
        parts = route.relative_destination.replace("\\", "/").split("/")
        static_parts: list[str] = []
        for part in parts:
            if part.startswith("{"):
                break
            static_parts.append(part)
        if static_parts:
            prefixes.append("/".join(static_parts))
    return prefixes

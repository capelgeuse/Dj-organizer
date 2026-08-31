"""Layer A transport contracts for CapelHouse.

The contracts are immutable carriers. They intentionally contain no service
lookups, filesystem operations, audio decoding, UI state, or persistence code.
"""
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping


class Command(StrEnum):
    PING = "ping"
    SHUTDOWN = "shutdown"
    SET_ROOT = "set_root"
    LOAD_LIBRARY = "load_library"
    GET_TRACK_PAGE = "get_track_page"
    MOVE_TRACK = "move_track"
    UNDO_LAST_MOVE = "undo_last_move"
    GET_CONFIG = "get_config"
    SET_ROUTES = "set_routes"


class SortField(StrEnum):
    NAME = "name"
    TITLE = "title"
    ARTIST = "artist"
    BPM = "bpm"
    GENRE = "genre"
    DURATION = "duration"


class SortDirection(StrEnum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class MoveStatus(StrEnum):
    MOVED = "moved"
    DESTINATION_EXISTS = "destination_exists"
    INVALID_ROUTE = "invalid_route"
    SOURCE_MISSING = "source_missing"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class BridgeRequest:
    request_id: str
    command: str
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.request_id,
            "command": self.command,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class TrackRecord:
    track_id: str
    source_path: str
    relative_path: str
    name: str
    title: str | None
    artist: str | None
    bpm: float | None
    genre: str | None
    duration_seconds: float | None
    artwork_uri: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trackId": self.track_id,
            "sourcePath": self.source_path,
            "relativePath": self.relative_path,
            "name": self.name,
            "title": self.title,
            "artist": self.artist,
            "bpm": self.bpm,
            "genre": self.genre,
            "durationSeconds": self.duration_seconds,
            "artworkUri": self.artwork_uri,
        }


@dataclass(frozen=True)
class LibrarySummary:
    root: str
    total_tracks: int
    returned_tracks: int
    has_more: bool
    sort_field: SortField
    sort_direction: SortDirection
    tracks: tuple[TrackRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "totalTracks": self.total_tracks,
            "returnedTracks": self.returned_tracks,
            "hasMore": self.has_more,
            "sort": {
                "field": self.sort_field.value,
                "direction": self.sort_direction.value,
            },
            "tracks": [track.to_dict() for track in self.tracks],
        }


@dataclass(frozen=True)
class RoutePreset:
    route_id: str
    label: str
    relative_destination: str
    category: str | None = None
    genre: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "routeId": self.route_id,
            "label": self.label,
            "relativeDestination": self.relative_destination,
            "category": self.category,
            "genre": self.genre,
        }


@dataclass(frozen=True)
class MoveResult:
    status: MoveStatus
    track_id: str
    source_path: str
    destination_path: str | None
    operation_id: str | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "trackId": self.track_id,
            "sourcePath": self.source_path,
            "destinationPath": self.destination_path,
            "operationId": self.operation_id,
            "error": self.error,
        }


@dataclass(frozen=True)
class ProgressEvent:
    request_id: str
    phase: str
    completed: int
    total: int | None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.request_id,
            "type": "progress",
            "phase": self.phase,
            "completed": self.completed,
            "total": self.total,
            "message": self.message,
        }


@dataclass(frozen=True)
class BridgeResponse:
    request_id: str
    ok: bool
    data: Mapping[str, Any] | None = None
    error: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.request_id,
            "ok": self.ok,
            "data": dict(self.data) if self.data is not None else None,
            "error": dict(self.error) if self.error is not None else None,
        }

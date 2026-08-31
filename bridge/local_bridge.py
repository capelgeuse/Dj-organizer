"""Tauri-owned JSON-lines bridge for CapelHouse."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from architecture.contracts import (
    BridgeResponse,
    LibrarySummary,
    SortDirection,
    SortField,
)
from architecture.errors import BridgeError, ErrorCode
from core.classifier import Classifier
from core.config import ConfigStore
from core.library_scope import LibraryScope
from core.routes import destination_prefixes
from core.sorting import sort_tracks


class BackendApplication:
    def __init__(self, config: ConfigStore | None = None):
        self.config = config or ConfigStore()
        self.classifier = Classifier(self.config)

    def _scope(self, root_value: str | None = None) -> LibraryScope:
        document = self.config.read()
        root = Path(root_value or str(document.get("root", "")).strip()).expanduser()
        if not str(root).strip() or not root.is_dir():
            raise BridgeException(BridgeError(ErrorCode.INVALID_ROOT, "Choose an existing music root."))
        return LibraryScope(root, destination_prefixes(self.config.routes()))

    @staticmethod
    def _sort(payload: dict[str, Any], config: dict[str, Any]) -> tuple[SortField, SortDirection]:
        raw_sort = config.get("sort")
        configured: dict[str, Any] = raw_sort if isinstance(raw_sort, dict) else {}
        field_value = payload.get("sortField", configured.get("field", SortField.NAME.value))
        direction_value = payload.get("sortDirection", configured.get("direction", SortDirection.ASCENDING.value))
        try:
            return SortField(str(field_value)), SortDirection(str(direction_value))
        except ValueError as error:
            raise BridgeException(BridgeError(ErrorCode.INVALID_REQUEST, "Unsupported sort field or direction.")) from error

    def load_library(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = self.config.read()
        scope = self._scope(str(payload.get("root", "")).strip() or None)
        field, direction = self._sort(payload, config)
        tracks = sort_tracks(scope.tracks(), field, direction)
        try:
            offset = max(0, int(payload.get("offset", 0)))
            limit = min(500, max(1, int(payload.get("limit", 200))))
        except (TypeError, ValueError) as error:
            raise BridgeException(BridgeError(ErrorCode.INVALID_REQUEST, "offset and limit must be integers.")) from error
        page = tuple(tracks[offset : offset + limit])
        summary = LibrarySummary(scope.root.as_posix(), len(tracks), len(page), offset + len(page) < len(tracks), field, direction, page)
        return summary.to_dict()

    def get_config(self) -> dict[str, Any]:
        document = self.config.read()
        document["configPath"] = str(self.config.path)
        return document

    def set_root(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = Path(str(payload.get("root", "")).strip()).expanduser()
        if not root.is_dir():
            raise BridgeException(BridgeError(ErrorCode.INVALID_ROOT, "Choose an existing music root."))
        return {"root": str(root.resolve()), "configPath": str(self.config.path)} | self.config.set_root(str(root.resolve()))

    def set_routes(self, payload: dict[str, Any]) -> dict[str, Any]:
        routes = payload.get("routes")
        if not isinstance(routes, list) or len(routes) != 9:
            raise BridgeException(BridgeError(ErrorCode.INVALID_REQUEST, "Exactly nine route presets are required."))
        ids = [str(item.get("routeId", "")) for item in routes if isinstance(item, dict)]
        if len(ids) != 9 or set(ids) != {str(index) for index in range(1, 10)}:
            raise BridgeException(BridgeError(ErrorCode.INVALID_ROUTE, "Route IDs must be exactly 1 through 9."))
        document = self.config.set_routes(routes)
        return {"routes": document["routes"]}

    def set_route_path(self, payload: dict[str, Any]) -> dict[str, Any]:
        route_id = str(payload.get("routeId", ""))
        path = str(payload.get("path", "")).strip()
        label = str(payload.get("label", "")).strip() or None
        try:
            document = self.config.set_route_path(route_id, path, label)
        except ValueError as error:
            code = ErrorCode.DESTINATION_OUTSIDE_ROOT if str(error) == "DESTINATION_OUTSIDE_ROOT" else ErrorCode.INVALID_ROUTE
            raise BridgeException(BridgeError(code, "Route folder must be inside the selected root.")) from error
        return {"routes": document["routes"]}

    def handle(self, command: str, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        if command == "ping":
            return {"ready": True, "protocolVersion": 1}, False
        if command == "shutdown":
            return {"shuttingDown": True}, True
        if command in {"load_library", "get_track_page"}:
            return self.load_library(payload), False
        if command == "get_config":
            return self.get_config(), False
        if command == "set_root":
            return self.set_root(payload), False
        if command == "set_routes":
            return self.set_routes(payload), False
        if command == "set_route_path":
            return self.set_route_path(payload), False
        if command == "move_track":
            result = self.classifier.move(str(payload.get("trackId", "")), str(payload.get("routeId", "")))
            return result.to_dict(), False
        if command == "undo_last_move":
            return self.classifier.undo().to_dict(), False
        raise BridgeException(BridgeError(ErrorCode.UNKNOWN_COMMAND, f"Unsupported command: {command or 'empty'}"))


class BridgeException(Exception):
    def __init__(self, error: BridgeError):
        super().__init__(error.message)
        self.error = error


def _payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise BridgeException(BridgeError(ErrorCode.INVALID_REQUEST, "Request payload must be an object."))
    return value


def serve(input_stream: TextIO, output_stream: TextIO, application: BackendApplication | None = None) -> None:
    app = application or BackendApplication()
    for line in input_stream:
        request_id = ""
        should_shutdown = False
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise BridgeException(BridgeError(ErrorCode.INVALID_REQUEST, "Request must be a JSON object."))
            request_id = str(request.get("id", ""))
            command = str(request.get("command", ""))
            data, should_shutdown = app.handle(command, _payload(request.get("payload", {})))
            response = BridgeResponse(request_id, True, data=data)
        except BridgeException as error:
            response = BridgeResponse(request_id, False, error=error.error.to_dict())
        except json.JSONDecodeError:
            response = BridgeResponse(request_id, False, error=BridgeError(ErrorCode.BRIDGE_PROTOCOL_ERROR, "Malformed JSON request.").to_dict())
        except Exception as error:  # Last-resort protocol boundary; details stay structured.
            response = BridgeResponse(request_id, False, error=BridgeError(ErrorCode.INTERNAL_ERROR, str(error), retryable=True).to_dict())
        output_stream.write(json.dumps(response.to_dict(), ensure_ascii=False) + "\n")
        output_stream.flush()
        if should_shutdown:
            break


def main() -> None:
    serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()

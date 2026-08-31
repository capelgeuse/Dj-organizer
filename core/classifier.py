"""Fail-closed filesystem move authority."""
from __future__ import annotations

import errno
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from architecture.contracts import MoveResult, MoveStatus, RoutePreset
from architecture.errors import BridgeError, ErrorCode
from core.config import ConfigStore
from core.library_scope import LibraryScope
from core.routes import destination_prefixes, resolve_destination


@dataclass(frozen=True)
class OperationReceipt:
    operation_id: str
    track_id: str
    source_path: Path
    destination_path: Path


class Classifier:
    def __init__(self, config: ConfigStore):
        self.config = config
        self.last_operation: OperationReceipt | None = None

    def _scope(self) -> LibraryScope:
        document = self.config.read()
        root = Path(str(document.get("root", "")).strip())
        return LibraryScope(root, destination_prefixes(self.config.routes()))

    @staticmethod
    def _error_result(track_id: str, source: Path, status: MoveStatus, error: BridgeError) -> MoveResult:
        return MoveResult(status, track_id, str(source), None, error=error.to_dict())

    def move(self, track_id: str, route_id: str) -> MoveResult:
        scope = self._scope()
        source_record = scope.find(track_id)
        source = Path(source_record.source_path) if source_record else scope.root / "missing"
        if source_record is None:
            return self._error_result(track_id, source, MoveStatus.SOURCE_MISSING, BridgeError(ErrorCode.TRACK_NOT_FOUND, "Track is no longer in the intake queue."))
        route = next((item for item in self.config.routes() if item.route_id == route_id), None)
        if route is None:
            return self._error_result(track_id, source, MoveStatus.INVALID_ROUTE, BridgeError(ErrorCode.INVALID_ROUTE, "Route is not configured."))
        try:
            relative_destination = resolve_destination(route, source_record)
            destination = (scope.root / relative_destination / source.name).resolve()
            root = scope.root
            if root not in destination.parents:
                return self._error_result(track_id, source, MoveStatus.INVALID_ROUTE, BridgeError(ErrorCode.DESTINATION_OUTSIDE_ROOT, "Destination must remain inside the selected root."))
            if root not in source.resolve().parents and source.resolve() != root:
                return self._error_result(track_id, source, MoveStatus.INVALID_ROUTE, BridgeError(ErrorCode.SOURCE_OUTSIDE_ROOT, "Source is outside the selected root."))
            if destination.exists():
                return self._error_result(track_id, source, MoveStatus.DESTINATION_EXISTS, BridgeError(ErrorCode.DESTINATION_EXISTS, "Destination already exists."))
            if source.anchor.casefold() != destination.anchor.casefold():
                return self._error_result(track_id, source, MoveStatus.FAILED, BridgeError(ErrorCode.CROSS_VOLUME_MOVE_UNSUPPORTED, "Cross-volume moves are not supported."))
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
        except PermissionError as error:
            return self._error_result(track_id, source, MoveStatus.FAILED, BridgeError(ErrorCode.PERMISSION_DENIED, str(error), retryable=True))
        except OSError as error:
            code = ErrorCode.CROSS_VOLUME_MOVE_UNSUPPORTED if error.errno == errno.EXDEV else ErrorCode.INTERNAL_ERROR
            return self._error_result(track_id, source, MoveStatus.FAILED, BridgeError(code, str(error), retryable=code is ErrorCode.INTERNAL_ERROR))
        receipt = OperationReceipt(f"op-{os.urandom(8).hex()}", track_id, source, destination)
        self.last_operation = receipt
        return MoveResult(MoveStatus.MOVED, track_id, str(source), str(destination), receipt.operation_id)

    def undo(self) -> MoveResult:
        receipt = self.last_operation
        if receipt is None:
            return MoveResult(MoveStatus.FAILED, "", "", None, error=BridgeError(ErrorCode.TRACK_NOT_FOUND, "There is no move to undo.").to_dict())
        if not receipt.destination_path.is_file() or receipt.source_path.exists():
            return MoveResult(MoveStatus.FAILED, receipt.track_id, str(receipt.source_path), str(receipt.destination_path), receipt.operation_id, BridgeError(ErrorCode.DESTINATION_EXISTS, "Undo cannot safely restore the original path.").to_dict())
        try:
            receipt.source_path.parent.mkdir(parents=True, exist_ok=True)
            receipt.destination_path.rename(receipt.source_path)
        except OSError as error:
            return MoveResult(MoveStatus.FAILED, receipt.track_id, str(receipt.source_path), str(receipt.destination_path), receipt.operation_id, BridgeError(ErrorCode.INTERNAL_ERROR, str(error), retryable=True).to_dict())
        result = MoveResult(MoveStatus.MOVED, receipt.track_id, str(receipt.destination_path), str(receipt.source_path), receipt.operation_id)
        self.last_operation = None
        return result

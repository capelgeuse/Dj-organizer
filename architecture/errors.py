"""Stable error vocabulary for the local desktop bridge.

This module contains data and vocabulary only. It does not touch the
filesystem, the audio stack, the UI, or the Python process lifecycle.
"""
from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
    BRIDGE_NOT_READY = "BRIDGE_NOT_READY"
    BRIDGE_PROTOCOL_ERROR = "BRIDGE_PROTOCOL_ERROR"
    BRIDGE_UNAVAILABLE = "BRIDGE_UNAVAILABLE"
    INVALID_ROOT = "INVALID_ROOT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TRACK_NOT_FOUND = "TRACK_NOT_FOUND"
    INVALID_ROUTE = "INVALID_ROUTE"
    DESTINATION_EXISTS = "DESTINATION_EXISTS"
    DESTINATION_OUTSIDE_ROOT = "DESTINATION_OUTSIDE_ROOT"
    SOURCE_OUTSIDE_ROOT = "SOURCE_OUTSIDE_ROOT"
    CROSS_VOLUME_MOVE_UNSUPPORTED = "CROSS_VOLUME_MOVE_UNSUPPORTED"
    METADATA_UNAVAILABLE = "METADATA_UNAVAILABLE"
    BPM_UNAVAILABLE = "BPM_UNAVAILABLE"
    OPERATION_CANCELLED = "OPERATION_CANCELLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class BridgeError:
    code: ErrorCode
    message: str
    retryable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
        }

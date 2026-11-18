"""Layer A contract tests; no GUI, filesystem, or audio dependencies."""
import unittest

from architecture.contracts import (
    BridgeRequest,
    BridgeResponse,
    LibrarySummary,
    MoveResult,
    MoveStatus,
    ProgressEvent,
    RoutePreset,
    SortDirection,
    SortField,
    TrackRecord,
)
from architecture.errors import BridgeError, ErrorCode


class ArchitectureContractTests(unittest.TestCase):
    def test_request_and_response_are_json_ready(self):
        request = BridgeRequest("req-1", "load_library", {"root": "C:/Music"})
        response = BridgeResponse("req-1", True, {"ready": True})

        self.assertEqual(request.to_dict(), {
            "id": "req-1",
            "command": "load_library",
            "payload": {"root": "C:/Music"},
        })
        self.assertEqual(response.to_dict()["id"], "req-1")
        self.assertTrue(response.to_dict()["ok"])

    def test_track_summary_and_route_keep_small_structured_payloads(self):
        track = TrackRecord(
            track_id="track-1",
            source_path="C:/Music/song.flac",
            relative_path="song.flac",
            name="song.flac",
            title="Song",
            artist="Artist",
            bpm=124.0,
            genre="House",
            duration_seconds=240.0,
        )
        summary = LibrarySummary(
            root="C:/Music",
            total_tracks=1,
            returned_tracks=1,
            has_more=False,
            sort_field=SortField.BPM,
            sort_direction=SortDirection.ASCENDING,
            tracks=(track,),
        )
        route = RoutePreset("route-1", "House / Inicio", "House/Inicio")

        self.assertEqual(summary.to_dict()["sort"], {"field": "bpm", "direction": "asc"})
        self.assertEqual(summary.to_dict()["tracks"][0]["trackId"], "track-1")
        self.assertEqual(route.to_dict()["routeId"], "route-1")

    def test_move_and_progress_contracts_preserve_terminal_state(self):
        result = MoveResult(
            status=MoveStatus.MOVED,
            track_id="track-1",
            source_path="C:/Music/song.flac",
            destination_path="C:/Music/House/song.flac",
            operation_id="op-1",
        )
        progress = ProgressEvent("req-2", "scan", 1, 10, "Reading metadata")

        self.assertEqual(result.to_dict()["status"], "moved")
        self.assertEqual(progress.to_dict()["type"], "progress")
        self.assertEqual(progress.to_dict()["completed"], 1)

    def test_error_codes_are_stable_and_serializable(self):
        error = BridgeError(ErrorCode.DESTINATION_EXISTS, "Destination already exists.")

        self.assertEqual(error.to_dict(), {
            "code": "DESTINATION_EXISTS",
            "message": "Destination already exists.",
            "retryable": False,
        })
        self.assertEqual(ErrorCode.BRIDGE_UNAVAILABLE.value, "BRIDGE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()

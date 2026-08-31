"""Tests for the headless bridge and fail-closed move authority."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from architecture.contracts import RoutePreset
from architecture.contracts import SortDirection, SortField, TrackRecord
from core.classifier import Classifier
from core.config import ConfigStore
from core.library_scope import LibraryScope, track_id_for
from core.config import default_routes
from core.routes import destination_prefixes
from core.sorting import sort_tracks


class BridgeTests(unittest.TestCase):
    def test_scan_job_reports_progress_and_completion(self):
        from bridge.local_bridge import BackendApplication

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.mp3").write_bytes(b"one")
            (root / "two.mp3").write_bytes(b"two")
            config = ConfigStore(root / "config.json")
            app = BackendApplication(config)
            config.set_root(str(root))
            started = app.start_library_scan({})
            state = app.poll_job({"jobId": started["jobId"]})
            deadline = time.monotonic() + 2
            while state["state"] == "running" and time.monotonic() < deadline:
                time.sleep(0.01)
                state = app.poll_job({"jobId": started["jobId"]})

            self.assertEqual(state["state"], "complete")
            self.assertEqual(state["progress"]["completed"], 2)
            self.assertEqual(state["data"]["totalTracks"], 2)
            app.close()

    def test_protocol_query_then_move_returns_refreshable_state(self):
        from bridge.local_bridge import BackendApplication, serve
        from io import StringIO

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "track.mp3"
            source.write_bytes(b"fixture")
            config = ConfigStore(root / "config.json")
            app = BackendApplication(config)
            lines = "\n".join([
                json.dumps({"id": "root", "command": "set_root", "payload": {"root": str(root)}}),
                json.dumps({"id": "load", "command": "load_library", "payload": {}}),
                json.dumps({"id": "move", "command": "move_track", "payload": {"trackId": track_id_for(Path("track.mp3")), "routeId": "9"}}),
                json.dumps({"id": "reload", "command": "load_library", "payload": {}}),
                json.dumps({"id": "stop", "command": "shutdown", "payload": {}}),
            ]) + "\n"
            output = StringIO()
            serve(StringIO(lines), output, app)
            responses = [json.loads(line) for line in output.getvalue().splitlines()]

            self.assertTrue(responses[0]["ok"])
            self.assertEqual(responses[1]["data"]["totalTracks"], 1)
            self.assertEqual(responses[2]["data"]["status"], "moved")
            self.assertEqual(responses[3]["data"]["totalTracks"], 0)
            self.assertFalse(source.exists())

    def test_library_query_returns_real_local_track_records(self):
        from bridge.local_bridge import BackendApplication

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "zulu.mp3").write_bytes(b"zulu")
            (root / "alpha.flac").write_bytes(b"alpha")
            config = ConfigStore(root / "config.json")
            app = BackendApplication(config)
            config.set_root(str(root))

            summary = app.load_library({"sortField": "name", "sortDirection": "asc", "limit": 10})

            self.assertEqual(summary["totalTracks"], 2)
            self.assertFalse(summary["hasMore"])
            self.assertEqual([track["name"] for track in summary["tracks"]], ["alpha.flac", "zulu.mp3"])
            self.assertEqual(summary["tracks"][0]["relativePath"], "alpha.flac")

    def test_ping_and_shutdown_are_json_lines_without_gui_dependencies(self):
        process = subprocess.Popen(
            [sys.executable, "-m", "bridge.local_bridge"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdin, stdout, stderr = process.stdin, process.stdout, process.stderr
        assert stdin is not None
        assert stdout is not None
        assert stderr is not None
        stdin.write(json.dumps({"id": "one", "command": "ping", "payload": {}}) + "\n")
        stdin.flush()
        ping = json.loads(stdout.readline())
        stdin.write(json.dumps({"id": "two", "command": "shutdown", "payload": {}}) + "\n")
        stdin.flush()
        shutdown = json.loads(stdout.readline())
        process.wait(timeout=5)
        stdin.close()
        stdout.close()
        stderr.close()

        self.assertEqual(ping["id"], "one")
        self.assertTrue(ping["ok"])
        self.assertTrue(ping["data"]["ready"])
        self.assertEqual(shutdown["id"], "two")
        self.assertTrue(shutdown["data"]["shuttingDown"])
        self.assertEqual(process.returncode, 0)

    def test_bridge_returns_structured_unknown_command_error(self):
        from bridge.local_bridge import BackendApplication, serve
        from io import StringIO

        output = StringIO()
        serve(StringIO('{"id":"bad","command":"missing","payload":{}}\n'), output, BackendApplication(ConfigStore(Path(tempfile.mkdtemp()) / "config.json")))
        response = json.loads(output.getvalue())

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "UNKNOWN_COMMAND")


class FilesystemAuthorityTests(unittest.TestCase):
    def test_default_genre_routes_exclude_their_generated_folders(self):
        prefixes = destination_prefixes(default_routes())

        self.assertIn("House/Inicio", prefixes)
        self.assertIn("Techno/Ponchadas", prefixes)
        self.assertIn("Progressive House/Medio", prefixes)
        self.assertIn("Needs Review", prefixes)

    def test_sorting_keeps_unknown_values_after_known_values_in_both_directions(self):
        def track(name: str, bpm: float | None) -> TrackRecord:
            return TrackRecord(f"id-{name}", f"C:/{name}", name, name, None, None, bpm, None, None)

        tracks = [track("unknown.mp3", None), track("128.mp3", 128), track("124.mp3", 124)]

        self.assertEqual([item.name for item in sort_tracks(tracks, SortField.BPM, SortDirection.ASCENDING)], ["124.mp3", "128.mp3", "unknown.mp3"])
        self.assertEqual([item.name for item in sort_tracks(tracks, SortField.BPM, SortDirection.DESCENDING)], ["128.mp3", "124.mp3", "unknown.mp3"])

    def test_route_folder_is_persisted_relative_to_root_and_external_folder_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            config = ConfigStore(root / "config.json")
            config.set_root(str(root))
            selected = root / "DJ Sets" / "August 31"
            selected.mkdir(parents=True)

            document = config.set_route_path("1", str(selected), "August 31")

            route = next(item for item in document["routes"] if item["routeId"] == "1")
            self.assertEqual(route["label"], "August 31")
            self.assertEqual(route["relativeDestination"], "DJ Sets/August 31/{bpmBucket}")
            with self.assertRaises(ValueError):
                config.set_route_path("1", outside, "Outside")

    def test_move_and_undo_keep_source_inside_root_and_exclude_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "song.mp3"
            source.write_bytes(b"fixture")
            config = ConfigStore(root / "config.json")
            config.set_root(str(root))
            config.set_routes([RoutePreset("1", "House", "{genre}/Inicio/{bpmBucket}", "Inicio", "House").to_dict()] + [
                RoutePreset(str(index), f"Route {index}", "Needs Review/{bpmBucket}").to_dict()
                for index in range(2, 10)
            ])
            relative = source.relative_to(root)
            track_id = track_id_for(relative)
            classifier = Classifier(config)

            result = classifier.move(track_id, "1")
            destination = root / "House" / "Inicio" / "BPM UNKNOWN" / "song.mp3"
            self.assertEqual(result.status.value, "moved")
            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())
            self.assertEqual([path.name for path in LibraryScope(root, ["House/Inicio"]).paths()], [])

            undo = classifier.undo()
            self.assertEqual(undo.status.value, "moved")
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())

    def test_destination_conflict_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "song.mp3"
            source.write_bytes(b"source")
            destination = root / "Needs Review" / "BPM UNKNOWN" / source.name
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"destination")
            config = ConfigStore(root / "config.json")
            config.set_root(str(root))
            config.set_routes([{
                "routeId": str(index),
                "label": f"Route {index}",
                "relativeDestination": "Needs Review/{bpmBucket}",
                "category": None,
                "genre": None,
            } for index in range(1, 10)])
            result = Classifier(config).move(track_id_for(source.relative_to(root)), "1")

            self.assertEqual(result.status.value, "destination_exists")
            self.assertEqual(source.read_bytes(), b"source")
            self.assertEqual(destination.read_bytes(), b"destination")


if __name__ == "__main__":
    unittest.main()

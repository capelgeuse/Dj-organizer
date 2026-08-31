"""Tests for the headless bridge and fail-closed move authority."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from architecture.contracts import RoutePreset
from core.classifier import Classifier
from core.config import ConfigStore
from core.library_scope import LibraryScope, track_id_for


class BridgeTests(unittest.TestCase):
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

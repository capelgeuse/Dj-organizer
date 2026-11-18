import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rekordbox_bridge import configure_connection, inspect_connection, inspect_tracks, _analysis_tags


def anlz(path, audio, *, waveform=True, grid=True):
    parts = []
    def tag(kind, header, body):
        return kind + struct.pack(">II", header, 12 + len(body)) + body
    encoded = str(audio).replace("\\", "/").encode("utf-16-be") + b"\0\0"
    parts.append(tag(b"PPTH", 16, struct.pack(">I", len(encoded)) + encoded))
    if grid:
        parts.append(tag(b"PQTZ", 24, b"\0" * 4 + struct.pack(">IIHHI", 0x80000, 1, 1, 12000, 0)))
    if waveform:
        parts.append(tag(b"PWAV", 20, struct.pack(">II", 2, 0x10000) + bytes([8, 16])))
    body = b"".join(parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PMAI" + struct.pack(">II", 28, 28 + len(body)) + b"\0" * 16 + body)


class BridgeTests(unittest.TestCase):
    def test_configuration_preserves_unknown_values_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = root / "rekordbox3.settings"
            original = b'<PROPERTIES><VALUE name="showRbXml" val="0"/><VALUE name="bridgeImportedLibraryFile" val="old.xml"/><VALUE name="untouched" val="private value"/></PROPERTIES>'
            settings.write_bytes(original)
            xml = root / "CapelHouse.xml"
            xml.write_text('<DJ_PLAYLISTS Version="1.0.0"/>', encoding="utf-8")
            with patch("rekordbox_bridge.rekordbox_running", return_value=False):
                result = configure_connection(xml, settings)
                info = inspect_connection(settings, xml)
            self.assertTrue(info["configured"])
            self.assertTrue(info["auto_analysis"])
            self.assertEqual(Path(result["backup"]).read_bytes(), original)
            self.assertEqual(ET.parse(settings).find(".//*[@name='untouched']").get("val"), "private value")
            before = settings.read_bytes()
            with patch("rekordbox_bridge.rekordbox_running", return_value=True), self.assertRaises(RuntimeError):
                configure_connection(xml, settings)
            self.assertEqual(settings.read_bytes(), before)

    def test_changed_settings_and_starting_process_do_not_get_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = root / "rekordbox3.settings"
            settings.write_text('<PROPERTIES/>', encoding="utf-8")
            xml = root / "CapelHouse.xml"
            xml.write_text('<DJ_PLAYLISTS/>', encoding="utf-8")
            before = settings.read_bytes()
            with patch("rekordbox_bridge.rekordbox_running", side_effect=[False, True]), self.assertRaises(RuntimeError):
                configure_connection(xml, settings)
            self.assertEqual(settings.read_bytes(), before)

    def test_status_requires_native_metadata_and_valid_analysis_for_same_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audio = root / "House" / "song.wav"
            audio.parent.mkdir()
            audio.write_bytes(b"test audio")
            record = {"id": "track", "path": str(audio), "genre": "House", "rating": 3, "color": "Morado"}
            native = {"id": "native1", "path": str(audio), "genre": "House", "rating": 3, "color_id": "8", "analysis": "/PIONEER/USBANLZ/a/b/ANLZ0000.DAT"}
            data = root / "share/PIONEER/USBANLZ/a/b/ANLZ0000.DAT"
            class Reader:
                def __init__(self):
                    self.root = root
                    self.closed = False
                def rows(self):
                    return [native]
                def close(self):
                    self.closed = True
            reader = Reader()
            state = lambda: inspect_tracks([record], lambda: reader)[0]["state"]
            self.assertEqual(state(), "imported")
            anlz(data, audio)
            self.assertEqual(state(), "ready")
            anlz(data, "?/song.wav")
            self.assertEqual(state(), "ready")
            self.assertTrue(reader.closed)
            native["rating"] = 0
            self.assertEqual(state(), "metadata_mismatch")
            native["rating"] = 3
            anlz(data, root / "wrong.wav")
            self.assertEqual(state(), "imported")
            anlz(data, audio, waveform=False)
            self.assertEqual(state(), "imported")
            data.write_bytes(b"corrupt")
            self.assertEqual(state(), "unverifiable")
            native["path"] = str(root / "another.wav")
            self.assertEqual(state(), "not_imported")
            audio.unlink()
            self.assertEqual(state(), "missing")

    def test_unreadable_native_library_is_not_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / "a.mp3"
            audio.write_bytes(b"audio")
            def unavailable():
                raise RuntimeError("Biblioteca no disponible")
            result = inspect_tracks([{"id": "1", "path": str(audio)}], unavailable)
            self.assertEqual(result[0]["state"], "unverifiable")


if __name__ == "__main__":
    unittest.main()

import csv
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import xml.etree.ElementTree as ET


spec = importlib.util.spec_from_file_location("rekordbox_export", Path(__file__).resolve().parents[1] / "rekordbox_export.py")
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


class ExportTests(unittest.TestCase):
    def test_contract_palette_and_playlists(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            tracks = []
            colors = list(export.COLOURS) + ["Sin color"]
            for i, color in enumerate(colors):
                path = base / f"canción & {i}.mp3"
                path.touch()
                tracks.append(dict(id=f"uuid-{i}", path=str(path), name="fallback", title='A & <"B">',
                                   artist="Björk", genre="House & <dance>" if i < 5 else "Morado",
                                   rating=i % 6, color=color, duration=42.9, comments="á & <>"))
            result = export.export_library(tracks, base / "out")
            self.assertEqual(result["count"], 9)
            self.assertEqual(result["missing"], [])
            self.assertEqual(result["report"].name, "missing_files.txt")
            self.assertIn("Total: 0", result["report"].read_text(encoding="utf-8"))
            self.assertRegex(result["xml"].parent.name, r"^rekordbox-export-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-.+")
            root = ET.parse(result["xml"]).getroot()
            self.assertEqual(root.tag, "DJ_PLAYLISTS")
            collection = root.find("COLLECTION")
            self.assertEqual(collection.get("Entries"), "9")
            rows = collection.findall("TRACK")
            ids = [row.get("TrackID") for row in rows]
            self.assertEqual(len(set(ids)), 9)
            for i, row in enumerate(rows):
                self.assertTrue(0 < int(ids[i]) < 2**31)
                self.assertEqual(row.get("Rating"), str(i % 6 * 51))
                self.assertEqual(row.get("Colour"), export.COLOURS.get(colors[i]))
                self.assertEqual(row.get("Name"), 'A & <"B">')
                self.assertIn("canci%C3%B3n%20%26%20", row.get("Location"))
                self.assertEqual(row.get("TotalTime"), "42")
                self.assertIsNone(row.get("AverageBpm"))
                self.assertEqual(list(row), [])
            nodes = root.findall("./PLAYLISTS/NODE/NODE")
            self.assertEqual({n.get("Name") for n in nodes}, {"House & <dance>", "Morado"})
            self.assertEqual({t.get("Key") for n in nodes for t in n}, set(ids))
            self.assertTrue(result["csv"].read_bytes().startswith(b"\xef\xbb\xbf"))
            with result["csv"].open(encoding="utf-8-sig", newline="") as f:
                self.assertEqual(list(csv.DictReader(f))[0]["comments"], "á & <>")
            self.assertIn(str(tracks[0]["path"]), result["m3u"].read_text(encoding="utf-8"))
            again = export.export_library(list(reversed(tracks)), base / "out")
            self.assertNotEqual(result["xml"], again["xml"])
            self.assertEqual(set(ids), {r.get("TrackID") for r in ET.parse(again["xml"]).findall("./COLLECTION/TRACK")})

    def test_missing_duplicates_and_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / "a.mp3"
            path.touch()
            track = {"id": "x", "path": str(path), "genre": ""}
            result = export.export_library([track, track, {"path": str(base / "faltante canción.mp3")}, {"path": "relative"}, {"path": ""}], base / "out")
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["missing"], [str(base / "faltante canción.mp3"), "relative", ""])
            report = result["report"].read_text(encoding="utf-8")
            self.assertEqual(result["report"].parent, result["xml"].parent)
            self.assertIn("Total: 3", report)
            self.assertIn(str(base / "faltante canción.mp3"), report)
            self.assertIn("relative", report)
            self.assertIn("(ruta vacía)", report)
            with result["csv"].open(encoding="utf-8-sig", newline="") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 1)
            with self.assertRaises(ValueError):
                export.export_library([{"path": str(base / "missing")}], base / "none")
            self.assertFalse((base / "none").exists())
            with self.assertRaises(ValueError):
                export.export_library([dict(track, rating=6)], base / "none")

    def test_windows_uri_and_genre_coalescing(self):
        self.assertEqual(export._file_uri('C:\\Música\\a #%.mp3'), 'file://localhost/C:/M%C3%BAsica/a%20%23%25.mp3')
        self.assertEqual(export._file_uri('\\\\server\\share\\a b.mp3'), 'file://server/share/a%20b.mp3')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            a, b = base / "a", base / "b"
            a.touch(); b.touch()
            result = export.export_library([{"id": "a", "path": str(a), "genre": ""},
                                            {"id": "b", "path": str(b), "genre": "Sin género"}], base / "out")
            nodes = ET.parse(result["xml"]).findall("./PLAYLISTS/NODE/NODE")
            self.assertEqual(len(nodes), 1)
            self.assertEqual(nodes[0].get("Entries"), "2")


class PublishTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.base = Path(directory)
        self.bridge = self.base / "Bridge"
        self.tracks = []
        for i, genre in enumerate(("House", "House", "")):
            path = self.base / f"canción {i} #%.wav"
            with wave.open(str(path), "wb") as audio:
                audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                audio.writeframes(b"\x00\x00" * 8000)
            self.tracks.append(dict(id=f"track-{i}", path=str(path), title=f"Música & <{i}>",
                                    artist="Björk", genre=genre, rating=i + 1, color="Azul",
                                    duration=1, comments="Keep  this\tcomment & <tag>"))

    def test_republish_full_snapshot_at_same_paths_with_archives(self):
        kinds = ("xml", "csv", "m3u", "report")
        audio_bytes = {Path(t["path"]): Path(t["path"]).read_bytes() for t in self.tracks}
        first = export.publish_library(self.tracks, self.bridge)
        self.assertEqual(set(first), {*kinds, "count", "missing", "published_at", "archive"})
        self.assertEqual(first["xml"], self.bridge / "CapelHouse.xml")
        self.assertTrue(all(first[k].parent == self.bridge for k in kinds))
        first_bytes = {k: first[k].read_bytes() for k in kinds}
        first_archive, = self.bridge.glob("rekordbox-export-*")
        self.assertEqual(first["archive"], first_archive / "library.xml")

        updated = [dict(self.tracks[0], rating=5), dict(self.tracks[1], color="Rosa"), self.tracks[2]]
        second = export.publish_library(list(reversed(updated)), self.bridge)
        self.assertEqual(second["count"], len(updated))
        self.assertEqual(second["missing"], [])
        self.assertEqual({k: first[k] for k in kinds}, {k: second[k] for k in kinds})
        start, end = (datetime.fromisoformat(r["published_at"]) for r in (first, second))
        self.assertEqual(end.utcoffset(), timedelta(0))
        self.assertLessEqual(start, end)
        second_archive, = set(self.bridge.glob("rekordbox-export-*")) - {first_archive}
        self.assertEqual(second["archive"], second_archive / "library.xml")
        for kind, name in zip(kinds, ("library.xml", "metadata.csv", "playlist.m3u8", "missing_files.txt")):
            self.assertEqual((first_archive / name).read_bytes(), first_bytes[kind])
            self.assertEqual((second_archive / name).read_bytes(), second[kind].read_bytes())

        root = ET.parse(second["xml"]).getroot()
        self.assertEqual(root.attrib, {"Version": "1.0.0"})
        collection = root.find("COLLECTION")
        self.assertEqual(collection.get("Entries"), "3")
        old = {t.get("Location"): t.attrib for t in ET.fromstring(first_bytes["xml"]).findall("COLLECTION/TRACK")}
        rows = {t.get("Location"): t for t in collection}
        self.assertEqual(set(rows), set(old))
        ids = []
        for i, track in enumerate(updated):
            location = export._file_uri(track["path"])
            row = rows[location]
            ids.append(int(row.get("TrackID")))
            self.assertTrue(location.startswith("file://localhost/"))
            self.assertTrue(location.endswith(f"canci%C3%B3n%20{i}%20%23%25.wav"))
            self.assertEqual(row.attrib, dict(old[location], Rating=str(51 * track["rating"]),
                                              Colour=export.COLOURS[track["color"]]))
            self.assertEqual(row.get("Name"), track["title"])
            self.assertEqual(row.get("Artist"), track["artist"])
            self.assertEqual(row.get("Genre"), track["genre"])
            self.assertEqual(row.get("Comments"), track["comments"])
            self.assertIsNone(row.get("AverageBpm"))
            self.assertIsNone(row.get("Tonality"))
            self.assertEqual(list(row), [])
        self.assertEqual(len(set(ids)), 3)
        self.assertTrue(all(0 < track_id <= 2**31 - 1 for track_id in ids))
        top = root.find("PLAYLISTS/NODE")
        self.assertEqual(top.attrib, {"Name": "ROOT", "Type": "0", "Count": "1"})
        folder, = top
        self.assertEqual(folder.attrib, {"Name": "CapelHouse", "Type": "0", "Count": "2"})
        self.assertEqual({n.get("Name"): {t.get("Key") for t in n} for n in folder},
                         {"House": set(map(str, ids[:2])), "Sin género": {str(ids[2])}})
        self.assertEqual({path: path.read_bytes() for path in audio_bytes}, audio_bytes)

    def test_invalid_input_leaves_existing_publication_untouched(self):
        first = export.publish_library(self.tracks, self.bridge)
        before = {p: p.read_bytes() for p in self.bridge.iterdir() if p.is_file()}
        entries = set(self.bridge.iterdir())
        missing = {"path": str(self.base / "missing.wav")}
        cases = [([], "biblioteca está vacía"), ([missing], "missing.wav"),
                 ([self.tracks[0], missing], "discos conectados"), ([{"path": ""}], "ruta vacía"),
                 ([dict(self.tracks[0], color="unknown")], "unknown color")]
        for batch, message in cases:
            with self.subTest(batch=batch), self.assertRaisesRegex(ValueError, message):
                export.publish_library(batch, self.bridge)
        self.assertIn(first["xml"], before)
        self.assertEqual(set(self.bridge.iterdir()), entries)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_staging_failure_leaves_stable_files_untouched(self):
        export.publish_library(self.tracks, self.bridge)
        before = {p: p.read_bytes() for p in self.bridge.iterdir() if p.is_file()}
        copyfile = export.shutil.copyfile

        def fail_xml_copy(source, target):
            if target.name == "CapelHouse.xml":
                raise OSError("staging failed")
            copyfile(source, target)

        updated = [dict(track, rating=5) for track in self.tracks]
        with patch.object(export.shutil, "copyfile", side_effect=fail_xml_copy):
            with self.assertRaisesRegex(OSError, "staging failed"):
                export.publish_library(updated, self.bridge)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual(list(self.bridge.glob(".capelhouse-publish-*")), [])

    def test_locked_xml_keeps_previous_snapshot_and_can_be_retried(self):
        first = export.publish_library(self.tracks, self.bridge)
        old_xml = first["xml"].read_bytes()
        replace = export.os.replace

        def locked_replace(source, target):
            if target == first["xml"]:
                self.assertEqual(source.read_bytes()[:5], b"<?xml")
                self.assertEqual(source.parent.parent, self.bridge)
                raise PermissionError("XML is open")
            replace(source, target)

        updated = [dict(track, color="Sin color") for track in self.tracks]
        with patch.object(export.os, "replace", side_effect=locked_replace):
            with self.assertRaisesRegex(PermissionError, "XML is open"):
                export.publish_library(updated, self.bridge)
        self.assertEqual(first["xml"].read_bytes(), old_xml)
        self.assertEqual(list(self.bridge.glob(".capelhouse-publish-*")), [])
        latest = export.publish_library(updated, self.bridge)
        self.assertEqual(latest["xml"], first["xml"])
        rows = ET.parse(latest["xml"]).findall("COLLECTION/TRACK")
        self.assertEqual(len(rows), len(updated))
        self.assertTrue(all("Colour" not in row.attrib for row in rows))


if __name__ == "__main__":
    unittest.main()

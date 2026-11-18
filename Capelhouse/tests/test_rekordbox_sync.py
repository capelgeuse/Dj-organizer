import hashlib
import json
import os
from contextlib import closing
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rekordbox_sync as sync
from rekordbox_bridge import COLOR_IDS, NativeReader, _normalized, inspect_tracks


class SyncTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / "fixture.db"
        self.database.touch()
        self.track = {"path": str(Path(temp.name) / "managed" / "Track.wav"),
                      "genre": "House", "rating": 5, "color": "Morado"}
        self.missing = dict(self.track, path=str(Path(temp.name) / "other" / "Track.wav"))
        self.reader = Mock()
        self.reader.connection.execute.return_value.fetchone.return_value = (0, "main", str(self.database))
        self.reader.rows.return_value = [{"id": "7", "path": self.track["path"].upper(),
                                         "rating": 0, "color_id": "0", "genre": "Old"}]
        self.writer = Mock()
        self.row = SimpleNamespace(FolderPath=self.track["path"], Rating=0, ColorID="0", GenreID="1",
                                   AnalysisDataPath="/PIONEER/ANLZ.dat")
        self.writer.get_content.return_value = self.row
        self.writer.get_genre.return_value.first.return_value = None
        self.writer.add_genre.return_value.ID = "8"
        for name, value in (("NativeReader", self.reader), ("_open_writer", self.writer),
                            ("_backup", self.database.with_suffix(".bak.db"))):
            patcher = patch.object(sync, name, return_value=value)
            mock = patcher.start()
            self.addCleanup(patcher.stop)
            setattr(self, name, mock)

    def test_updates_only_unique_exact_path(self):
        with patch.object(sync, "rekordbox_running", return_value=False):
            result = sync.apply_classification([self.track, self.missing, self.track], self.database)
        self.assertEqual(result, {"updated": 1, "backup": str(self.database.with_suffix(".bak.db")),
                                  "missing": [self.missing["path"]]})
        self.assertEqual((self.row.Rating, self.row.ColorID, self.row.GenreID), (5, "8", "8"))
        self.assertEqual(self.row.AnalysisDataPath, "/PIONEER/ANLZ.dat")
        self.writer.get_content.assert_called_once_with(ID="7")
        self.writer.get_genre.assert_called_once_with(Name="House")
        self.writer.add_genre.assert_called_once_with("House")
        self.writer.commit.assert_called_once_with()
        self.writer.rollback.assert_not_called()
        self.assertIsNone(self.writer.playlist_xml)

    def test_running_prevents_open_and_relaunch_prevents_commit(self):
        with patch.object(sync, "rekordbox_running", return_value=True), self.assertRaises(RuntimeError):
            sync.apply_classification([self.track], self.database)
        self.NativeReader.assert_not_called()
        with patch.object(sync, "rekordbox_running", side_effect=[False, False, True]):
            with self.assertRaisesRegex(RuntimeError, "Respaldo conservado"):
                sync.apply_classification([self.track], self.database)
        self.writer.commit.assert_not_called()
        self.writer.rollback.assert_called_once_with()

    def test_ambiguous_match_and_no_change_do_not_back_up_or_commit(self):
        row = self.reader.rows.return_value[0]
        self.reader.rows.return_value.append(dict(row, id="8"))
        with patch.object(sync, "rekordbox_running", return_value=False):
            result = sync.apply_classification([self.track], self.database)
            self.assertEqual(result, {"updated": 0, "backup": "", "missing": [self.track["path"]]})
            self.reader.rows.return_value = [dict(row, rating=5, color_id="8", genre="House")]
            self.assertEqual(sync.apply_classification([self.track], self.database),
                             {"updated": 0, "backup": "", "missing": []})
        self._backup.assert_not_called()
        self.writer.get_content.assert_not_called()
        self.writer.commit.assert_not_called()

    def test_validation_and_backup_failure_do_not_mutate(self):
        with self.assertRaises(ValueError):
            sync.apply_classification([dict(self.track, rating=True)], self.database)
        with self.assertRaises(ValueError):
            sync.apply_classification([self.track, dict(self.track, color="Rojo")], self.database)
        self.NativeReader.assert_not_called()
        self._backup.side_effect = OSError("private failure details")
        with patch.object(sync, "rekordbox_running", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "No se pudo aplicar"):
                sync.apply_classification([self.track], self.database)
        self.writer.get_content.assert_not_called()
        self.writer.commit.assert_not_called()
        self.writer.rollback.assert_called_once_with()


@unittest.skipUnless(os.environ.get("CAPELHOUSE_TEST_NATIVE_DB") and os.environ.get("CAPELHOUSE_TEST_LIBRARY"),
                     "opt-in encrypted snapshot test; only the disposable copy is writable")
class NativeSnapshotTests(unittest.TestCase):
    def test_native_encrypted_copy_preserves_source_and_analysis(self):
        source = Path(os.environ["CAPELHOUSE_TEST_NATIVE_DB"]).resolve(strict=True)
        library = Path(os.environ["CAPELHOUSE_TEST_LIBRARY"])
        tracks = json.loads(library.read_text(encoding="utf-8-sig"))["tracks"]
        self.assertTrue(tracks)
        file_digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        fingerprint = file_digest(source)
        copy_parent = Path(__file__).resolve().parents[1] / "qa" / "native-copy"
        copy_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=copy_parent) as folder:
            copied = Path(folder) / "master.db"
            with closing(NativeReader(source)) as reader:
                original = reader.rows()
                snapshot = sync._backup(reader, copied)
            snapshot.rename(copied)
            self.assertNotEqual(copied.resolve(), source)
            # Exercise the production lock + separate read-only backup in WAL mode.
            with patch("pyrekordbox.masterdb.database.get_rekordbox_pid", return_value=0):
                writer = sync._open_writer(copied)
                try:
                    mode = writer.session.connection().exec_driver_sql("PRAGMA journal_mode=WAL").scalar_one()
                    self.assertEqual(mode, "wal")
                finally:
                    writer.close()
                    writer.engine.dispose()
            with closing(NativeReader(copied)) as reader:
                self.assertEqual(reader.connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                def counts(connection):
                    return [connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                            for table in ("djmdContent", "djmdCue")]

                def usn(connection):
                    return connection.execute("SELECT int_1 FROM agentRegistry WHERE registry_id='localUpdateCount'").fetchone()[0]

                before_counts, before_usn = counts(reader.connection), usn(reader.connection)
                before = reader.rows()
            self.assertEqual(before, original)
            by_path = {_normalized(row["path"]): row for row in before if row["path"]}
            changed = 0
            for track in tracks:
                row = by_path[_normalized(track["path"])]
                self.assertTrue(row["analysis"])
                changed += (row["rating"] or 0, str(row["color_id"] or "0"), row["genre"] or "") != (
                    track.get("rating", 0), COLOR_IDS[track.get("color", "Sin color")], track.get("genre", ""))
            self.assertGreater(changed, 0, "the snapshot must exercise a real repair")
            with patch.object(sync, "rekordbox_running", return_value=False), patch(
                "pyrekordbox.masterdb.database.get_rekordbox_pid", return_value=0
            ):
                result = sync.apply_classification(tracks, copied)
                repeat = sync.apply_classification(tracks, copied)
            print(f"Encrypted snapshot: {len(tracks)} requested tracks, {result['updated']} updated")
            self.assertEqual(result["updated"], changed)
            self.assertEqual(result["missing"], [])
            self.assertEqual(repeat, {"updated": 0, "backup": "", "missing": []})
            backup = Path(result["backup"])
            self.assertEqual(backup.parent, copied.parent)
            self.assertTrue(backup.name.endswith(".bak.db"))
            with closing(NativeReader(backup)) as reader:
                self.assertEqual(reader.rows(), before)
                self.assertEqual(usn(reader.connection), before_usn)
            with closing(NativeReader(copied)) as reader:
                after = reader.rows()
                self.assertEqual(counts(reader.connection), before_counts)
                self.assertGreater(usn(reader.connection), before_usn)
            after_by_id = {row["id"]: row for row in after}
            self.assertEqual({row["id"]: (row["path"], row["analysis"]) for row in before},
                             {row["id"]: (row["path"], row["analysis"]) for row in after})
            for track in tracks:
                row = after_by_id[by_path[_normalized(track["path"])]["id"]]
                self.assertEqual((row["rating"], str(row["color_id"]), row["genre"] or ""),
                                 (track["rating"], COLOR_IDS[track["color"]], track["genre"]))

            def copied_reader_with_native_analysis():
                reader = NativeReader(copied)
                reader.root = source.parent
                return reader

            statuses = inspect_tracks(tracks, db_factory=copied_reader_with_native_analysis)
            self.assertEqual([row["state"] for row in statuses], ["ready"] * len(tracks), statuses)
            with closing(NativeReader(source)) as reader:
                self.assertEqual(reader.rows(), original)
            self.assertEqual(file_digest(source), fingerprint)


if __name__ == "__main__":
    unittest.main()

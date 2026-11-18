"""Integration of real Qt controls, background library tasks and exported metadata."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import tempfile
import time
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox
from unittest.mock import patch
from CapelHouse_Qt import App
from demo import create_demo


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def wait_job(self, window):
        end = time.monotonic() + 15
        while window.busy and time.monotonic() < end:
            self.qt.processEvents()
            QTest.qWait(20)
        self.assertFalse(window.busy, "Background job did not complete")
        self.qt.processEvents()

    def test_prepare_filter_edit_export_and_preserve_original(self):
        with tempfile.TemporaryDirectory() as directory:
            config = create_demo(directory)
            window = App(config)
            window.show()
            self.qt.processEvents()
            self.wait_job(window)
            self.assertEqual(len(window.pending), 3)
            source = window.current
            window.autoplay.setChecked(False)
            window.set_rating(3)
            window.color_combo.setCurrentText("Morado")
            self.assertEqual(window.current_rating, 3)
            window.set_rating(5)
            self.assertEqual(window.color_combo.currentText(), "Morado")
            window.set_rating(3)
            window.classify()
            self.wait_job(window)
            self.assertTrue(source.exists())
            record = window.library.tracks[0]
            self.assertEqual((record["rating"], record["color"]), (3, "Morado"))
            self.assertEqual(Path(record["path"]).parent.name, "House")
            self.assertEqual(len(window.pending), 2)
            window.tabs.setCurrentIndex(1)
            self.qt.processEvents()
            self.assertEqual(window.current_record["id"], record["id"])
            window.set_rating(1)
            window.classify()
            self.wait_job(window)
            self.assertEqual(window.library.tracks[0]["color"], "Morado")
            self.assertEqual(window.library.tracks[0]["rating"], 1)
            window.color_filter.setCurrentText("Rojo")
            self.assertEqual(window.prepared_table.rowCount(), 0)
            window.color_filter.setCurrentText("Morado")
            self.assertEqual(window.prepared_table.rowCount(), 1)
            export_folder = Path(directory) / "Export"
            export_folder.mkdir()
            with patch.object(QFileDialog, "getExistingDirectory", return_value=str(export_folder)), patch.object(QMessageBox, "exec", return_value=QMessageBox.Ok):
                window.export()
                self.wait_job(window)
            track = ET.parse(window.last_export["xml"]).find("COLLECTION/TRACK")
            self.assertEqual(track.attrib["Rating"], "51")
            self.assertEqual(track.attrib["Colour"], "0x660099")
            window.close()
            self.qt.processEvents()
            reloaded = App(config)
            self.qt.processEvents()
            self.wait_job(reloaded)
            self.assertEqual(reloaded.library.tracks[0]["rating"], 1)
            self.assertEqual(reloaded.library.tracks[0]["color"], "Morado")
            reloaded.close()
            self.qt.processEvents()

    def test_shortcuts_do_not_intercept_search_or_modal(self):
        with tempfile.TemporaryDirectory() as directory:
            window = App(create_demo(directory))
            window.show()
            self.qt.processEvents()
            self.wait_job(window)
            window.set_rating(3)
            window.pending_search.setFocus()
            QTest.keyClicks(window.pending_search, "House 5")
            self.assertEqual(window.pending_search.text(), "House 5")
            window.pending_search.clear()
            self.assertEqual(window.current_rating, 3)
            dialog = QInputDialog(window)
            dialog.setModal(True)
            dialog.show()
            self.qt.processEvents()
            QTest.keyClick(dialog, Qt.Key_5)
            self.assertEqual(window.current_rating, 3)
            dialog.close()
            window.close()
            self.qt.processEvents()

    def test_send_publishes_full_library_and_never_marks_ready_from_xml(self):
        with tempfile.TemporaryDirectory() as directory:
            window = App(create_demo(directory))
            window.show()
            self.qt.processEvents()
            self.wait_job(window)
            window.autoplay.setChecked(False)
            window.library.config["rekordbox_bridge_dir"] = str(Path(directory) / "bridge")
            window.set_rating(3)
            window.color_combo.setCurrentText("Morado")
            window.classify()
            self.wait_job(window)
            window.set_rating(5)
            window.color_combo.setCurrentText("Aqua")
            window.classify()
            self.wait_job(window)
            window.tabs.setCurrentIndex(1)
            window.color_filter.setCurrentText("Morado")
            self.assertEqual(window.prepared_table.rowCount(), 1)
            with patch.object(window, "show_connection_dialog") as show_dialog:
                window.send_to_rekordbox()
                self.wait_job(window)
                show_dialog.assert_called_once()
            xml = window.last_export["xml"]
            self.assertEqual(xml.name, "CapelHouse.xml")
            self.assertEqual(len(ET.parse(xml).findall("COLLECTION/TRACK")), 2)
            self.assertEqual(window.rb_states, {})
            self.assertEqual(window.prepared_table.item(0, 4).text(), "Sin verificar")
            with patch("CapelHouse_Qt.inspect_tracks", return_value=[{"id": record["id"], "state": "not_imported", "detail": "No está en Colección"} for record in window.library.tracks]):
                window.refresh_rekordbox_status()
                self.wait_job(window)
            self.assertEqual(window.prepared_table.item(0, 4).text(), "No importada")
            self.assertNotIn("Lista", window.status.text())
            window.set_rating(4)
            with patch.object(window, "open_track") as reopen:
                window.rekordbox_status_received(list(window.rb_states.values()))
                reopen.assert_not_called()
            self.assertEqual(window.current_rating, 4)
            with patch.object(window, "show_connection_dialog"):
                window.send_to_rekordbox()
                self.wait_job(window)
            self.assertEqual(window.last_export["xml"], xml)
            window.close()
            self.qt.processEvents()


if __name__ == "__main__":
    unittest.main()

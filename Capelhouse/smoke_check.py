"""End-to-end check usable from source and the packaged executable."""
import json
import traceback
import time
from pathlib import Path
import xml.etree.ElementTree as ET
from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaPlayer

from demo import create_demo
from rekordbox_export import publish_library


def start_check(qt, directory):
    from CapelHouse_Qt import App
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    config = create_demo(directory / "datos")
    window = App(config)
    window.resize(1240, 850)
    window.show()
    result = {"passed": False, "checks": []}
    stage = [0]
    began = time.monotonic()
    timer = QTimer(window)

    def finish(error=None):
        timer.stop()
        if error:
            result["error"] = error
        else:
            result["passed"] = True
        (directory / "resultado.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        window.player.stop()
        window.close()
        qt.exit(1 if error else 0)

    def tick():
        try:
            if time.monotonic() - began > 45:
                raise RuntimeError("La prueba superó 45 segundos")
            if window.busy:
                return
            if stage[0] == 0:
                assert window.current and window.current.is_file(), "No se cargó el audio de prueba"
                window.autoplay.setChecked(False)
                window.player.play()
                stage[0] = 1
            elif stage[0] == 1:
                if window.player.error() != QMediaPlayer.NoError:
                    raise RuntimeError(window.player.errorString())
                if window.player.duration() <= 0 or window.player.position() < 250:
                    return
                result["checks"].append("Reproducción y decodificación de WAV en QtMultimedia")
                window.player.pause()
                window.set_rating(3)
                window.color_combo.setCurrentText("Morado")
                window.set_rating(5)
                assert window.color_combo.currentText() == "Morado"
                window.set_rating(3)
                stage[0] = 2
                window.classify()
            elif stage[0] == 2:
                record = window.library.tracks[0]
                assert record["rating"] == 3 and record["color"] == "Morado"
                assert Path(record["source"]).is_file()
                assert Path(record["path"]).parent.name == "House"
                result["checks"].append("Guardar por género conserva el original y los valores independientes")
                published = publish_library(window.library.tracks, directory / "Conexion")
                result["export"] = {key: str(value) for key, value in published.items()}
                xml = ET.parse(result["export"]["xml"]).find("COLLECTION/TRACK")
                assert xml.get("Rating") == "153" and xml.get("Colour") == "0x660099"
                assert Path(published["xml"]).name == "CapelHouse.xml"
                repeated = publish_library(window.library.tracks, directory / "Conexion")
                assert repeated["xml"] == published["xml"]
                assert ET.parse(repeated["xml"]).find("./PLAYLISTS/NODE/NODE").get("Name") == "CapelHouse"
                assert not window.rb_states
                result["checks"].append("Publicación y actualización en la misma ruta, con 3 estrellas y morado")
                result["checks"].append("Publicar XML no da por hecho que la canción esté importada o analizada")
                window.tabs.setCurrentIndex(1)
                window.prepared_table.selectRow(0)
                stage[0] = 3
            elif stage[0] == 3:
                window.grab().save(str(directory / "CapelHouse.png"))
                result["screenshot"] = str(directory / "CapelHouse.png")
                result["checks"].append("Ventana renderizada con selección preparada")
                finish()
        except Exception:
            finish(traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start(100)
    return qt.exec()

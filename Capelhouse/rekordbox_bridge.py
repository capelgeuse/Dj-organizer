"""Stable XML connection and strictly read-only Rekordbox library verification.

No master.db writer is instantiated. Native queries use SQLCipher mode=ro and
query_only; missing or unreadable evidence can never produce a ready result.
"""
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET


COLOR_IDS = {"Sin color": "0", "Rosa": "1", "Rojo": "2", "Naranja": "3", "Amarillo": "4",
             "Verde": "5", "Aqua": "6", "Azul": "7", "Morado": "8"}


def default_bridge_dir():
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CapelHouse" / "Rekordbox"


def find_settings():
    root = Path(os.environ.get("APPDATA", Path.home())) / "Pioneer"
    for directory in ("rekordbox6", "rekordbox7", "rekordbox"):
        candidate = root / directory / "rekordbox3.settings"
        if candidate.is_file():
            return candidate
    return None


def rekordbox_running():
    if os.name != "nt":
        return False
    import psutil
    for process in psutil.process_iter(["name"]):
        if (process.info.get("name") or "").casefold() == "rekordbox.exe":
            return True
    return False


def _settings(path):
    tree = ET.parse(path)
    values = {}
    for element in tree.iter():
        name = element.get("name")
        if name:
            values[name] = element.get("val", element.get("value", element.text or ""))
    return tree, values


def _normalized(path):
    return os.path.normcase(os.path.abspath(str(path).replace("\\", "/"))).casefold()


def _executable():
    candidates = []
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        root = Path(os.environ.get(key, "C:/Program Files")) / "rekordbox"
        if root.exists():
            candidates.extend(root.glob("rekordbox*/rekordbox.exe"))
    if not candidates:
        return None
    import re
    return max(candidates, key=lambda p: tuple(int(n) for n in re.findall(r"\d+", p.parent.name)))


def inspect_connection(settings_path=None, xml_path=None):
    path = Path(settings_path) if settings_path else find_settings()
    values = _settings(path)[1] if path and path.exists() else {}
    target = Path(xml_path) if xml_path else default_bridge_dir() / "CapelHouse.xml"
    executable = _executable()
    return {
        "settings_path": str(path) if path else None,
        "running": rekordbox_running(),
        "configured": bool(values.get("bridgeImportedLibraryFile") and
                           _normalized(values["bridgeImportedLibraryFile"]) == _normalized(target) and
                           values.get("showRbXml") == "1" and target.is_file()),
        "auto_analysis": values.get("AutoAnalysis") == "1",
        "xml": str(target),
        "imported_library": values.get("bridgeImportedLibraryFile", ""),
        "executable": str(executable) if executable else None,
        "version": executable.parent.name.replace("rekordbox", "").strip() if executable else None,
    }


def configure_connection(xml_path, settings_path=None):
    xml_path = Path(xml_path).resolve()
    if not xml_path.is_file() or ET.parse(xml_path).getroot().tag != "DJ_PLAYLISTS":
        raise ValueError("Publica primero una biblioteca XML válida desde CapelHouse.")
    if rekordbox_running():
        raise RuntimeError("Cierra Rekordbox y vuelve a pulsar Configurar conexión. No se cambiaron sus ajustes.")
    path = Path(settings_path) if settings_path else find_settings()
    if not path or not path.is_file():
        raise FileNotFoundError("Abre Rekordbox una vez para crear sus ajustes y después ciérralo.")
    original = path.read_bytes()
    tree, _ = _settings(path)
    changes = {"bridgeImportedLibraryFile": xml_path.as_posix(), "showRbXml": "1",
               "RekordboxXmlChecked": "1", "AutoAnalysis": "1"}
    for name, value in changes.items():
        nodes = [element for element in tree.iter() if element.get("name") == name]
        if not nodes:
            nodes = [ET.SubElement(tree.getroot(), "VALUE", name=name, val=value)]
        for node in nodes:
            attribute = "value" if "value" in node.attrib else "val"
            node.set(attribute, value)
    backup = path.with_name(path.name + ".capelhouse-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6] + ".bak")
    with backup.open("xb") as stream:
        stream.write(original)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".capelhouse-", delete=False) as stream:
            temporary = Path(stream.name)
            tree.write(stream, encoding="utf-8", xml_declaration=True)
            stream.flush()
            os.fsync(stream.fileno())
        if rekordbox_running() or path.read_bytes() != original:
            raise RuntimeError("Rekordbox o sus ajustes cambiaron durante la operación. No se reemplazó la configuración.")
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return {"settings": str(path), "backup": str(backup), "xml": str(xml_path)}


class NativeReader:
    def __init__(self, path=None):
        from sqlcipher3 import dbapi2
        from pyrekordbox.masterdb.database import BLOB
        from pyrekordbox.utils import deobfuscate
        root = Path(os.environ.get("APPDATA", Path.home())) / "Pioneer" / "rekordbox"
        database = Path(path) if path else root / "master.db"
        settings = find_settings()
        if path is None and settings:
            values = _settings(settings)[1]
            configured = values.get("masterDbDirectory")
            if configured:
                database = Path(configured) / "master.db"
        if not database.is_file():
            raise FileNotFoundError("No se encontró la colección nativa de Rekordbox.")
        self.root = database.parent
        self.connection = dbapi2.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        try:
            # Never print, return, persist or log the database key.
            self.connection.execute("PRAGMA key='" + deobfuscate(BLOB).replace("'", "''") + "'")
            self.connection.execute("PRAGMA query_only=ON")
            self.connection.execute("SELECT count(*) FROM djmdContent").fetchone()
        except Exception:
            self.close()
            raise RuntimeError("No se pudo leer la colección de esta versión de Rekordbox.") from None

    def rows(self):
        cursor = self.connection.execute(
            "SELECT c.ID, c.FolderPath, c.Rating, c.ColorID, c.AnalysisDataPath, "
            "g.Name FROM djmdContent c LEFT JOIN djmdGenre g ON c.GenreID=g.ID")
        return [dict(zip(("id", "path", "rating", "color_id", "analysis", "genre"), row)) for row in cursor]

    def close(self):
        self.connection.close()


def _analysis_tags(path):
    """Validate the ANLZ container before trusting any nonempty data tag."""
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"PMAI":
        raise ValueError("Cabecera de análisis inválida")
    header, total = struct.unpack_from(">II", data, 4)
    if header < 12 or total != len(data) or header > total:
        raise ValueError("Archivo de análisis incompleto")
    cursor, tags = header, set()
    while cursor < total:
        if cursor + 12 > total:
            raise ValueError("Etiqueta de análisis incompleta")
        name = data[cursor:cursor + 4]
        tag_header, size = struct.unpack_from(">II", data, cursor + 4)
        if tag_header < 12 or size < tag_header or cursor + size > total:
            raise ValueError("Longitud de análisis inválida")
        if size > tag_header:
            tags.add(name)
        cursor += size
    return tags


def _has_analysis(row, root, audio_path):
    from pyrekordbox.anlz import AnlzFile
    value = row.get("analysis") or ""
    if not value:
        return False
    normalized = str(value).replace("\\", "/")
    path = Path(normalized)
    # Relative AnalysisDataPath commonly starts with /PIONEER/... .
    if not path.is_absolute() or normalized.startswith("/PIONEER/"):
        path = root / "share" / normalized.lstrip("/")
    candidates = [path.with_suffix(extension) for extension in (".DAT", ".EXT", ".2EX")]
    tags = set()
    embedded_path = None
    nonempty_grid = False
    nonempty_waveform = False
    for candidate in candidates:
        if candidate.is_file():
            tags.update(_analysis_tags(candidate))
            parsed = AnlzFile.parse_file(candidate)
            if "PPTH" in parsed:
                embedded_path = parsed.get("PPTH")
            if "PQTZ" in parsed:
                nonempty_grid |= bool(len(parsed.get("PQTZ")[0]))
            for name in ("PWAV", "PWV2", "PWV3", "PWV4", "PWV5"):
                if name in parsed:
                    nonempty_waveform |= bool(len(parsed.get(name)[0]))
    embedded = str(embedded_path or "").replace("\\", "/")
    # Local Rekordbox 7.2.8 ANLZ files use ?/filename. The exact directory
    # association comes from the native row's AnalysisDataPath and FolderPath.
    same_audio = (embedded.startswith("?/") and embedded[2:].casefold() == audio_path.name.casefold())
    same_audio |= bool(embedded and _normalized(embedded) == _normalized(audio_path))
    if not same_audio:
        return False
    waveform = bool(tags & {b"PWAV", b"PWV2", b"PWV3", b"PWV4", b"PWV5", b"PWV6", b"PWV7"})
    return waveform and b"PQTZ" in tags and nonempty_grid and nonempty_waveform


def inspect_tracks(tracks, db_factory=None):
    result = []
    available = [record for record in tracks if Path(record.get("path", "")).is_file()]
    reader = None
    error = None
    native = {}
    if available:
        try:
            reader = (db_factory or NativeReader)()
            for row in reader.rows():
                native.setdefault(_normalized(row["path"]), []).append(row)
        except Exception as failure:
            error = str(failure) or "No se pudo verificar la biblioteca nativa."
    try:
        for record in tracks:
            state, detail = "unverifiable", error or "No se pudo verificar."
            if not Path(record.get("path", "")).is_file():
                state, detail = "missing", "El archivo de audio no está disponible en su ruta."
            elif error:
                pass
            else:
                rows = native.get(_normalized(record["path"]), [])
                if not rows:
                    state, detail = "not_imported", "La ruta no figura en Colección. Importa la playlist desde el panel rekordbox xml."
                elif len(rows) > 1:
                    state, detail = "unverifiable", "Hay varios registros nativos para esta ruta; revisa los duplicados en Rekordbox."
                else:
                    row = rows[0]
                    try:
                        rating = int(row.get("rating") or 0)
                        color_id = str(row.get("color_id") or "0")
                        genre = str(row.get("genre") or "")
                        matches = (rating == record.get("rating", 0) and
                                   color_id == COLOR_IDS.get(record.get("color", "Sin color")) and
                                   genre == record.get("genre", ""))
                        if not matches:
                            differences = []
                            if rating != record.get("rating", 0):
                                differences.append(f"estrellas: CapelHouse {record.get('rating', 0)}, Rekordbox {rating}")
                            if color_id != COLOR_IDS.get(record.get("color", "Sin color")):
                                native_color = next((name for name, value in COLOR_IDS.items() if value == color_id), "desconocido")
                                differences.append(f"color: CapelHouse {record.get('color')}, Rekordbox {native_color}")
                            if genre != record.get("genre", ""):
                                differences.append(f"género: CapelHouse {record.get('genre')}, Rekordbox {genre}")
                            state, detail = "metadata_mismatch", "Importada con diferencias: " + "; ".join(differences) + ". Revisa su importación desde el panel XML."
                        elif _has_analysis(row, Path(reader.root), Path(record["path"])):
                            state, detail = "ready", "La ruta, clasificación y los datos nativos de forma de onda y beatgrid fueron verificados."
                        else:
                            state, detail = "imported", "Está en Colección con su clasificación. Falta encontrar análisis completo de forma de onda y beatgrid."
                    except Exception as failure:
                        state, detail = "unverifiable", "No se pudieron validar los datos nativos de análisis: " + str(failure)
            result.append({"id": record["id"], "state": state, "detail": detail})
    finally:
        if reader:
            reader.close()
    return result

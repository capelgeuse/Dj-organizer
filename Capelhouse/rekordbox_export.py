"""Create standalone Rekordbox XML, metadata CSV and convenience M3U8 exports.

Format: https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf
Developer instructions: https://rekordbox.com/en/support/developer/
Rekordbox 7.2.14 manual: https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf

Import is manual. Rekordbox's handling of metadata for previously imported tracks
can vary by version and workflow; this export does not update its database.
M3U8 contains paths only, not ratings or colours.
The XML specification does not define a value for clearing a colour. "Sin color"
therefore omits Colour; this is not a guarantee of clearing an existing colour.
"""

import csv
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import tempfile
from urllib.parse import quote
from uuid import uuid4
import xml.etree.ElementTree as ET


COLOURS = {
    "Rosa": "0xFF007F", "Rojo": "0xFF0000", "Naranja": "0xFFA500",
    "Amarillo": "0xFFFF00", "Verde": "0x00FF00", "Aqua": "0x25FDE9",
    "Azul": "0x0000FF", "Morado": "0x660099",
}
FIELDS = ("id", "path", "name", "title", "artist", "genre", "rating",
          "color", "duration", "comments")


def _xml_text(value):
    # XML 1.0 forbids control characters and surrogate code points.
    return "".join(c for c in str(value or "") if c in "\t\n\r" or
                   0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or
                   0x10000 <= ord(c) <= 0x10FFFF)


def _file_uri(path):
    if re.match(r"^[A-Za-z]:[\\/]", path):
        return "file://localhost/" + quote(path.replace("\\", "/"), safe="/:")
    if path.startswith("\\\\") or path.startswith("//"):
        # UNC authorities are standard file URIs, although the spec expects localhost.
        parts = path.replace("\\", "/").lstrip("/").split("/", 1)
        return "file://" + quote(parts[0], safe="") + "/" + quote(parts[1] if len(parts) > 1 else "", safe="/")
    return "file://localhost" + quote(path, safe="/")


def _track_ids(tracks):
    # Deterministic regardless of input order; collisions are resolved within export.
    keys = sorted({(str(t.get("id", "")), str(t["path"])) for t in tracks})
    result, used = {}, set()
    for key in keys:
        salt = 0
        while True:
            digest = hashlib.sha256((key[0] + "\0" + key[1] + "\0" + str(salt)).encode("utf-8")).digest()
            number = int.from_bytes(digest[:4], "big") & 0x7fffffff
            if number and number not in used:
                break
            salt += 1
        used.add(number)
        result[key] = number
    return result


def export_library(tracks: list[dict], output_dir: Path) -> dict:
    """Export existing absolute-path files; return paths, exported count and missing paths.

    Each invocation creates a unique timestamped directory inside output_dir.
    The report path identifies a UTF-8 list of omitted paths, including relative
    or empty paths; the CSV contains only exported tracks. Duplicate id/path
    records are exported once. Invalid metadata raises ValueError before writing.
    """
    return _export_library(tracks, output_dir)


def _export_library(tracks, output_dir, *, for_publish=False):
    valid, missing, seen = [], [], set()
    for track in tracks:
        path = str(track.get("path") or "")
        if not path or not (os.path.isabs(path) or PureWindowsPath(path).is_absolute()) or not Path(path).is_file():
            missing.append(path)
            continue
        key = (str(track.get("id", "")), path)
        if key in seen:
            continue
        seen.add(key)
        rating = track.get("rating", 0)
        if isinstance(rating, bool) or not isinstance(rating, int) or not 0 <= rating <= 5:
            raise ValueError("rating must be an integer from 0 to 5")
        color = track.get("color") or "Sin color"
        if color != "Sin color" and color not in COLOURS:
            raise ValueError(f"unknown color: {color}")
        try:
            duration = float(track.get("duration") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("duration must be a nonnegative finite number") from exc
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("duration must be a nonnegative finite number")
        valid.append(track)
    if for_publish:
        if missing:
            first = repr(missing[0]) if missing[0] else "(ruta vacía)"
            raise ValueError(f"No se pudo publicar: {len(missing)} rutas de audio no disponibles o no válidas. "
                             f"Primera ruta: {first}. Comprueba las rutas y los discos conectados.")
        if not valid:
            raise ValueError("No se pudo publicar: la biblioteca está vacía.")
    elif not valid:
        raise ValueError("No valid existing tracks to export")

    ids = _track_ids(valid)
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name="Capelhouse", Version="1.0", Company="Capelhouse")
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(valid)))
    genres = {}
    for track in valid:
        path = str(track["path"])
        track_id = ids[(str(track.get("id", "")), path)]
        genre = _xml_text(track.get("genre"))
        playlist_genre = genre or "Sin género"
        attrs = {"TrackID": str(track_id), "Name": _xml_text(track.get("title") or track.get("name") or Path(path).stem),
                 "Artist": _xml_text(track.get("artist")), "Genre": genre if for_publish else playlist_genre,
                 "Rating": str(track.get("rating", 0) * 51), "Location": _file_uri(path),
                 "TotalTime": str(int(float(track.get("duration") or 0))),
                 "Comments": _xml_text(track.get("comments"))}
        color = track.get("color") or "Sin color"
        if color in COLOURS:
            attrs["Colour"] = COLOURS[color]
        ET.SubElement(collection, "TRACK", attrs)
        genres.setdefault(playlist_genre, []).append(track_id)
    playlists = ET.SubElement(root, "PLAYLISTS")
    node = ET.SubElement(playlists, "NODE", Type="0", Name="ROOT", Count=str(1 if for_publish else len(genres)))
    if for_publish:
        node = ET.SubElement(node, "NODE", Type="0", Name="CapelHouse", Count=str(len(genres)))
    for genre, track_ids in genres.items():
        playlist = ET.SubElement(node, "NODE", Type="1", Name=genre, KeyType="0", Entries=str(len(track_ids)))
        for track_id in track_ids:
            ET.SubElement(playlist, "TRACK", Key=str(track_id))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    export_dir = Path(tempfile.mkdtemp(prefix=f"rekordbox-export-{timestamp}-", dir=output_dir))
    paths = {"xml": export_dir / "library.xml", "csv": export_dir / "metadata.csv", "m3u": export_dir / "playlist.m3u8",
             "report": export_dir / "missing_files.txt"}
    # Each file is first completed under a private name, then atomically renamed.
    for kind, target in paths.items():
        temporary = export_dir / ("." + uuid4().hex + ".tmp")
        try:
            if kind == "xml":
                ET.ElementTree(root).write(temporary, encoding="utf-8", xml_declaration=True)
            elif kind == "csv":
                with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(valid)
            elif kind == "m3u":
                with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                    stream.write("#EXTM3U\n")
                    for track in valid:
                        stream.write(str(track["path"]) + "\n")
            else:
                with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                    stream.write("Archivos omitidos: ruta vacía, relativa o archivo no encontrado.\n")
                    stream.write(f"Total: {len(missing)}\n\n")
                    for path in missing:
                        # Keep one entry per line even for unusual filenames.
                        display = path.replace("\r", "\\r").replace("\n", "\\n") if path else "(ruta vacía)"
                        stream.write(display + "\n")
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
    return {**paths, "count": len(valid), "missing": missing}


def publish_library(tracks: list[dict], bridge_dir: Path) -> dict:
    """Publish a complete snapshot to CapelHouse.xml and stable companion files.

    The caller supplies the full library; this function does not merge with an
    earlier snapshot. Empty or incomplete input raises before changing any files.
    Each publish archives the snapshot in a timestamped directory in bridge_dir;
    archive is the path to that snapshot's XML.
    Stable files are replaced atomically one at a time, with the XML last so a
    staging or companion replacement error leaves the previous XML intact.
    published_at is the UTC ISO 8601 timestamp of the completed publish.
    """
    bridge_dir = Path(bridge_dir)
    archive = _export_library(tracks, bridge_dir, for_publish=True)
    paths = {"csv": bridge_dir / "CapelHouse.csv",
             "m3u": bridge_dir / "CapelHouse.m3u8",
             "report": bridge_dir / "CapelHouse-missing_files.txt",
             "xml": bridge_dir / "CapelHouse.xml"}
    with tempfile.TemporaryDirectory(prefix=".capelhouse-publish-", dir=bridge_dir) as directory:
        stage = Path(directory)
        for kind, target in paths.items():
            shutil.copyfile(archive[kind], stage / target.name)
        for target in paths.values():
            os.replace(stage / target.name, target)

    return {**paths, "count": archive["count"], "missing": archive["missing"], "archive": archive["xml"],
            "published_at": datetime.now(timezone.utc).isoformat()}

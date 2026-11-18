"""Explicit offline repair of classification on existing Rekordbox tracks."""

from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from threading import Lock
from time import monotonic

from rekordbox_bridge import COLOR_IDS, NativeReader, _normalized, rekordbox_running


_writer_lock = Lock()  # pyrekordbox's update buffer is shared within the process.


def _require_closed():
    if rekordbox_running() is not False:
        raise RuntimeError("Cierra Rekordbox antes de aplicar la clasificación.")


def _requested(tracks):
    requested = {}
    for track in tracks:
        path = str(track.get("path") or "")
        rating = track.get("rating", 0)
        color = track.get("color", "Sin color")
        genre = track.get("genre", "")
        if not Path(path).is_absolute():
            raise ValueError("Cada pista debe tener una ruta absoluta de la biblioteca preparada.")
        if type(rating) is not int or not 0 <= rating <= 5:
            raise ValueError("La valoración debe ser un entero de 0 a 5.")
        if not isinstance(color, str) or color not in COLOR_IDS or not isinstance(genre, str):
            raise ValueError("El género o el color de la pista no es válido.")
        key = _normalized(path)
        values = (rating, COLOR_IDS[color], genre)
        if key in requested and requested[key][1] != values:
            raise ValueError("Hay clasificaciones incompatibles para la misma ruta preparada.")
        requested.setdefault(key, (path, values))
    return requested


def _backup(reader, database):
    from sqlcipher3 import dbapi2
    from pyrekordbox.masterdb.database import BLOB
    from pyrekordbox.utils import deobfuscate

    prefix = database.stem + ".capelhouse-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-")
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=".bak.db", dir=database.parent)
    os.close(fd)
    target = Path(name)
    deadline = monotonic() + 30

    def progress(status, remaining, total):
        if remaining and monotonic() >= deadline:
            raise TimeoutError("No se pudo completar el respaldo de Rekordbox a tiempo.")

    try:
        with closing(dbapi2.connect(str(target), timeout=2)) as destination:
            destination.execute("PRAGMA key='" + deobfuscate(BLOB).replace("'", "''") + "'")
            reader.connection.backup(destination, pages=128, progress=progress, sleep=0.05)
            destination.execute("PRAGMA journal_mode=DELETE").fetchone()
        # Validate the standalone encrypted copy with the same read-only reader.
        with target.open("rb") as stream:
            if len(header := stream.read(16)) != 16 or header == b"SQLite format 3\x00":
                raise RuntimeError("El respaldo de Rekordbox no está cifrado.")
        with closing(NativeReader(target)):
            pass
    except BaseException:
        target.unlink(missing_ok=True)  # Only the incomplete file created by mkstemp.
        raise
    return target


def _open_writer(database):
    from pyrekordbox.masterdb import database as native

    # pyrekordbox 0.5 logs its connection key at DEBUG in the constructor.
    def hide_key(record):
        return record.msg != "Key: %s"

    native.logger.addFilter(hide_key)
    try:
        return native.MasterDatabase(database)
    finally:
        native.logger.removeFilter(hide_key)


def apply_classification(tracks: list[dict], db_path: Path | None = None) -> dict:
    """Update genre, rating and color only; skip unmatched or ambiguous paths.

    Returns the number of changed rows, the encrypted backup path (empty if no
    changes), and the managed paths that had no unique native match. Raises on
    failure without restoring over the live database.
    """
    requested = _requested(tracks)
    result = {"updated": 0, "backup": "", "missing": []}
    with _writer_lock:
        _require_closed()
        if not requested:
            return result
        with closing(NativeReader(db_path)) as reader:
            # Derive the writer/backup source from the actual read-only connection.
            database = Path(reader.connection.execute("PRAGMA database_list").fetchone()[2]).resolve(strict=True)
            db = None
            try:
                db = _open_writer(database)
                # Do not allow pyrekordbox.commit() to reconcile/write playlist XML.
                db.playlist_xml = None
                db.session.connection().exec_driver_sql("PRAGMA busy_timeout=2000")
                db.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                native = {}
                for row in reader.rows():
                    if row["path"] and (key := _normalized(row["path"])) in requested:
                        native.setdefault(key, []).append(row)
                changes = []
                for key, (path, desired) in requested.items():
                    rows = native.get(key, ())
                    if len(rows) != 1:
                        result["missing"].append(path)
                        continue
                    row = rows[0]
                    current = (row["rating"] or 0, str(row["color_id"] or "0"), row["genre"] or "")
                    if current != desired:
                        changes.append((key, row["id"], desired))
                if not changes:
                    db.rollback()
                    return result

                result["backup"] = str(_backup(reader, database))
                _require_closed()
                genre_ids = {"": None}
                for key, track_id, (rating, color_id, genre) in changes:
                    content = db.get_content(ID=track_id)
                    if content is None or _normalized(content.FolderPath) != key:
                        raise RuntimeError("La ruta nativa cambió durante la clasificación.")
                    if genre not in genre_ids:
                        entry = db.get_genre(Name=genre).first()
                        if entry is None:
                            entry = db.add_genre(genre)
                        genre_ids[genre] = entry.ID
                    for field, value in (("Rating", rating), ("ColorID", color_id), ("GenreID", genre_ids[genre])):
                        if getattr(content, field) != value:
                            setattr(content, field, value)
                _require_closed()
                db.commit()  # pyrekordbox updates both row and library USNs.
                result["updated"] = len(changes)
            except BaseException as error:
                if db is not None:
                    db.rollback()
                if not isinstance(error, Exception):
                    raise
                # Do not surface connection details containing secrets. Keep any
                # completed backup for manual recovery; never overwrite the source.
                backup = f" Respaldo conservado: {result['backup']}" if result["backup"] else ""
                raise RuntimeError("No se pudo aplicar la clasificación. Verifica que Rekordbox esté cerrado." + backup) from None
            finally:
                if db is not None:
                    try:
                        db.close()
                    finally:
                        db.engine.dispose()
    return result

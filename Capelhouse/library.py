"""Persistent local music library. Audio is copied, never moved or retagged."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

AUDIO = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.aiff', '.aif'}
DEFAULT_GENRES = ['House', 'Techno', 'Progressive House', 'Melodic House',
                  'Indie Dance', 'Trance', 'Melodic Techno', 'EDM']
COLORS = {'Sin color': None, 'Rosa': (255, 0, 127), 'Rojo': (255, 0, 0),
          'Naranja': (255, 165, 0), 'Amarillo': (255, 255, 0),
          'Verde': (0, 255, 0), 'Aqua': (37, 253, 233),
          'Azul': (0, 0, 255), 'Morado': (102, 0, 153)}
_RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?$', re.I)


def _genre(value):
    if (not isinstance(value, str) or not value or value in ('.', '..') or
            value != value.strip() or value.endswith('.') or
            any(ord(c) < 32 or c in '<>:"/\\|?*' for c in value) or
            _RESERVED.match(value)):
        raise ValueError('Nombre de carpeta de género no válido en Windows')
    return value


def _absolute(value):
    return Path(value).expanduser().resolve()


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _metadata(path):
    result = {'title': path.stem, 'artist': '', 'duration': 0.0, 'comments': ''}
    try:
        import mutagen
        audio = mutagen.File(path, easy=True)
        if audio is not None:
            result['duration'] = float(getattr(audio.info, 'length', 0) or 0)
            for key in ('title', 'artist', 'comments'):
                value = audio.get('comment' if key == 'comments' else key)
                if value:
                    result[key] = str(value[0] if isinstance(value, (list, tuple)) else value)
    except Exception:
        pass
    return result


class Library:
    def __init__(self, config_path: Path):
        self._hash_cache = {}
        requested = _absolute(config_path)
        legacy = requested if requested.name.lower() == 'configuracion_dj.json' else requested.with_name('configuracion_dj.json')
        self.config_path = requested.with_name('library.json') if requested == legacy else requested
        load_path = self.config_path if self.config_path.exists() else legacy
        self._legacy_path = legacy if load_path == legacy and legacy.exists() and legacy != self.config_path else None
        if load_path.exists():
            with load_path.open(encoding='utf-8-sig') as stream:
                self.config = json.load(stream)
            if not isinstance(self.config, dict):
                raise ValueError('La configuración de la biblioteca debe ser un objeto')
        else:
            self.config = {}
        if load_path.exists() and 'tracks' not in self.config and 'revisadas' in self.config:
            self._legacy_path = load_path
        self.input_path = _absolute(self.config['entrada']) if self.config.get('entrada') else None
        self.library_path = _absolute(self.config['biblioteca']) if self.config.get('biblioteca') else None
        self.genres = list(self.config.get('generos', DEFAULT_GENRES))
        self.tracks = copy.deepcopy(self.config.get('tracks', []))
        self.skipped = list(self.config.get('skipped', self.config.get('omitidas', [])))
        if 'tracks' not in self.config:
            for old in self.config.get('revisadas', []):
                destination = old.get('destination')
                if destination and self.library_path:
                    # Legacy paths are stored with Windows separators.
                    target = self.library_path.joinpath(*destination.replace('\\', '/').split('/')).resolve()
                else:
                    target = _absolute(old['source']) if old.get('source') else None
                if target is None:
                    continue
                source = _absolute(old['source']) if old.get('source') else target
                record = {'id': str(uuid.uuid4()), 'path': str(target), 'source': str(source),
                          'name': old.get('name') or target.name, 'genre': old.get('genre', ''),
                          'rating': 0, 'color': 'Sin color'}
                record.update(_metadata(target) if target.is_file() else
                              {'title': target.stem, 'artist': '', 'duration': 0.0, 'comments': ''})
                self.tracks.append(record)

    def save(self):
        data = copy.deepcopy(self.config)
        data.update(entrada=str(self.input_path) if self.input_path else '',
                    biblioteca=str(self.library_path) if self.library_path else '',
                    generos=self.genres, tracks=self.tracks, skipped=self.skipped)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if self._legacy_path is not None:
            backup = self._legacy_path.with_name(self._legacy_path.name + '.bak')
            original_bytes = self._legacy_path.read_bytes()
            for index in range(1000000):
                candidate = backup if index == 0 else backup.with_name(backup.name + f'.{index}')
                try:
                    with candidate.open('xb') as output:
                        try:
                            output.write(original_bytes)
                            output.flush()
                            os.fsync(output.fileno())
                        except BaseException:
                            output.close()
                            candidate.unlink()
                            raise
                    break
                except FileExistsError:
                    if candidate.read_bytes() == original_bytes:
                        break
            else:
                raise FileExistsError('No se pudo crear un nombre para el respaldo de la configuración anterior')
        temp = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.config_path.parent,
                                             prefix='.capelhouse-', suffix='.tmp', delete=False) as stream:
                temp = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.config_path)
        finally:
            if temp and temp.exists():
                temp.unlink()
        self.config = data
        self._legacy_path = None

    def set_paths(self, input_path=None, library_path=None):
        previous = self.input_path, self.library_path
        if input_path is not None:
            self.input_path = _absolute(input_path) if str(input_path) else None
        if library_path is not None:
            self.library_path = _absolute(library_path) if str(library_path) else None
        try:
            self.save()
        except Exception:
            self.input_path, self.library_path = previous
            raise

    def set_genres(self, genres):
        values = [_genre(g) for g in genres]
        if len({g.casefold() for g in values}) != len(values):
            raise ValueError('Hay géneros duplicados')
        previous = self.genres
        self.genres = values
        try:
            self.save()
        except Exception:
            self.genres = previous
            raise

    def _cached_hash(self, path):
        path = _absolute(path)
        stat = path.stat()
        signature = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        cached = self._hash_cache.get(path)
        if cached and cached[0] == signature:
            return cached[1]
        digest = _hash(path)
        after = path.stat()
        if signature == (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            self._hash_cache[path] = (signature, digest)
        else:
            self._hash_cache.pop(path, None)
        return digest

    def scan(self, input_path=None):
        root = _absolute(input_path) if input_path is not None else self.input_path
        if root is None or not root.is_dir():
            return []
        excluded = {str(_absolute(p)).casefold() for t in self.tracks for p in (t.get('source'), t.get('path')) if p}
        excluded.update(str(_absolute(p)).casefold() for p in self.skipped if isinstance(p, str) and p)
        hashes = set()
        for track in self.tracks:
            digest = track.get('hash')
            if not digest:
                for candidate in (track.get('path'), track.get('source')):
                    if candidate:
                        try:
                            digest = self._cached_hash(candidate)
                            break
                        except OSError:
                            continue
            if digest:
                hashes.add(digest)
        result = []
        for path in root.rglob('*'):
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                continue
            if self.library_path:
                if not root.is_relative_to(self.library_path) and resolved.is_relative_to(self.library_path):
                    continue
                if root == self.library_path:
                    relative = resolved.relative_to(root) if resolved.is_relative_to(root) else None
                    if relative and len(relative.parts) > 1 and relative.parts[0].casefold() in {g.casefold() for g in self.genres}:
                        continue
            if path.is_file() and path.suffix.lower() in AUDIO and str(resolved).casefold() not in excluded:
                try:
                    if not hashes or self._cached_hash(resolved) not in hashes:
                        result.append(resolved)
                except OSError:
                    continue
        return sorted(result, key=lambda p: str(p).casefold())

    def _validate(self, genre, rating, color, existing_genre=None):
        _genre(genre)
        if genre not in self.genres and genre != existing_genre:
            raise ValueError('Género desconocido')
        if type(rating) is not int or not 0 <= rating <= 5:
            raise ValueError('La valoración debe ser un número entero de 0 a 5')
        if color not in COLORS:
            raise ValueError('Color desconocido')
        if self.library_path is None:
            raise ValueError('No se ha configurado la carpeta de destino')

    def _copy(self, source, genre):
        folder = self.library_path / genre
        folder.mkdir(parents=True, exist_ok=True)
        if not folder.resolve().is_relative_to(self.library_path.resolve()):
            raise ValueError('La carpeta de género está fuera de la biblioteca')
        for index in range(1000000):
            name = source.name if index == 0 else f'{source.stem} ({index}){source.suffix}'
            target = folder / name
            try:
                with target.open('xb') as output:
                    try:
                        with source.open('rb') as original:
                            shutil.copyfileobj(original, output)
                    except BaseException:
                        output.close()
                        target.unlink()
                        raise
                return target.resolve()
            except FileExistsError:
                continue
        raise FileExistsError('No se pudo crear un nombre de archivo único')

    def prepare(self, source: Path, genre: str, rating: int, color: str):
        self._validate(genre, rating, color)
        source = _absolute(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        if source.suffix.lower() not in AUDIO:
            raise ValueError('Formato de audio no compatible')
        digest = self._cached_hash(source)
        for track in self.tracks:
            candidates = [track.get('path'), track.get('source')]
            if any(p and _absolute(p) == source for p in candidates):
                raise ValueError('La canción ya está preparada')
            known = track.get('hash')
            if not known:
                existing = next((_absolute(p) for p in candidates if p and _absolute(p).is_file()), None)
                known = self._cached_hash(existing) if existing else None
            if known == digest:
                raise ValueError('Esta canción ya existe en la biblioteca')
        metadata = _metadata(source)
        target = self._copy(source, genre)
        record = {'id': str(uuid.uuid4()), 'path': str(target), 'source': str(source),
                  'name': target.name, 'genre': genre, 'rating': rating, 'color': color,
                  'hash': digest, **metadata}
        self.tracks.append(record)
        try:
            self.save()
        except BaseException:
            self.tracks.pop()
            target.unlink()
            raise
        return record

    def update(self, track_id: str, genre: str, rating: int, color: str):
        track = next((t for t in self.tracks if t['id'] == track_id), None)
        if track is None:
            raise KeyError(track_id)
        self._validate(genre, rating, color, existing_genre=track.get('genre'))
        previous = track.copy()
        target = None
        if genre != track['genre']:
            source = _absolute(track['path'])
            if not source.is_file():
                raise FileNotFoundError(source)
            target = self._copy(source, genre)
            track.update(path=str(target), name=target.name)
        track.update(genre=genre, rating=rating, color=color)
        try:
            self.save()
        except BaseException:
            track.clear()
            track.update(previous)
            if target:
                target.unlink()
            raise
        return track

    def skip(self, source):
        path = str(_absolute(source))
        if path not in self.skipped:
            self.skipped.append(path)
            try:
                self.save()
            except Exception:
                self.skipped.pop()
                raise

    def restore_skipped(self):
        previous = self.skipped
        self.skipped = []
        try:
            self.save()
        except Exception:
            self.skipped = previous
            raise

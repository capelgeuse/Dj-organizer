import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import Library
import library


def wav(path, frames=b'\0\0' * 100):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        stream.writeframes(frames)
    return path


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'library.json'
        self.lib = Library(self.config)
        self.src = wav(self.root / 'input' / 'song.wav')
        self.lib.set_paths(self.src.parent, self.root / 'managed')

    def test_prepare_update_persist_and_collision(self):
        collision = wav(self.root / 'managed' / 'House' / 'song.wav', b'\1\0' * 100)
        old = collision.read_bytes()
        record = self.lib.prepare(self.src, 'House', 5, 'Azul')
        self.assertEqual(collision.read_bytes(), old)
        self.assertNotEqual(Path(record['path']), collision)
        self.assertTrue(self.src.exists())
        old_path = Path(record['path'])
        updated = self.lib.update(record['id'], 'Techno', 0, 'Rojo')
        self.assertTrue(old_path.exists())
        self.assertEqual(Path(updated['path']).parent.name, 'Techno')
        loaded = Library(self.config)
        self.assertEqual(loaded.tracks[0]['color'], 'Rojo')
        self.assertEqual(loaded.tracks[0]['rating'], 0)
        self.assertEqual(loaded.scan(), [])

    def test_duplicate_scan_skip_and_missing(self):
        duplicate = wav(self.src.parent / 'duplicate.wav')
        self.lib.skip(duplicate)
        self.assertEqual(self.lib.scan(), [self.src.resolve()])
        self.lib.restore_skipped()
        self.lib.prepare(self.src, 'House', 1, 'Sin color')
        with self.assertRaises(ValueError):
            self.lib.prepare(duplicate, 'House', 2, 'Rosa')
        with self.assertRaises(FileNotFoundError):
            self.lib.prepare(self.root / 'missing.wav', 'House', 0, 'Sin color')
        self.assertEqual(Library(self.root / 'empty' / 'config.json').scan(), [])

    def test_same_input_and_library_excluded(self):
        self.lib.set_paths(self.src.parent, self.src.parent)
        self.assertEqual(self.lib.scan(), [self.src.resolve()])
        record = self.lib.prepare(self.src, 'House', 0, 'Sin color')
        self.assertTrue(Path(record['path']).exists())
        self.assertTrue(self.src.exists())
        self.assertEqual(self.lib.scan(), [])

    def test_duplicate_content_not_pending_and_removed_genre_editable(self):
        self.lib.prepare(self.src, 'House', 0, 'Sin color')
        duplicate = wav(self.src.parent / 'renamed.wav')
        self.assertEqual(self.lib.scan(), [])
        record = self.lib.tracks[0]
        self.lib.set_genres(['Techno'])
        self.lib.update(record['id'], 'House', 3, 'Aqua')
        self.assertEqual(record['rating'], 3)
        self.assertTrue(duplicate.exists())

    def test_scan_caches_hashes_and_invalidates_changed_files(self):
        self.lib.prepare(self.src, 'House', 0, 'Sin color')
        pending = wav(self.src.parent / 'new.wav', b'\2\0' * 100)
        with patch.object(library, '_hash', wraps=library._hash) as hashing:
            self.assertEqual(self.lib.scan(), [pending.resolve()])
            self.assertEqual(self.lib.scan(), [pending.resolve()])
            self.assertEqual(hashing.call_count, 1)
            wav(pending, b'\0\0' * 100)
            self.assertEqual(self.lib.scan(), [])
            self.assertEqual(hashing.call_count, 2)

    def test_same_input_destination_symlink_and_external_file(self):
        external = wav(self.root / 'outside.wav', b'\3\0' * 100)
        link = self.src.parent / 'external.wav'
        alias = self.root / 'alias'
        try:
            link.symlink_to(external)
            alias.symlink_to(self.src.parent, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'Symlink creation unavailable: {error}')
        self.lib.set_paths(alias, self.src.parent)
        self.assertEqual(self.lib.scan(), [self.src.resolve()])
        self.lib.prepare(self.src, 'House', 0, 'Sin color')
        self.assertEqual(self.lib.scan(), [])

    def test_scan_rejects_resolved_file_outside_root(self):
        external = wav(self.root / 'outside.wav', b'\3\0' * 100).resolve()
        link = wav(self.src.parent / 'link.wav', b'\4\0' * 100)
        self.lib.set_paths(self.src.parent, self.src.parent)
        resolve = Path.resolve

        def resolve_link(path, *args, **kwargs):
            if path == link:
                return external
            return resolve(path, *args, **kwargs)

        with patch.object(Path, 'resolve', resolve_link):
            self.assertEqual(self.lib.scan(), [self.src.resolve()])

    def test_invalid_genres_and_rollback(self):
        for name in ('..', 'a/b', 'CON', 'nul.txt', 'name.', 'x:y', 'bad '):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.lib.set_genres([name])
        with patch.object(self.lib, 'save', side_effect=OSError('failed')):
            with self.assertRaises(OSError):
                self.lib.prepare(self.src, 'House', 0, 'Sin color')
        self.assertEqual(self.lib.tracks, [])
        self.assertEqual(list((self.root / 'managed' / 'House').iterdir()), [])

    def test_legacy_migration_preserves_file_and_missing_source(self):
        target = wav(self.root / 'managed' / 'House' / 'old.wav')
        legacy = self.root / 'legacy' / 'configuracion_dj.json'
        legacy.parent.mkdir()
        data = {'biblioteca': str(self.root / 'managed'), 'generos': ['House'],
                'categorias': ['Medio'], 'revisadas': [
                    {'source': str(self.root / 'gone.wav'), 'name': 'old.wav',
                     'destination': 'House\\old.wav', 'genre': 'House', 'category': 'Medio'}]}
        legacy.write_text(json.dumps(data), encoding='utf-8')
        before = legacy.read_bytes()
        migrated = Library(legacy)
        backup = legacy.with_name(legacy.name + '.bak')
        self.assertFalse(backup.exists())
        self.assertFalse(migrated.config_path.exists())
        self.assertEqual(Path(migrated.tracks[0]['path']), target.resolve())
        self.assertEqual(migrated.tracks[0]['rating'], 0)
        self.assertEqual(migrated.tracks[0]['color'], 'Sin color')
        migrated.save()
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(before, legacy.read_bytes())
        self.assertEqual(migrated.config['categorias'], ['Medio'])

    def test_defaults_and_existing_backup_are_preserved(self):
        directory = self.root / 'new'
        directory.mkdir()
        empty = Library(directory / 'configuracion_dj.json')
        self.assertTrue(empty.genres)
        self.assertEqual(empty.scan(), [])
        self.assertEqual(list(directory.iterdir()), [])
        legacy = directory / 'configuracion_dj.json'
        legacy.write_text('{"revisadas": []}', encoding='utf-8')
        backup = directory / 'configuracion_dj.json.bak'
        backup.write_bytes(b'older backup')
        migrated = Library(legacy)
        migrated.save()
        self.assertEqual(backup.read_bytes(), b'older backup')
        self.assertEqual((directory / 'configuracion_dj.json.bak.1').read_bytes(), legacy.read_bytes())


if __name__ == '__main__':
    unittest.main()

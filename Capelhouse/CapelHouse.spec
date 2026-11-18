# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
datas = [
    (str(root / 'logo.png'), '.'),
    (str(root / 'Mr_Dafoe'), 'Mr_Dafoe'),
    (str(root / 'Barlow_Condensed,Mr_Dafoe'), 'Barlow_Condensed,Mr_Dafoe'),
]

a = Analysis(
    [str(root / 'CapelHouse_Qt.py')],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    # The bridge loads the reader/driver at runtime, and SQLAlchemy resolves
    # SQLite dialects by name. Follow normal imports for NumPy and Construct.
    hiddenimports=[
        'pyrekordbox',
        'pyrekordbox.config',
        'sqlalchemy.dialects.sqlite.pysqlite',
        'sqlalchemy.dialects.sqlite.pysqlcipher',
        'sqlcipher3.dbapi2',
        'sqlcipher3._sqlite3',
    ],
    excludes=['librosa', 'pygame', 'matplotlib', 'pandas', 'scipy', 'IPython', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='CapelHouse', console=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    name='CapelHouse',
)

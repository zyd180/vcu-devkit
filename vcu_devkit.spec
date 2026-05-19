# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for VCU DevKit.

Build command:
    pyinstaller vcu_devkit.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Project root
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # QSS themes
        (str(ROOT / 'ui' / 'themes' / '*.qss'), 'ui/themes'),
        # SVG icons
        (str(ROOT / 'ui' / 'icons' / '*.svg'), 'ui/icons'),
        # Jinja2 templates
        (str(ROOT / 'core' / 'templates'), 'core/templates'),
    ],
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'lxml',
        'lxml.etree',
        'cantools',
        'peewee',
        'openpyxl',
        'jinja2',
        'rich',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'tkinter', 'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VCU-DevKit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VCU-DevKit',
)

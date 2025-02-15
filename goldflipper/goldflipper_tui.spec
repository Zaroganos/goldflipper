# -*- mode: python ; coding: utf-8 -*-
import os

# Ensure __file__ is defined
if '__file__' not in globals():
    __file__ = os.path.abspath('goldflipper_tui.spec')

# Set the project root directory one level up from the spec file
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from PyInstaller.utils.hooks import collect_data_files

# Collect non-Python data files from the goldflipper package.
# This will include configuration files, JSON plays, and templates.
datas = []
datas += collect_data_files('goldflipper', includes=['config/*.py', 'plays/*.json', 'tools/PlayTemplate/*'])

a = Analysis(
    ['goldflipper_tui.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'win32timezone',  # Required by pywin32 on Windows
        # Include additional hidden imports if needed
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GoldflipperTUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
) 
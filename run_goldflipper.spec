# -*- mode: python ; coding: utf-8 -*-
import os

project_root = os.path.abspath(".")

a = Analysis(
    ['run_goldflipper.py'],
    pathex=[project_root],  # ensures the project root is on the search path
    binaries=[],
    datas=[
        # Copy the settings.yaml file into the goldflipper/config folder in the bundle
        (os.path.join('goldflipper', 'config', 'settings.yaml'),
         os.path.join('goldflipper', 'config')),
        (
            os.path.join('goldflipper', 'tools'),
            'tools'
        ),
        (
            os.path.join('goldflipper', 'chart'),
            'chart'
        ),
        (
            os.path.join('goldflipper', 'logging'),
            'logging'
        )
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],  # make sure this file is in your project root
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
    name='Goldflipper',
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
    icon='goldflipper.ico',
)

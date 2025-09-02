# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs

# Ensure __file__ is defined for PyInstaller discovery
if '__file__' not in globals():
    __file__ = os.path.abspath('goldflipper_web.spec')

# Project root is two levels up from this spec (goldflipper/goldflipper/*.spec)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Bundle non-Python resources
# - Web application files (app.py, pages, assets)
# - Icon
# - Optionally, a seeded DB located at goldflipper/data/db/goldflipper.db

datas = []

# Include web directory contents
web_root = os.path.join(package_root, "web")
if os.path.isdir(web_root):
    datas.append((os.path.join(web_root, "app.py"), "web"))
    # pages directory
    pages_dir = os.path.join(web_root, "pages")
    if os.path.isdir(pages_dir):
        datas.append((pages_dir, os.path.join("web", "pages")))
    # assets directory
    assets_dir = os.path.join(web_root, "assets")
    if os.path.isdir(assets_dir):
        datas.append((assets_dir, os.path.join("web", "assets")))

# Icon
icon_path = os.path.join(project_root, "goldflipper.ico")
if not os.path.isfile(icon_path):
    icon_path = None

# Optional: seed DB source (copied to user data dir at runtime)
seed_db = os.path.join(package_root, "data", "db", "goldflipper.db")
if os.path.isfile(seed_db):
    datas.append((seed_db, os.path.join("web", "data", "db")))

# Dynamic libraries for duckdb, numpy, pandas
binaries = []
try:
    binaries += collect_dynamic_libs("duckdb")
except Exception:
    pass

# Hidden imports that commonly need pinning for Windows builds
hiddenimports = [
    "win32timezone",
]


a = Analysis(
    [os.path.join(package_root, "web", "entrypoint.py")],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='GoldflipperWeb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

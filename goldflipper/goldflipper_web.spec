# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

# Robust repository root discovery so this spec works from various CWDs/spec paths
CANDIDATE_ROOTS = []
try:
    CANDIDATE_ROOTS.append(Path(__file__).resolve().parent)          # spec dir or relative dir
    CANDIDATE_ROOTS.append(Path(__file__).resolve().parent.parent)   # one level up
except Exception:
    pass
CANDIDATE_ROOTS.append(Path.cwd())
CANDIDATE_ROOTS.append(Path.cwd().parent)

repo_root = None
for root in CANDIDATE_ROOTS:
    if (root / 'goldflipper' / 'web' / 'entrypoint.py').exists():
        repo_root = root
        break

if repo_root is None:
    # Last-resort: search up to 3 parents for the marker
    probe = Path.cwd()
    for _ in range(3):
        if (probe / 'goldflipper' / 'web' / 'entrypoint.py').exists():
            repo_root = probe
            break
        probe = probe.parent

if repo_root is None:
    raise FileNotFoundError('Unable to locate repository root containing goldflipper/web/entrypoint.py')

package_root = repo_root / 'goldflipper'
web_root = package_root / 'web'

# Bundle non-Python resources
# - Web application files (app.py, pages, assets, utils)
# - Icon and splash
# - Seeded DB from project data directory (top-level), copied to user data dir on first run

datas = []

# Include web directory contents
if web_root.is_dir():
    datas.append((str(web_root / 'app.py'), 'web'))
    pages_dir = web_root / 'pages'
    if pages_dir.is_dir():
        datas.append((str(pages_dir), 'web/pages'))
    assets_dir = web_root / 'assets'
    if assets_dir.is_dir():
        datas.append((str(assets_dir), 'web/assets'))
    utils_dir = web_root / 'utils'
    if utils_dir.is_dir():
        datas.append((str(utils_dir), 'web/utils'))

# Icon and splash
icon_path = repo_root / 'goldflipper.ico'
if not icon_path.is_file():
    icon_path = None
splash_path = web_root / 'assets' / 'splash.png'
if splash_path.is_file():
    # Distribute splash asset; enable splash with this image
    datas.append((str(splash_path), 'web/assets'))

# Seed DB source from top-level project data directory
top_level_seed_db = repo_root / 'goldflipper' / 'data' / 'db' / 'goldflipper.db'
if top_level_seed_db.is_file():
    datas.append((str(top_level_seed_db), 'web/data/db'))

# Also consider a seed DB inside the package layout (if present)
package_seed_db = package_root / 'data' / 'db' / 'goldflipper.db'
if package_seed_db.is_file():
    datas.append((str(package_seed_db), 'web/data/db'))

# Streamlit package data and metadata (required for importlib.metadata)
datas += collect_data_files('streamlit')
datas += copy_metadata('streamlit')

# Alpaca package metadata (distribution is alpaca-py)
datas += copy_metadata('alpaca-py')

# Bundle the entire goldflipper source tree as data to ensure availability at runtime
source_pkg_dir = package_root / 'goldflipper'
if source_pkg_dir.is_dir():
    datas.append((str(source_pkg_dir), 'goldflipper'))

# Hidden imports: include Streamlit runtime and specific modules required by entrypoint and pages
hiddenimports = [
    'win32timezone',
    'streamlit.web.cli',
    'streamlit.web.server',
    'streamlit.runtime.scriptrunner.magic_funcs',
    'zoneinfo',
    'yfinance',
]

# Collect submodules for key dynamic packages
for pkg in ['streamlit.runtime', 'alpaca']:
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

entry_script = web_root / 'entrypoint.py'
if not entry_script.is_file():
    raise FileNotFoundError(f'Entrypoint not found at {entry_script}')


a = Analysis(
    [str(entry_script)],
    pathex=[str(repo_root)],
    binaries=[],
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

# Configure splash screen if available (Windows run-time splash)
splash_arg = str(splash_path) if splash_path.is_file() else None

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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path else None,
    splash=splash_arg,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GoldflipperWeb',
)

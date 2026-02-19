"""
Fast Nuitka dev build script for the Goldflipper Windows executable.
Optimized for iteration speed, NOT final distribution.

Differences from production build (build_nuitka.py):
- No LTO (--lto=no) - skips slow Link Time Optimization
- No compression (--onefile-no-compression) - skips slow zstd compression
- Uses all CPU cores (--jobs=N)
- Still produces single-file .exe with full functionality

Speed gains:
- LTO removal: ~30-50% faster
- No compression: ~20-30% faster (larger exe, but faster to build)
- Combined: Can cut build time by 50%+ on typical setups

Run with: uv run python scripts/build_nuitka_dev.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT_CANDIDATES = [
    PROJECT_ROOT / "src" / "goldflipper" / "launcher.py",
    PROJECT_ROOT / "goldflipper" / "launcher.py",
    PROJECT_ROOT / "src" / "goldflipper" / "run.py",
    PROJECT_ROOT / "goldflipper" / "run.py",
]

# ============================================================================
# PACKAGES TO COMPILE (use --include-package)
# These are Python modules that need to be compiled into the exe, not just
# copied as data files. CRITICAL for dynamic imports via importlib.
# ============================================================================
PACKAGES_TO_COMPILE = [
    "goldflipper",  # Root package (core.py, run.py, alpaca_client.py, etc.)
    "goldflipper.config",  # Configuration module (CRITICAL for settings loading)
    "goldflipper.data",  # Data modules (greeks, indicators, market)
    "goldflipper.tools",  # All tool modules (GUI, CLI tools)
    "goldflipper.chart",  # Chart viewer module
    "goldflipper.trade_logging",  # Trade logger module
    "goldflipper.strategy",  # Strategy modules (runners, shared, playbooks loader)
    "goldflipper.utils",  # Utility modules
    "goldflipper.watchdog",  # Watchdog module
]

# ============================================================================
# DATA FILES (use --include-data-dir / --include-data-files)
# These are non-Python files: YAML configs, JSON templates, CSV reference data.
# ============================================================================
DATA_MAPPINGS = [
    # Config directory (settings.yaml excluded below)
    (PROJECT_ROOT / "goldflipper" / "config", "goldflipper/config"),
    # Reference data (CSV files)
    (PROJECT_ROOT / "goldflipper" / "reference", "goldflipper/reference"),
    # Tool templates (JSON play templates)
    (PROJECT_ROOT / "goldflipper" / "tools" / "templates", "goldflipper/tools/templates"),
    # Strategy playbooks (YAML configs for momentum, sell_puts, etc.)
    (PROJECT_ROOT / "goldflipper" / "strategy" / "playbooks", "goldflipper/strategy/playbooks"),
    # Application icon
    (PROJECT_ROOT / "goldflipper.ico", "goldflipper.ico"),
]

# ============================================================================
# DATA FILES TO EXCLUDE (use --noinclude-data-files)
# These patterns exclude gitignored or user-specific files from bundling.
# ============================================================================
DATA_EXCLUDE_PATTERNS = [
    "**/settings.yaml",  # User-specific config (created on first run)
    "**/*.log",  # Log files
    "**/*.bak",  # Backup files
    "**/*.old",  # Old leftover files
    "**/*.tmp",  # Temp files
    "**/__pycache__/**",  # Python cache
]

OUTPUT_DIR = PROJECT_ROOT / "dist"
APP_NAME = "goldflipper"


def build() -> None:
    """Build a standalone executable via Nuitka (fast dev mode)."""
    entry_point = next(
        (path for path in ENTRY_POINT_CANDIDATES if path.exists()),
        None,
    )
    if entry_point is None:
        joined = "\n - ".join(str(p) for p in ENTRY_POINT_CANDIDATES)
        raise FileNotFoundError(f"None of the entry point candidates exist:\n - {joined}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build --include-package flags for modules that need to be compiled
    # These are dynamically imported via importlib and won't be auto-discovered
    package_flags: list[str] = []
    for package in PACKAGES_TO_COMPILE:
        package_flags.append(f"--include-package={package}")
        print(f"[INFO] Including package for compilation: {package}")

    # Build --include-data-dir/files flags for actual data files (YAML, JSON, CSV)
    data_flags: list[str] = []
    for src, dest in DATA_MAPPINGS:
        if not src.exists():
            print(f"[WARN] Data path missing, skipping: {src}")
            continue
        flag = f"--include-data-dir={src}={dest}" if src.is_dir() else f"--include-data-files={src}={dest}"
        data_flags.append(flag)
        print(f"[INFO] Including data: {src} -> {dest}")

    # Get CPU count for parallel compilation
    cpu_count = 16
    # os.cpu_count() or 4
    # replace `16` with above line to restore typical function

    # Path to application icon
    icon_path = PROJECT_ROOT / "goldflipper.ico"

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}_dev",
        "--windows-console-mode=force",  # Force console creation for Textual TUI
        "--enable-plugin=tk-inter",
        "--follow-imports",
        "--prefer-source-code",
        # ======================================================================
        # DEV BUILD SPEED OPTIMIZATIONS
        # ======================================================================
        "--lto=no",  # Skip Link Time Optimization (big speedup)
        "--onefile-no-compression",  # Skip zstd compression (bigger exe, faster build)
        f"--jobs={cpu_count}",  # Use all CPU cores
        "--assume-yes-for-downloads",  # No interactive prompts
        # CRITICAL: Allow the exe to launch itself with custom arguments (--tool)
        "--no-deployment-flag=self-execution",
    ]

    # Windows icon for the executable
    if icon_path.exists():
        cmd.append(f"--windows-icon-from-ico={icon_path}")

    # Add exclusion patterns for gitignored/user-specific files
    for pattern in DATA_EXCLUDE_PATTERNS:
        cmd.append(f"--noinclude-data-files={pattern}")
        print(f"[INFO] Excluding data pattern: {pattern}")

    # Add package compilation flags BEFORE data flags
    cmd.extend(package_flags)
    cmd.extend(data_flags)
    cmd.append(str(entry_point))

    print()
    print("=" * 70)
    print("[DEV BUILD] Building Goldflipper with Nuitka (FAST MODE)")
    print("=" * 70)
    print(f"Entry point : {entry_point}")
    print(f"Output dir  : {OUTPUT_DIR}")
    print(f"CPU cores   : {cpu_count}")
    print()
    print("Speed optimizations enabled:")
    print("  - No LTO (--lto=no)")
    print("  - No compression (--onefile-no-compression)")
    print("  - Parallel compilation (--jobs)")
    print()
    print("Command line:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        exe_path = OUTPUT_DIR / f"{APP_NAME}_dev.exe"
        print("\n" + "=" * 70)
        print("[DEV BUILD] Build successful!")
        print("=" * 70)
        print(f"Executable : {exe_path}")
        print(f"Test with  : .\\dist\\{APP_NAME}_dev.exe --help")
        print()
        print("NOTE: This build is larger than production (no compression).")
        print("      For optimized release: uv run python scripts/build_nuitka.py")
        print("=" * 70)
    else:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    build()

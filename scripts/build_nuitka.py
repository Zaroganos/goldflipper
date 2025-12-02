"""
Nuitka build script for the Goldflipper Windows executable.
Run with: uv run python scripts/build_nuitka.py
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
DATA_MAPPINGS = [
    # Core config and reference data
    (PROJECT_ROOT / "goldflipper" / "config", "goldflipper/config"),
    (PROJECT_ROOT / "goldflipper" / "reference", "goldflipper/reference"),
    
    # Tools directory - all tool scripts and templates
    (PROJECT_ROOT / "goldflipper" / "tools", "goldflipper/tools"),
    
    # Chart viewer module
    (PROJECT_ROOT / "goldflipper" / "chart", "goldflipper/chart"),
    
    # Trade logging module  
    (PROJECT_ROOT / "goldflipper" / "trade_logging", "goldflipper/trade_logging"),
    
    # Strategy playbooks (YAML configs for momentum, sell_puts, etc.)
    (PROJECT_ROOT / "goldflipper" / "strategy" / "playbooks", "goldflipper/strategy/playbooks"),
    
    # Application icon
    (PROJECT_ROOT / "goldflipper.ico", "goldflipper.ico"),
]
OUTPUT_DIR = PROJECT_ROOT / "dist"
APP_NAME = "goldflipper"


def build() -> None:
    """Build a standalone executable via Nuitka."""
    entry_point = next(
        (path for path in ENTRY_POINT_CANDIDATES if path.exists()),
        None,
    )
    if entry_point is None:
        joined = "\n - ".join(str(p) for p in ENTRY_POINT_CANDIDATES)
        raise FileNotFoundError(
            "None of the entry point candidates exist:\n"
            f" - {joined}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data_flags: list[str] = []
    for src, dest in DATA_MAPPINGS:
        if not src.exists():
            print(f"[WARN] Data path missing, skipping: {src}")
            continue
        flag = (
            f"--include-data-dir={src}={dest}"
            if src.is_dir()
            else f"--include-data-files={src}={dest}"
        )
        data_flags.append(flag)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}",
        "--windows-console-mode=attach",
        "--lto=yes",
        "--enable-plugin=tk-inter",
        # Modern Nuitka handles pywin32 automatically; no extra plugin flag
        "--follow-imports",
        "--prefer-source-code",
    ]
    cmd.extend(data_flags)
    cmd.append(str(entry_point))

    print(f"Building {APP_NAME} with Nuitka...")
    print(f"Entry point : {entry_point}")
    print(f"Output dir  : {OUTPUT_DIR}")
    print("Command line:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("Build successful!")
        print("Executable:", OUTPUT_DIR / f"{APP_NAME}.exe")
        print(f"Test with: .\\dist\\{APP_NAME}.exe --help")
        print("=" * 60)
    else:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    build()


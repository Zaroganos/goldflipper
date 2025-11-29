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
    PROJECT_ROOT / "src" / "goldflipper" / "run.py",
    PROJECT_ROOT / "goldflipper" / "run.py",
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

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}",
        "--windows-console-mode=attach",
        "--enable-console",
        "--lto=yes",
        "--enable-plugin=anti-bloat",
        "--enable-plugin=tk-inter",
        # Modern Nuitka handles pywin32 automatically; no extra plugin flag
        "--follow-imports",
        "--prefer-source-code",
        # Data directories (uncomment / duplicate as mappings are finalized)
        # "--include-data-dir=src/goldflipper/config=goldflipper/config",
        # "--include-data-dir=src/goldflipper/reference=goldflipper/reference",
        # "--include-data-files=src/goldflipper/tools/play-template.json="
        # "goldflipper/tools/play-template.json",
        str(entry_point),
    ]

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


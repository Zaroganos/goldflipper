"""
Nuitka build script for the Goldflipper Windows executable.
Run with: uv run python scripts/build_nuitka.py
         uv run python scripts/build_nuitka.py --debug   (verbose + persistent extraction)

IMPORTANT: Python modules must be included with --include-package (compiled).
           Data files (YAML, JSON, CSV, templates) use --include-data-dir/files.

           Using --include-data-dir for .py files makes them DATA, not executable code!
"""

from __future__ import annotations

import argparse
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
# copied as data files. Critical for dynamic imports via importlib.
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


def build(debug: bool = False, persistent_extract: bool = False) -> None:
    """
    Build a standalone executable via Nuitka.

    Args:
        debug: Enable verbose output and compilation report
        persistent_extract: Use a persistent extraction directory instead of temp
    """
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

    # Path to application icon
    icon_path = PROJECT_ROOT / "goldflipper.ico"

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}",
        "--windows-console-mode=force",  # Force console creation for Textual TUI
        "--lto=yes",
        "--enable-plugin=tk-inter",
        # Modern Nuitka handles pywin32 automatically; no extra plugin flag
        "--follow-imports",
        "--prefer-source-code",
        # CRITICAL: Allow the exe to launch itself with custom arguments (--tool)
        # Without this, Nuitka's fork-bomb protection may block self-execution
        "--no-deployment-flag=self-execution",
    ]

    # Windows icon for the executable
    if icon_path.exists():
        cmd.append(f"--windows-icon-from-ico={icon_path}")
        print(f"[INFO] Using icon: {icon_path}")
    else:
        print(f"[WARN] Icon not found: {icon_path}")

    # Debug mode: add verbose output and compilation report
    if debug:
        cmd.extend(
            [
                "--verbose",
                "--show-modules",
                f"--report={OUTPUT_DIR / 'compilation-report.xml'}",
            ]
        )
        print("[DEBUG] Verbose mode enabled with compilation report")

    # Persistent extraction directory: extract next to exe instead of temp
    # This helps with:
    # - Antivirus false positives (temp dirs are suspicious)
    # - Debugging (easier to find extracted files)
    # - Faster subsequent launches (no re-extraction)
    if persistent_extract:
        # Extract to .goldflipper_runtime folder next to the exe
        cmd.append("--onefile-tempdir-spec={CACHE_DIR}/goldflipper_runtime")
        print("[INFO] Using persistent extraction directory: %LOCALAPPDATA%/goldflipper_runtime")

    # Add exclusion patterns for gitignored/user-specific files
    for pattern in DATA_EXCLUDE_PATTERNS:
        cmd.append(f"--noinclude-data-files={pattern}")
        print(f"[INFO] Excluding data pattern: {pattern}")

    # Add package compilation flags BEFORE data flags
    cmd.extend(package_flags)
    cmd.extend(data_flags)
    cmd.append(str(entry_point))

    print(f"\nBuilding {APP_NAME} with Nuitka...")
    print(f"Entry point : {entry_point}")
    print(f"Output dir  : {OUTPUT_DIR}")
    print(f"Debug mode  : {debug}")
    print(f"Persistent  : {persistent_extract}")
    print("\nCommand line:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        exe_path = OUTPUT_DIR / f"{APP_NAME}.exe"
        print("\n" + "=" * 60)
        print("Build successful!")
        print("Executable:", exe_path)
        print(f"Test with: .\\dist\\{APP_NAME}.exe --help")
        if debug:
            print(f"Report: {OUTPUT_DIR / 'compilation-report.xml'}")
        print("=" * 60)

        # Code signing (Development Mode)
        sign_executable(exe_path)
    else:
        raise SystemExit(result.returncode)


def find_signtool() -> Path | None:
    """
    Locate signtool.exe in standard Windows Kits directories.
    Prioritizes the latest version and x64 architecture.
    """
    import shutil

    # Check PATH first
    if signtool_path := shutil.which("signtool"):
        return Path(signtool_path)

    # Standard location
    kits_root = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if not kits_root.exists():
        return None

    # Find all versions (10.0.xxxxx.0)
    versions = []
    for entry in kits_root.iterdir():
        if entry.is_dir() and entry.name.startswith("10."):
            versions.append(entry)

    # Sort by version number (descending)
    versions.sort(key=lambda p: [int(x) for x in p.name.split(".")], reverse=True)

    for version_dir in versions:
        # Check x64 first, then x86
        for arch in ["x64", "x86", "arm64"]:
            candidate = version_dir / arch / "signtool.exe"
            if candidate.exists():
                return candidate

    return None


def sign_executable(exe_path: Path) -> bool:
    """
    Sign the executable with a self-signed development certificate.
    """
    print("\n" + "-" * 60)
    print("  CODE SIGNING (Development Mode)")
    print("-" * 60)

    signtool = find_signtool()
    if not signtool:
        print("[WARN] signtool.exe not found. Skipping code signing.")
        print("       Install Windows SDK to enable signing.")
        return False

    print(f"[INFO] Found signtool: {signtool}")

    # Get or create certificate via PowerShell script
    ps_script = PROJECT_ROOT / "scripts" / "setup_dev_cert.ps1"
    if not ps_script.exists():
        print(f"[ERROR] Certificate setup script missing: {ps_script}")
        return False

    try:
        # Run PS script to get thumbprint
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)], capture_output=True, text=True, check=True
        )

        # Parse output for thumbprint
        lines = result.stdout.strip().splitlines()
        thumbprint = None
        for line in lines:
            if "Certificate found:" in line:
                thumbprint = line.split(":")[-1].strip()
                break

        if not thumbprint:
            print("[WARN] Could not retrieve certificate thumbprint.")
            return False

        print(f"[INFO] Using certificate: {thumbprint}")

        # Sign the executable
        # /fd SHA256 is required for modern Windows
        # /t is for timestamping (crucial for valid signatures after cert expiry)
        cmd = [str(signtool), "sign", "/sha1", thumbprint, "/fd", "SHA256", "/t", "http://timestamp.digicert.com", str(exe_path)]

        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[SUCCESS] Signed: {exe_path.name}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Signing failed: {e}")
        if e.stderr:
            print(f"       {e.stderr.strip()}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error during signing: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Build Goldflipper with Nuitka")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose output, show modules, and generate compilation report",
    )
    parser.add_argument(
        "--persistent-extract",
        action="store_true",
        help="Use persistent extraction directory instead of temp (helps with antivirus)",
    )
    args = parser.parse_args()

    build(debug=args.debug, persistent_extract=args.persistent_extract)


if __name__ == "__main__":
    main()

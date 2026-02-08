"""
MSI installer build script for Goldflipper.

Wraps the Nuitka-compiled executable into a proper Windows Installer (.msi)
package using the WiX Toolset v4+.

Usage:
    uv run python scripts/build_msi.py
    uv run python scripts/build_msi.py --skip-nuitka      # skip Nuitka build step
    uv run python scripts/build_msi.py --arch x64          # target architecture

Prerequisites:
    1. .NET 6+ SDK          → https://dotnet.microsoft.com/download
    2. WiX v4+ .NET tool    → dotnet tool install --global wix
    3. WiX UI extension     → wix extension add WixToolset.UI.wixext
    4. Nuitka build done    → uv run python scripts/build_nuitka.py
       (or pass --skip-nuitka if dist/goldflipper.exe already exists)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WXS_SOURCE = PROJECT_ROOT / "installer" / "goldflipper.wxs"
DIST_DIR = PROJECT_ROOT / "dist"
EXE_PATH = DIST_DIR / "goldflipper.exe"
ICON_PATH = PROJECT_ROOT / "goldflipper.ico"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_version() -> str:
    """
    Read the project version from pyproject.toml and normalise it for MSI.

    MSI requires a version in X.Y.Z or X.Y.Z.W format (numeric only).
    Pre-release suffixes like '-beta' are stripped.
    """
    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError("Could not find 'version' in pyproject.toml")

    raw = match.group(1)
    # Strip pre-release / build metadata (e.g. "0.2.3-beta" → "0.2.3")
    numeric = re.match(r"(\d+\.\d+\.\d+(?:\.\d+)?)", raw)
    if not numeric:
        raise ValueError(f"Version '{raw}' does not start with a numeric X.Y.Z pattern")

    version = numeric.group(1)
    if raw != version:
        print(f"[INFO] Stripped non-numeric suffix: '{raw}' → '{version}'")
    return version


def _find_wix() -> str | None:
    """
    Locate the wix CLI executable.

    Checks PATH first, then the default .NET global tools directory
    (%USERPROFILE%/.dotnet/tools) which may not be in PATH.
    """
    # 1. Check PATH
    found = shutil.which("wix")
    if found:
        return found

    # 2. Check default .NET global tools directory (Windows)
    dotnet_tools = Path(os.path.expanduser("~")) / ".dotnet" / "tools"
    for name in ("wix.exe", "wix"):
        candidate = dotnet_tools / name
        if candidate.is_file():
            return str(candidate)

    return None


def _check_dotnet() -> bool:
    """Return True if the dotnet CLI is available."""
    return shutil.which("dotnet") is not None


def _check_wix(wix_path: str | None) -> bool:
    """Return True if the wix CLI is available at the given path."""
    if wix_path is None:
        return False
    try:
        result = subprocess.run(
            [wix_path, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_wix_ui_extension(wix_path: str) -> bool:
    """Return True if WixToolset.UI.wixext is installed."""
    try:
        result = subprocess.run(
            [wix_path, "extension", "list"],
            capture_output=True, text=True, timeout=10,
        )
        return "WixToolset.UI.wixext" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _print_prereq_help() -> None:
    """Print setup instructions for missing prerequisites."""
    print()
    print("=" * 65)
    print("  MSI BUILD PREREQUISITES")
    print("=" * 65)
    print()
    print("  1. Install .NET 6+ SDK:")
    print("     https://dotnet.microsoft.com/download")
    print()
    print("  2. Install WiX Toolset v4+ as a .NET global tool:")
    print("     dotnet tool install --global wix")
    print()
    print("  3. Add the WiX UI extension (install wizard dialogs):")
    print("     wix extension add WixToolset.UI.wixext")
    print()
    print("  4. Build the Nuitka executable first:")
    print("     uv run python scripts/build_nuitka.py")
    print()
    print("=" * 65)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_msi(
    arch: str = "x64",
    skip_nuitka: bool = False,
    output: str | None = None,
) -> None:
    """
    Build the MSI installer package.

    Args:
        arch: Target architecture (x86 | x64 | arm64). Default: x64.
        skip_nuitka: If True, assume dist/goldflipper.exe already exists.
        output: Override output path for the .msi file.
    """
    print("=" * 60)
    print("  Goldflipper MSI Installer Build")
    print("=" * 60)
    print()

    # ------------------------------------------------------------------
    # 1. Read version
    # ------------------------------------------------------------------
    version = _read_version()
    print(f"[INFO] Product version: {version}")

    # ------------------------------------------------------------------
    # 2. Check prerequisites
    # ------------------------------------------------------------------
    missing = []

    if not _check_dotnet():
        missing.append(".NET SDK (dotnet CLI)")

    wix_path = _find_wix()
    if not _check_wix(wix_path):
        missing.append("WiX Toolset (wix CLI)")
    else:
        print(f"[INFO] WiX CLI: {wix_path}")

    if missing:
        print()
        for item in missing:
            print(f"[ERROR] Missing prerequisite: {item}")
        _print_prereq_help()
        raise SystemExit(1)

    # Check WiX UI extension (non-fatal warning; build may still work
    # if user added it at a different scope)
    if not _check_wix_ui_extension(wix_path):  # type: ignore[arg-type]  # guarded by missing check above
        print("[WARN] WixToolset.UI.wixext not found in global extension list.")
        print("[WARN] If the build fails, run: wix extension add WixToolset.UI.wixext")
        print()

    # ------------------------------------------------------------------
    # 3. Ensure Nuitka exe exists
    # ------------------------------------------------------------------
    if not skip_nuitka and not EXE_PATH.exists():
        print("[INFO] dist/goldflipper.exe not found. Running Nuitka build first...")
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "build_nuitka.py")],
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            print("[ERROR] Nuitka build failed. Cannot create MSI.")
            raise SystemExit(result.returncode)

    if not EXE_PATH.exists():
        print(f"[ERROR] Executable not found: {EXE_PATH}")
        print("[ERROR] Run 'uv run python scripts/build_nuitka.py' first,")
        print("        or pass --skip-nuitka if the exe is in a different location.")
        raise SystemExit(1)

    print(f"[INFO] Source executable: {EXE_PATH}")
    print(f"[INFO] Executable size: {EXE_PATH.stat().st_size / (1024*1024):.1f} MB")

    # ------------------------------------------------------------------
    # 4. Verify WiX source and supporting files
    # ------------------------------------------------------------------
    if not WXS_SOURCE.exists():
        print(f"[ERROR] WiX source file not found: {WXS_SOURCE}")
        raise SystemExit(1)

    license_rtf = PROJECT_ROOT / "installer" / "License.rtf"
    if not license_rtf.exists():
        print(f"[WARN] License.rtf not found at {license_rtf}")
        print("[WARN] The install wizard license dialog may fail.")

    if not ICON_PATH.exists():
        print(f"[WARN] Application icon not found: {ICON_PATH}")

    # ------------------------------------------------------------------
    # 5. Build MSI
    # ------------------------------------------------------------------
    if output:
        msi_path = Path(output)
    else:
        msi_path = DIST_DIR / f"goldflipper-{version}-{arch}.msi"

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        wix_path, "build",
        "-arch", arch,
        "-ext", "WixToolset.UI.wixext",
        "-d", f"ProductVersion={version}",
        "-d", f"ProjectDir={PROJECT_ROOT}",
        "-d", f"DistDir={DIST_DIR}",
        "-o", str(msi_path),
        str(WXS_SOURCE),
    ]

    print()
    print(f"[INFO] Target architecture: {arch}")
    print(f"[INFO] Output: {msi_path}")
    print()
    print("Command:")
    print("  " + " ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode == 0:
        size_mb = msi_path.stat().st_size / (1024 * 1024)
        print()
        print("=" * 60)
        print("  MSI BUILD SUCCESSFUL")
        print("=" * 60)
        print(f"  Installer : {msi_path}")
        print(f"  Size      : {size_mb:.1f} MB")
        print(f"  Version   : {version}")
        print(f"  Arch      : {arch}")
        print()
        print("  To install (GUI):")
        print(f"    msiexec /i \"{msi_path}\"")
        print()
        print("  To install silently:")
        print(f"    msiexec /i \"{msi_path}\" /qn")
        print()
        print("  To uninstall silently:")
        print(f"    msiexec /x \"{msi_path}\" /qn")
        print("=" * 60)
    else:
        print()
        print("[ERROR] MSI build failed!")
        print("[ERROR] Check the output above for details.")
        print()
        print("Common fixes:")
        print("  - Install WiX UI extension: wix extension add WixToolset.UI.wixext")
        print("  - Ensure .NET 6+ SDK is installed")
        print("  - Verify dist/goldflipper.exe exists")
        raise SystemExit(result.returncode)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Goldflipper MSI installer (requires WiX Toolset v4+)",
    )
    parser.add_argument(
        "--arch",
        choices=["x86", "x64", "arm64"],
        default="x64",
        help="Target architecture (default: x64)",
    )
    parser.add_argument(
        "--skip-nuitka",
        action="store_true",
        help="Skip the Nuitka build step (assumes dist/goldflipper.exe exists)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Override output path for the .msi file",
    )
    args = parser.parse_args()

    build_msi(
        arch=args.arch,
        skip_nuitka=args.skip_nuitka,
        output=args.output,
    )


if __name__ == "__main__":
    main()

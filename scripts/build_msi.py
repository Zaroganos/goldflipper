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
    3. WiX extensions:
       - wix extension add WixToolset.UI.wixext
       - wix extension add WixToolset.Util.wixext
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

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WXS_SOURCE = PROJECT_ROOT / "installer" / "goldflipper.wxs"
DIST_DIR = PROJECT_ROOT / "dist"
EXE_PATH = DIST_DIR / "goldflipper.exe"
ICON_PATH = PROJECT_ROOT / "goldflipper.ico"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

BANNER_PATH = PROJECT_ROOT / "installer" / "banner.bmp"
DIALOG_PATH = PROJECT_ROOT / "installer" / "dialog.bmp"
REQUIRED_WIX_EXTENSIONS = (
    "WixToolset.UI.wixext",
    "WixToolset.Util.wixext",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_gradient(width: int, height: int, start_color: tuple, end_color: tuple) -> Image.Image:
    """Generate a vertical gradient image."""
    base = Image.new("RGB", (width, height), start_color)
    Image.new("RGB", (width, height), start_color)
    bottom = Image.new("RGB", (width, height), end_color)
    mask = Image.new("L", (width, height))
    mask_data = []
    for y in range(height):
        mask_data.extend([int(255 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(bottom, (0, 0), mask)
    return base


def _generate_installer_images() -> None:
    """Generate installer banner and dialog bitmaps if missing."""
    if not PIL_AVAILABLE:
        print("[WARN] Pillow not installed. Skipping installer image generation.")
        return

    if BANNER_PATH.exists() and DIALOG_PATH.exists():
        return

    print("[INFO] Generating installer images...")

    # Goldflipper Brand Colors (Dark Blue/Gold theme)
    # Dark Blue: #001f3f (0, 31, 63) -> #001122 (0, 17, 34)
    start_color = (0, 31, 63)
    end_color = (0, 10, 20)
    text_color = (255, 215, 0)  # Gold

    # 1. Top Banner (493 x 58)
    if not BANNER_PATH.exists():
        banner = _generate_gradient(493, 58, start_color, end_color)
        draw = ImageDraw.Draw(banner)
        # Simple text for now
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except OSError:
            font = None

        text = "Goldflipper Setup"
        draw.text((20, 15), text, fill=text_color, font=font)
        banner.save(BANNER_PATH)
        print(f"[INFO] Created {BANNER_PATH}")

    # 2. Dialog Background (493 x 312) - Left side is usually white in WixUI_InstallDir
    # But WixUIDialogBmp covers the left panel of Welcome/Finish dialogs
    if not DIALOG_PATH.exists():
        dialog = _generate_gradient(493, 312, start_color, end_color)
        draw = ImageDraw.Draw(dialog)

        # Draw some "tech" lines or simple decoration
        for i in range(0, 493, 20):
            draw.line([(i, 0), (0, i)], fill=(0, 40, 80), width=1)

        try:
            font_large = ImageFont.truetype("arial.ttf", 36)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except OSError:
            font_large = None
            font_small = None

        draw.text((30, 130), "Goldflipper", fill=text_color, font=font_large)
        draw.text((30, 180), "Multi-Strategy Options Trading", fill=(200, 200, 200), font=font_small)

        dialog.save(DIALOG_PATH)
        print(f"[INFO] Created {DIALOG_PATH}")


def _find_signtool() -> Path | None:
    """Locate signtool.exe (duplicated logic from build_nuitka.py)."""
    if shutil.which("signtool"):
        return Path(shutil.which("signtool"))

    kits_root = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if not kits_root.exists():
        return None

    versions = [e for e in kits_root.iterdir() if e.is_dir() and e.name.startswith("10.")]
    versions.sort(key=lambda p: [int(x) for x in p.name.split(".")], reverse=True)

    for v in versions:
        for arch in ["x64", "x86"]:
            candidate = v / arch / "signtool.exe"
            if candidate.exists():
                return candidate
    return None


def _sign_msi(msi_path: Path) -> None:
    """Sign the generated MSI package."""
    print("\n" + "-" * 60)
    print("  MSI SIGNING")
    print("-" * 60)

    signtool = _find_signtool()
    if not signtool:
        print("[WARN] signtool.exe not found. Skipping MSI signing.")
        return

    ps_script = PROJECT_ROOT / "scripts" / "setup_dev_cert.ps1"
    if not ps_script.exists():
        return

    try:
        # Reuse existing cert setup logic
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)], capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().splitlines()
        thumbprint = next((line.split(":")[-1].strip() for line in lines if "Certificate found:" in line), None)

        if not thumbprint:
            print("[WARN] No certificate thumbprint found.")
            return

        cmd = [str(signtool), "sign", "/sha1", thumbprint, "/fd", "SHA256", "/t", "http://timestamp.digicert.com", str(msi_path)]

        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[SUCCESS] Signed MSI: {msi_path.name}")

    except Exception as e:
        print(f"[ERROR] MSI signing failed: {e}")


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
    # Strip pre-release / build metadata (e.g. "0.2.5-beta" → "0.2.5")
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
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_missing_wix_extensions(wix_path: str) -> list[str]:
    """Return required WiX extensions that are not currently installed."""
    try:
        result = subprocess.run(
            [wix_path, "extension", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return list(REQUIRED_WIX_EXTENSIONS)

        output = result.stdout
        return [extension for extension in REQUIRED_WIX_EXTENSIONS if extension not in output]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return list(REQUIRED_WIX_EXTENSIONS)


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
    print("  3. Add required WiX extensions:")
    print("     wix extension add WixToolset.UI.wixext")
    print("     wix extension add WixToolset.Util.wixext")
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

    # Generate installer images if PIL is available
    if PIL_AVAILABLE:
        _generate_installer_images()

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

    # Check required WiX extensions (non-fatal warning; build may still work
    # if extensions are available in a different scope)
    missing_extensions = _get_missing_wix_extensions(wix_path)  # type: ignore[arg-type]  # guarded by missing check above
    if missing_extensions:
        for extension in missing_extensions:
            print(f"[WARN] {extension} not found in global extension list.")
            print(f"[WARN] If the build fails, run: wix extension add {extension}")
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
    print(f"[INFO] Executable size: {EXE_PATH.stat().st_size / (1024 * 1024):.1f} MB")

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
        wix_path,
        "build",
        "-arch",
        arch,
        "-ext",
        "WixToolset.UI.wixext",
        "-ext",
        "WixToolset.Util.wixext",
        "-d",
        f"ProductVersion={version}",
        "-d",
        f"ProjectDir={PROJECT_ROOT}",
        "-d",
        f"DistDir={DIST_DIR}",
        "-o",
        str(msi_path),
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
        print(f'    msiexec /i "{msi_path}"')
        print()
        print("  To install silently:")
        print(f'    msiexec /i "{msi_path}" /qn')
        print()
        print("  To uninstall silently:")
        print(f'    msiexec /x "{msi_path}" /qn')
        print("=" * 60)

        # Sign the MSI
        _sign_msi(msi_path)
    else:
        print()
        print("[ERROR] MSI build failed!")
        print("[ERROR] Check the output above for details.")
        print()
        print("Common fixes:")
        print("  - Install WiX UI extension: wix extension add WixToolset.UI.wixext")
        print("  - Install WiX Util extension: wix extension add WixToolset.Util.wixext")
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
        "--output",
        "-o",
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

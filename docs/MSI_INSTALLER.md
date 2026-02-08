# Goldflipper MSI Installer

Build a proper Windows Installer (.msi) package for distributing Goldflipper.

## Overview

The MSI installer wraps the Nuitka-compiled `goldflipper.exe` into a standard
Windows Installer package that provides:

- **Program Files installation** → `C:\Program Files\Goldflipper\`
- **Start Menu shortcut** → Start Menu → Goldflipper
- **Desktop shortcut** (optional, enabled by default)
- **Add/Remove Programs** entry with icon and uninstall support
- **Major upgrade support** — newer versions seamlessly replace older ones
- **Silent install** support via `msiexec` flags

## Prerequisites

### 1. .NET 6+ SDK

Download from <https://dotnet.microsoft.com/download>

Verify:

```powershell
dotnet --version
```

### 2. WiX Toolset v4+

Install as a .NET global tool:

```powershell
dotnet tool install --global wix
```

Verify:

```powershell
wix --version
```

### 3. WiX UI Extension

Provides the graphical install wizard (Welcome → License → Directory → Install):

```powershell
wix extension add WixToolset.UI.wixext
```

### 4. Nuitka Build

The MSI packages the compiled executable from `dist/goldflipper.exe`.
Build it first (or let the MSI script trigger it automatically):

```powershell
uv run python scripts/build_nuitka.py
```

## Building the MSI

### One-command build

```powershell
uv run python scripts/build_msi.py
```

This will:

1. Read the version from `pyproject.toml`
2. Verify all prerequisites
3. Trigger a Nuitka build if `dist/goldflipper.exe` is missing
4. Compile the WiX source into an MSI

Output: `dist/goldflipper-X.Y.Z-x64.msi`

### Options

```text
--arch {x86,x64,arm64}   Target architecture (default: x64)
--skip-nuitka            Skip Nuitka build (assumes exe already exists)
--output, -o PATH        Override output MSI path
```

### Manual WiX build

```powershell
wix build -arch x64 `
    -ext WixToolset.UI.wixext `
    -d ProductVersion=0.2.3 `
    -d ProjectDir=. `
    -d DistDir=dist `
    -o dist\goldflipper-0.2.3-x64.msi `
    installer\goldflipper.wxs
```

## Installing

### GUI install (default)

```powershell
msiexec /i dist\goldflipper-0.2.3-x64.msi
```

### Silent install

```powershell
msiexec /i dist\goldflipper-0.2.3-x64.msi /qn
```

### Silent install to custom directory

```powershell
msiexec /i dist\goldflipper-0.2.3-x64.msi /qn INSTALLFOLDER="D:\MyApps\Goldflipper"
```

### Uninstall

```powershell
msiexec /x dist\goldflipper-0.2.3-x64.msi /qn
```

Or use **Add/Remove Programs** in Windows Settings.

## File Structure

```text
installer/
├── goldflipper.wxs      # WiX v4 source (Package, Components, Shortcuts)
└── License.rtf          # License text shown during installation (RTF)

scripts/
└── build_msi.py         # Python build orchestration script
```

## What Gets Installed

| File / Shortcut | Location |
| --- | --- |
| `goldflipper.exe` | `C:\Program Files\Goldflipper\` |
| `goldflipper.ico` | `C:\Program Files\Goldflipper\` |
| Start Menu shortcut | `Start Menu\Programs\Goldflipper\` |
| Desktop shortcut | Desktop (optional feature) |

## First Run After Install

On first launch, Goldflipper's built-in **First Run Setup Wizard** will appear
to configure `settings.yaml` and set up the data directory. This is handled by
the application itself, not the MSI installer.

## Versioning & Upgrades

- The MSI version is derived from `pyproject.toml` (pre-release suffixes stripped)
- The `UpgradeCode` GUID is fixed across all versions — this enables seamless
  major upgrades where a new version automatically replaces the old one
- Downgrade attempts are blocked with an error message

## Customisation

### Custom banner/dialog images

Uncomment the `WixVariable` lines in `goldflipper.wxs` and provide:

- `installer/banner.bmp` — 493×58 pixels (top banner)
- `installer/dialog.bmp` — 493×312 pixels (welcome/finish background)

### Removing the license dialog

Remove the `WixUILicenseRtf` variable and switch to `WixUI_Minimal` instead
of `WixUI_InstallDir` in the wxs file.

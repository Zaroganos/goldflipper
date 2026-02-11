# MSI Installer Development Chat

**Date**: February 8-11, 2026  
**Branch**: `feature/msi-installer` → `multistrat`  
**Objective**: Implement Windows Installer (MSI) for Goldflipper

## Initial Request

> User: "let's implement an .msi installer (installable form) for this software. create a new branch if needed, or not if you think it's trivial."

## Implementation Process

### 1. Branch Creation & Research
- Created `feature/msi-installer` branch (based on `multistrat`)
- Researched WiX Toolset v4+ syntax and best practices
- Analyzed existing Nuitka build system

### 2. Core Implementation

#### Files Created:
- **`installer/goldflipper.wxs`** - WiX v4 XML source (150 lines)
  - Package definition with fixed UpgradeCode: `7B2A7F4E-3D1C-4A8B-9E5F-6C0D2B4A8E1F`
  - Major upgrade support with downgrade protection
  - WixUI_InstallDir dialog set (Welcome → License → Directory → Install)
  - Start Menu shortcut (mandatory) + Desktop shortcut (optional)

- **`installer/License.rtf`** - License text in RTF format for installer dialog
- **`scripts/build_msi.py`** - Python build orchestration (332 lines)
  - Prerequisites checking (.NET SDK, WiX CLI, UI extension)
  - Version extraction from `pyproject.toml` (strips pre-release suffixes)
  - Nuitka build integration (optional automatic trigger)
  - WiX CLI path resolution (PATH + .dotnet/tools fallback)

#### Key Features:
- Professional GUI installer with license agreement
- Program Files installation (`C:\Program Files\Goldflipper\`)
- Windows ecosystem integration (shortcuts, Add/Remove Programs)
- Silent installation support (`msiexec /qn`)
- Major upgrade support (newer replaces older, blocks downgrade)
- Embedded cabinet (single MSI file)

### 3. Build Issues & Fixes

#### XML Comment Issue:
```
C:\...\goldflipper.wxs(20) : error WIX0104: Not a valid source file; detail: An XML comment cannot contain '--', and '-' cannot be the last character.
```
**Fix**: Removed `--global` from XML comments (illegal in XML)

#### WiX CLI Path Issue:
```
[WARN] WixToolset.UI.wixext not found in global extension list.
```
**Fix**: Added `_find_wix()` function to check both PATH and `%USERPROFILE%\.dotnet\tools\`

### 4. Documentation

#### User-Facing (`docs/MSI_INSTALLER.md`):
- Prerequisites and setup instructions
- Build commands and options
- Installation methods (GUI, silent, custom directory)
- Troubleshooting and customization

#### Development (`docs/WINDOWS_INSTALLER.md`):
- Complete implementation overview
- Technical architecture details
- Build system integration
- Maintenance and testing procedures

#### README Update:
- Added Windows Installer as recommended installation method
- Linked to comprehensive documentation

### 5. Successful Build
```
============================================================
  MSI BUILD SUCCESSFUL
============================================================
  Installer : C:\...\dist\goldflipper-0.2.3-x64.msi
  Size      : 80.9 MB
  Version   : 0.2.3
  Arch      : x64
```

## Compatibility Analysis

### Side-by-Side Issues Identified:

**❌ Service Mode Incompatibility**:
- MSI installs to `Program Files` with only executable
- Service mode expects source code structure (`src/service/`)
- Service registration commands will fail with MSI installation

**❌ No Deployment Choice During Setup**:
- MSI only asks: License → Directory → Desktop Shortcut
- No questions about service vs portable vs source code
- Users get confused when service options appear in TUI but don't work

**⚠️ Path Expectation Mismatches**:
```python
# Service mode expects:
goldflipper/src/service/service_wrapper.py

# MSI provides:
C:\Program Files\Goldflipper\goldflipper.exe
C:\Program Files\Goldflipper\goldflipper.ico
```

## Merge Confusion & Resolution

### The Problem:
1. User said "merge into main" - meant `multistrat` branch
2. I merged into literal `main` branch by mistake
3. Pushed MSI commits to `origin/main`
4. User corrected the misunderstanding

### Resolution Process:
1. ✅ Merged MSI into `multistrat` (correct branch)
2. ❌ Accidentally pushed to `main` 
3. ✅ Reset local `main` to original state
4. ✅ Force-pushed to fix `origin/main`
5. ✅ Verified MSI only in `multistrat`

### Final State:
- `main`: Clean (no MSI commits)
- `multistrat`: Contains MSI installer (5 commits)
- `origin/main`: Reset to original state
- `origin/multistrat`: Contains MSI installer

## Key Commits

1. `75f7498` - Add MSI installer support using WiX Toolset v4+
2. `6fd45a6` - Fix MSI build: remove illegal XML comment dashes, resolve wix CLI path
3. `3bb7081` - Create dotnet-tools.json
4. `b5f557f` - Add comprehensive Windows Installer documentation
5. `add1d17` - Update README.md

## Files Added/Modified

### New Files:
- `installer/goldflipper.wxs` - WiX source
- `installer/License.rtf` - License file
- `scripts/build_msi.py` - Build script
- `docs/MSI_INSTALLER.md` - User guide
- `docs/WINDOWS_INSTALLER.md` - Development documentation
- `dotnet-tools.json` - .NET tools manifest

### Modified:
- `README.md` - Added MSI installer section
- `.gitignore` - Added WiX build artifacts (`*.wixobj`, `*.wixpdb`)

## Technical Details

### WiX Configuration:
```xml
<Package
    Name="Goldflipper"
    Manufacturer="Iliya Yaroshevskiy"
    Version="$(var.ProductVersion)"
    UpgradeCode="7B2A7F4E-3D1C-4A8B-9E5F-6C0D2B4A8E1F"
    Scope="perMachine"
    InstallerVersion="500"
    Compressed="yes">
```

### Build Command:
```bash
uv run python scripts/build_msi.py --arch x64 --skip-nuitka
```

### Output:
- `dist/goldflipper-0.2.3-x64.msi` (80.9 MB)
- Embedded cabinet (single file distribution)
- Windows Installer v500 compatibility

## Recommendations for Future

1. **Enhance MSI** - Add service components and deployment choices
2. **Clear Documentation** - Explain when to use each deployment method
3. **Detection Logic** - Hide service options in MSI installations
4. **Separate Installers** - Different installers for different use cases

## Conclusion

The MSI installer implementation provides Goldflipper with a professional, enterprise-ready installation package. However, it currently conflicts with the service mode functionality and needs either enhancement or clear documentation to guide users to the appropriate deployment method for their needs.

The implementation is successfully integrated into the `multistrat` development branch and ready for use as a portable executable installer.

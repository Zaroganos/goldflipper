# Goldflipper Windows Installer (MSI) Implementation

## Overview

This document describes the complete Windows Installer (MSI) implementation for Goldflipper, which provides a professional, enterprise-ready installation package for Windows users. The MSI installer wraps the Nuitka-compiled executable into a standard Windows Installer package with full integration into the Windows ecosystem.

## Development Summary

### Implementation Date
**February 8, 2026** - Feature branch `feature/msi-installer`

### Technologies Used
- **WiX Toolset v4+** - Modern Windows Installer XML toolset
- **.NET 6+ SDK** - Required for WiX CLI
- **Python 3.11+** - Build orchestration script
- **Nuitka** - For the compiled executable that the MSI packages

### Key Features Implemented

#### 1. Professional Installation Experience
- **GUI Installer** with Welcome → License → Directory → Install wizard flow
- **License Agreement** displayed during installation using RTF format
- **Custom Installation Directory** support (defaults to Program Files)
- **Progress Indication** and standard Windows Installer UX

#### 2. System Integration
- **Program Files Installation** to `C:\Program Files\Goldflipper\`
- **Start Menu Shortcut** under `Start Menu\Programs\Goldflipper\`
- **Desktop Shortcut** (optional feature, enabled by default)
  - TODO: Add option to the install wizard flow; remove from the secondary python tkinter GUI if using the install wizard instead.
- **Add/Remove Programs** entry with:
  - Application icon
  - Product information
  - Help and support links
  - Proper uninstall support

#### 3. Version Management
- **Major Upgrade Support** - Newer versions seamlessly replace older ones
- **Downgrade Protection** - Prevents installing older versions over newer
- **Fixed UpgradeCode** - Ensures proper upgrade chain across versions
- **Automatic Version Detection** - Reads from `pyproject.toml`
  - TODO: Also check the dl location's json manifest

#### 4. Enterprise Features
- **Silent Installation** support (`msiexec /qn`)
- **Custom Directory Installation** (`INSTALLFOLDER` property)
- **Per-Machine Installation Scope** (requires admin privileges)
  - TODO: Check if it will need the Powershell execution override thing
- **Embedded Cabinet** - Single MSI file, no loose CAB files

## Architecture

### File Structure
```
installer/
├── goldflipper.wxs      # WiX v4 XML source file
└── License.rtf          # License text for installer dialog

scripts/
└── build_msi.py         # Python build orchestration script

docs/
├── MSI_INSTALLER.md     # User-facing installation guide
└── WINDOWS_INSTALLER.md # This development documentation
```

### WiX Source Components

#### Package Definition
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

#### Key Elements
- **MajorUpgrade** - Handles version upgrades and downgrade protection
- **MediaTemplate** - Embeds cabinet for single-file distribution
- **Icon & ARP Properties** - Add/Remove Programs integration
- **WixUI_InstallDir** - Standard installation wizard
- **WixUILicenseRtf** - License agreement display

#### Installation Features
1. **MainFeature** (Level 1) - Core application and Start Menu shortcut
2. **DesktopShortcutFeature** (Level 1) - Optional desktop shortcut

### Build Script Architecture

#### Prerequisites Checking
- **.NET SDK** availability verification
- **WiX CLI** detection (PATH + .dotnet/tools fallback)
- **WiX UI Extension** validation
- **Nuitka executable** presence verification

#### Version Management
```python
def _read_version() -> str:
    """Read version from pyproject.toml and normalize for MSI"""
    # Strips pre-release suffixes (e.g., "0.2.3-beta" → "0.2.3")
    # Ensures MSI-compatible X.Y.Z format
```

#### Build Process
1. **Version Extraction** from `pyproject.toml`
2. **Prerequisites Validation**
3. **Nuitka Build** (optional, automatic if exe missing)
4. **WiX Compilation** with proper parameters
5. **MSI Generation** with embedded cabinet

## Technical Implementation Details

### WiX Toolset Integration
- Uses **WiX v4+** (modern .NET-based toolset)
- **WixToolset.UI.wixext** extension for installer dialogs
- **Preprocessor Variables** for dynamic content:
  - `ProductVersion` - From pyproject.toml
  - `ProjectDir` - Root directory
  - `DistDir` - Build output directory

### Windows Installer Best Practices
- **Component Rules** - One component per directory, proper GUIDs
- **Shortcut Management** - Registry-based for proper cleanup
- **Upgrade Strategy** - MajorUpgrade with downgrade protection
- **Icon Integration** - ARP icon and shortcut icons
- **Uninstall Cleanup** - RemoveFolder and RegistryValue cleanup

### Error Handling & User Experience
- **Prerequisites Validation** with clear error messages
- **Missing File Warnings** for optional assets (icon, license)
- **Build Progress Indication** throughout the process
- **Common Fix Suggestions** in error output

## Build System Integration

### Command Line Interface
```bash
# Standard build
uv run python scripts/build_msi.py

# With options
uv run python scripts/build_msi.py --arch x64 --skip-nuitka --output custom.msi
```

### Build Options
- `--arch {x86,x64,arm64}` - Target architecture (default: x64)
- `--skip-nuitka` - Skip Nuitka build (assumes exe exists)
- `--output, -o PATH` - Custom output MSI path

### Integration Points
- **Version Sync** - Automatically reads from `pyproject.toml`
- **Nuitka Integration** - Can trigger Nuitka build automatically
- **Git Integration** - .gitignore updated for build artifacts
- **CI/CD Ready** - Script can be used in automated pipelines

## Installation Experience

### User Installation Flow
1. **Welcome Screen** - Product introduction
2. **License Agreement** - RTF license display with accept/decline
3. **Installation Directory** - Choose target folder (default: Program Files)
4. **Feature Selection** - Desktop shortcut on/off
5. **Installation Progress** - Standard Windows Installer progress
6. **Completion** - Success message with launch option

### Post-Installation
- **Start Menu Integration** - Goldflipper folder with shortcut
- **Desktop Shortcut** - If selected during installation
- **Add/Remove Programs** - Full uninstall support
- **First Run Setup** - Application handles initial configuration

## Version Management Strategy

### UpgradeCode vs ProductCode
- **UpgradeCode** (Fixed): `7B2A7F4E-3D1C-4A8B-9E5F-6C0D2B4A8E1F`
  - Remains constant across all versions
  - Enables major upgrade detection
- **ProductCode** (Auto-generated): Changes per version
  - Generated by WiX during build
  - Ensures proper Windows Installer behavior

### Version Numbering
- **Source**: `pyproject.toml` version field
- **Format**: X.Y.Z (numeric only for MSI compatibility)
- **Pre-release**: Stripped (e.g., "0.2.3-beta" → "0.2.3")
- **Validation**: Ensures MSI-compatible version format

### Upgrade Behavior
- **Major Upgrade**: Newer version replaces older automatically
- **Downgrade Protection**: Error message when attempting downgrade
- **Minor Updates**: Handled through major upgrade mechanism
- **Patch Updates**: Supported through version increment

## Distribution Considerations

### File Size Optimization
- **High Compression** - MediaTemplate with CompressionLevel="high"
- **Embedded Cabinet** - Single MSI file, no external dependencies
- **Efficient Packaging** - Only necessary files included

### System Requirements
- **Windows 10+** - Modern Windows Installer support
- **Administrator Privileges** - Required for Program Files installation
- **.NET Framework** - Included with Windows (no separate install needed)
- **Disk Space** - ~100MB for application and installer

### Security Considerations
- **Code Signing** - Recommended for distribution (not implemented)
  - TODO!!! Self-signed for now. Let the user import the self-signed certs??
- **Digital Signature** - Prevents tampering warnings
- **UAC Compliance** - Proper elevation requests
- **Secure Installation** - No temporary file exposure

## Maintenance and Updates

### Build Process Maintenance
- **Dependency Updates** - Keep WiX Toolset current
- **Version Sync** - Ensure pyproject.toml version accuracy
- **Testing** - Verify install/uninstall cycles
- **Documentation** - Keep this doc updated with changes

### Troubleshooting Common Issues
1. **WiX Not Found** - Check .NET tools PATH
2. **UI Extension Missing** - Run `wix extension add`
3. **Version Format Error** - Check pyproject.toml version
4. **Missing Executable** - Run Nuitka build first
5. **XML Parse Errors** - Check for illegal comment sequences

### Future Enhancements
- **Code Signing Integration** - Automated signing during build
- **Custom Graphics** - Banner and dialog images
- **Update Checking** - Auto-update mechanism
- **Multi-Language Support** - Internationalization
- **Silent Repair** - Self-repair capabilities

## Testing and Validation

### Installation Testing Checklist
- [ ] Clean install on Windows 10/11
- [ ] Upgrade from previous version
- [ ] Downgrade attempt (should fail)
- [ ] Silent install (`/qn`)
- [ ] Custom directory install
- [ ] Feature selection (desktop shortcut on/off)
- [ ] Uninstall via Add/Remove Programs
- [ ] Uninstall via command line
- [ ] Shortcut functionality
- [ ] First run setup integration

### Build Testing Checklist
- [ ] Prerequisites validation
- [ ] Version extraction accuracy
- [ ] Nuitka integration (if needed)
- [ ] WiX compilation success
- [ ] MSI file generation
- [ ] Output file naming convention
- [ ] Build script error handling

## Conclusion

The MSI installer implementation provides Goldflipper with a professional, enterprise-ready installation package that meets Windows Installer best practices. The implementation includes:

- Complete user experience with GUI installer
- Robust version management and upgrade support
- Integration with Windows ecosystem (shortcuts, Add/Remove Programs)
- Automated build process with prerequisite checking
- Comprehensive documentation and maintenance procedures

This implementation positions Goldflipper for professional distribution and enterprise adoption while maintaining the flexibility needed for ongoing development and updates.

## Related Documentation

- **[MSI_INSTALLER.md](MSI_INSTALLER.md)** - User-facing installation guide
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - General development setup
- **[README.md](README.md)** - Project overview and getting started

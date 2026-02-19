"""
Nuitka project configuration for Goldflipper.

Reference:
https://nuitka.net/doc/nuitka-project-options.html

CRITICAL FIX (2025-12-03):
- Python modules must be in NUITKA_INCLUDE_PACKAGES (compiled into exe)
- Only non-Python data files go in NUITKA_DATA_FILES
- Using --include-data-dir for .py files makes them DATA, not executable!
"""

# Main entry point
NUITKA_MAIN = "goldflipper/launcher.py"

# Output configuration
NUITKA_OUTPUT_DIR = "dist"
NUITKA_OUTPUT_FILENAME = "goldflipper"

# Build mode
NUITKA_STANDALONE = True
NUITKA_ONEFILE = True

# Windows console behavior
# "force" ensures a console is always created (required for Textual TUI)
# "attach" would fail when double-clicking exe since there's no console to attach to
NUITKA_WINDOWS_CONSOLE_MODE = "force"

# Performance
NUITKA_LTO = "yes"
# anti-bloat is now always enabled by default in Nuitka 2.x
NUITKA_PLUGIN_ENABLE = ["tk-inter"]

# Windows icon for the executable
NUITKA_WINDOWS_ICON = "goldflipper.ico"

# Import handling
NUITKA_FOLLOW_IMPORTS = True

# ============================================================================
# PACKAGES TO COMPILE (--include-package)
# These Python modules are dynamically imported via importlib.import_module()
# and must be explicitly included for Nuitka to compile them.
# ============================================================================
NUITKA_INCLUDE_PACKAGES = [
    "goldflipper.tools",  # All tool modules (GUI, CLI tools)
    "goldflipper.chart",  # Chart viewer module
    "goldflipper.trade_logging",  # Trade logger module
    "goldflipper.strategy",  # Strategy modules (runners, shared, playbooks)
    "goldflipper.utils",  # Utility modules
]

# ============================================================================
# DATA FILES (--include-data-dir / --include-data-files)
# Non-Python files only: YAML configs, JSON templates, CSV reference data.
# Python modules should NOT be here - they won't be compiled!
# ============================================================================
NUITKA_DATA_FILES = [
    # Core config templates (YAML)
    ("goldflipper/config", "goldflipper/config"),
    # Reference data (CSV files)
    ("goldflipper/reference", "goldflipper/reference"),
    # Tool templates only (JSON play templates, not .py files)
    ("goldflipper/tools/templates", "goldflipper/tools/templates"),
    # Strategy playbooks (YAML configs)
    ("goldflipper/strategy/playbooks", "goldflipper/strategy/playbooks"),
    # Application icon
    ("goldflipper.ico", "goldflipper.ico"),
]

# ============================================================================
# DATA FILES TO EXCLUDE (--noinclude-data-files)
# These patterns exclude gitignored or user-specific files from bundling.
# Applied in build scripts (build_nuitka.py, build_nuitka_dev.py).
# ============================================================================
NUITKA_DATA_EXCLUDE_PATTERNS = [
    "**/settings.yaml",  # User-specific config (created on first run)
    "**/*.log",  # Log files
    "**/*.bak",  # Backup files
    "**/*.old",  # Old leftover files
    "**/*.tmp",  # Temp files
    "**/__pycache__/**",  # Python cache
]

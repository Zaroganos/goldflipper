"""
Nuitka project configuration for Goldflipper.

Reference:
https://nuitka.net/doc/nuitka-project-options.html
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
NUITKA_WINDOWS_CONSOLE_MODE = "attach"  # Keep console for Textual UI

# Performance
NUITKA_LTO = "yes"
# anti-bloat is now always enabled by default in Nuitka 2.x
NUITKA_PLUGIN_ENABLE = ["tk-inter"]

# Import handling
NUITKA_FOLLOW_IMPORTS = True

# Data files ("source", "destination" tuples)
# Full exe bundle - includes all tools, chart, trade_logging for internal module launching
NUITKA_DATA_FILES = [
    # Core config and reference data
    ("goldflipper/config", "goldflipper/config"),
    ("goldflipper/reference", "goldflipper/reference"),
    
    # Tools directory - all tool scripts and templates
    ("goldflipper/tools", "goldflipper/tools"),
    
    # Chart viewer module
    ("goldflipper/chart", "goldflipper/chart"),
    
    # Trade logging module
    ("goldflipper/trade_logging", "goldflipper/trade_logging"),
    
    # Strategy playbooks (YAML configs)
    ("goldflipper/strategy/playbooks", "goldflipper/strategy/playbooks"),
    
    # Application icon
    ("goldflipper.ico", "goldflipper.ico"),
]

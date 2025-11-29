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
NUITKA_PLUGIN_ENABLE = ["anti-bloat", "tk-inter"]

# Import handling
NUITKA_FOLLOW_IMPORTS = True

# Data files ("source", "destination" tuples)
NUITKA_DATA_FILES = [
    ("goldflipper/config", "goldflipper/config"),
    ("goldflipper/reference", "goldflipper/reference"),
    ("goldflipper/tools/play-template.json", "goldflipper/tools/play-template.json"),
    ("goldflipper.ico", "goldflipper.ico"),
]

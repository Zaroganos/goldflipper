import sys

# Single source of truth for the running version.
# Keep in sync with pyproject.toml when cutting a release.
__version__ = "0.3.3"

# Only print import message if not running in console mode
if not any("--mode console" in arg for arg in sys.argv):
    print("Importing Goldflipper ...")

# Uncomment these if you need them, but be cautious of circular imports
# from . import config
# from . import core
# from . import alpaca_client

import os
import sys

# Only print import message if not running in console mode
if not any('--mode console' in arg for arg in sys.argv):
    print("Importing goldflipper package")

# Uncomment these if you need them, but be cautious of circular imports
# from . import config
# from . import core
# from . import alpaca_client
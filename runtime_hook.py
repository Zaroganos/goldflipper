import os
import sys

if getattr(sys, "frozen", False):
    # sys._MEIPASS is where PyInstaller unpacks the bundled files.
    base_path = sys._MEIPASS
    # Prepend the temporary folder to the PATH so Windows can find python312.dll.
    os.environ["PATH"] = base_path + os.pathsep + os.environ.get("PATH", "") 
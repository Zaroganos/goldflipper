import os
import sys

def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource.

    This function works for both development and PyInstaller one-file (or one-folder) environments.

    Args:
        relative_path (str): The relative path to the resource from the base folder.

    Returns:
        str: The absolute path to the resource.
    """
    if getattr(sys, "frozen", False):
        # When bundled, PyInstaller extracts files to sys._MEIPASS.
        base_path = sys._MEIPASS
    else:
        # Use this file's directory as the base path in development.
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path) 
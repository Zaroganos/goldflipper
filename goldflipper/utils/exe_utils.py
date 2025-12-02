"""
Executable detection and path utilities for Nuitka-compiled builds.

This module provides utilities for detecting whether the application is running
from a compiled executable (frozen) or from source, and handles path resolution
accordingly.
"""

import sys
import os
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    """
    Check if the application is running from a compiled executable.
    
    Returns:
        True if running from exe (Nuitka/PyInstaller), False if running from source.
    """
    return getattr(sys, 'frozen', False)


def get_executable_path() -> Optional[Path]:
    """
    Get the path to the executable if running frozen.
    
    Returns:
        Path to the executable, or None if running from source.
    """
    if is_frozen():
        return Path(sys.executable)
    return None


def get_application_dir() -> Path:
    """
    Get the application's base directory.
    
    When running from exe: Returns the directory containing the executable.
    When running from source: Returns the goldflipper package directory.
    
    Returns:
        Path to the application directory.
    """
    if is_frozen():
        # When frozen, sys.executable is the exe path
        return Path(sys.executable).parent
    else:
        # When running from source, use the package directory
        return Path(__file__).resolve().parent.parent


def get_package_root() -> Path:
    """
    Get the root directory of the goldflipper package.
    
    When running from exe: Returns the directory containing the executable.
    When running from source: Returns the parent of the goldflipper package.
    
    Returns:
        Path to the package root directory.
    """
    if is_frozen():
        return Path(sys.executable).parent
    else:
        # Go up from utils/ to goldflipper/ to project root
        return Path(__file__).resolve().parent.parent.parent


def get_data_dir(relative_path: str) -> Path:
    """
    Get the path to a data directory, handling both frozen and source modes.
    
    In frozen mode, Nuitka extracts data files to a temp directory.
    This function handles finding them correctly.
    
    Args:
        relative_path: Relative path from the package root (e.g., "goldflipper/config")
        
    Returns:
        Absolute path to the data directory.
    """
    if is_frozen():
        # In onefile mode, data files are extracted alongside the frozen modules
        # __file__ points to the extraction location
        base = Path(__file__).resolve().parent.parent
        return base / relative_path.replace("goldflipper/", "")
    else:
        return get_package_root() / relative_path


def get_external_dir(dir_name: str) -> Path:
    """
    Get the path to an external directory (like plays/, logs/).
    
    These directories exist outside the exe and should be next to it.
    
    Args:
        dir_name: Name of the external directory (e.g., "plays", "logs")
        
    Returns:
        Absolute path to the external directory.
    """
    if is_frozen():
        # External dirs should be next to the exe
        return Path(sys.executable).parent / dir_name
    else:
        return get_package_root() / dir_name


def run_tool_module(module_name: str, *args, **kwargs) -> None:
    """
    Run a tool module, handling both frozen and source modes.
    
    In frozen mode: Imports and runs the module directly.
    In source mode: Can also import directly (subprocess is optional).
    
    Args:
        module_name: Full module path (e.g., "goldflipper.tools.play_creator_gui")
        *args, **kwargs: Arguments to pass to the module's main() function.
    """
    import importlib
    
    try:
        module = importlib.import_module(module_name)
        if hasattr(module, 'main'):
            module.main(*args, **kwargs)
        elif hasattr(module, 'run'):
            module.run(*args, **kwargs)
        else:
            # Some modules like GUI tools just need to be imported to run
            pass
    except Exception as e:
        import logging
        logging.error(f"Failed to run tool module {module_name}: {e}")
        raise


def get_icon_path() -> Path:
    """
    Get the path to the application icon.
    
    Returns:
        Path to goldflipper.ico
    """
    if is_frozen():
        # Icon is bundled with the exe data files
        return Path(sys.executable).parent / "goldflipper.ico"
    else:
        return get_package_root() / "goldflipper.ico"

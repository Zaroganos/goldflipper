"""
Executable detection and path utilities for Nuitka-compiled builds.

This module provides utilities for detecting whether the application is running
from a compiled executable (frozen) or from source, and handles path resolution
accordingly.

CRITICAL: In Nuitka onefile mode:
- sys.executable = python.exe in TEMP extraction directory (NOT the exe!)
- sys.argv[0] = actual path to the .exe file (USE THIS for persistent data!)
- __file__ for modules = temp extraction directory (NOT the exe directory)
- Settings/config should persist NEXT TO the exe, not in temp extraction
- Bundled data files (templates, reference) are in temp extraction

Nuitka Detection (from official docs):
- Nuitka does NOT set sys.frozen (that's PyInstaller)
- Nuitka sets __compiled__ at module level for compiled code
- Nuitka onefile sets __nuitka_binary_dir on the main module
- Use __compiled__ to test if a module was compiled
"""

import sys
import os
from pathlib import Path
from typing import Optional

# Cache the frozen state at module load time
_FROZEN_STATE: Optional[bool] = None


def is_frozen() -> bool:
    """
    Check if the application is running from a Nuitka-compiled executable.
    
    Nuitka Detection (from official Nuitka docs):
    - Nuitka does NOT set sys.frozen (that's PyInstaller only)
    - Nuitka sets __compiled__ at module level for compiled code
    - Nuitka onefile sets __nuitka_binary_dir on the main module
    
    Returns:
        True if running from Nuitka exe, False if running from source.
    """
    global _FROZEN_STATE
    
    # Return cached result if available
    if _FROZEN_STATE is not None:
        return _FROZEN_STATE
    
    # DEBUG: Print diagnostic info to help identify frozen detection issues
    _debug = os.environ.get('GOLDFLIPPER_DEBUG_FROZEN', '')
    if _debug:
        print(f"[is_frozen DEBUG] sys.argv = {sys.argv}")
        print(f"[is_frozen DEBUG] sys.executable = {sys.executable}")
    
    # Check 1: __nuitka_binary_dir in main module (most reliable for onefile)
    main_module = sys.modules.get('__main__')
    if main_module is not None:
        if hasattr(main_module, '__nuitka_binary_dir'):
            if _debug:
                print(f"[is_frozen DEBUG] Found __nuitka_binary_dir = {main_module.__nuitka_binary_dir}")
            _FROZEN_STATE = True
            return True
        # Check if main module was compiled by Nuitka
        if hasattr(main_module, '__compiled__'):
            if _debug:
                print(f"[is_frozen DEBUG] Found __compiled__ on main module")
            _FROZEN_STATE = True
            return True
    
    # Check 2: __compiled__ in global namespace (for compiled modules)
    # Use globals() explicitly since 'in dir()' doesn't work reliably
    try:
        if globals().get('__compiled__', False):
            if _debug:
                print(f"[is_frozen DEBUG] Found __compiled__ in globals")
            _FROZEN_STATE = True
            return True
    except Exception:
        pass
    
    # Check 3: sys.argv[0] is our app (use argv[0], NOT sys.executable!)
    # CRITICAL: In Nuitka onefile mode:
    # - sys.executable = python.exe in TEMP extraction dir (WRONG!)
    # - sys.argv[0] = actual exe path (CORRECT!)
    if sys.argv:
        argv0_name = Path(sys.argv[0]).stem.lower()
        if _debug:
            print(f"[is_frozen DEBUG] argv0_name = {argv0_name}")
        # Match both production and dev builds
        if argv0_name.startswith('goldflipper'):
            if _debug:
                print(f"[is_frozen DEBUG] Matched 'goldflipper' prefix")
            _FROZEN_STATE = True
            return True
        # Check if argv[0] is a .exe that's not python
        if sys.argv[0].lower().endswith('.exe'):
            if argv0_name not in ('python', 'pythonw', 'python3', 'python3w'):
                if _debug:
                    print(f"[is_frozen DEBUG] Matched non-python .exe")
                # Likely a compiled executable
                _FROZEN_STATE = True
                return True
    
    if _debug:
        print(f"[is_frozen DEBUG] No frozen indicators found, returning False")
    _FROZEN_STATE = False
    return False


def get_nuitka_binary_dir() -> Optional[Path]:
    """
    Get the Nuitka binary directory if available.
    
    In Nuitka onefile mode, __nuitka_binary_dir points to the directory
    containing the exe (NOT the temp extraction directory).
    
    Returns:
        Path to the binary directory, or None if not available.
    """
    main_module = sys.modules.get('__main__')
    if main_module is not None and hasattr(main_module, '__nuitka_binary_dir'):
        return Path(main_module.__nuitka_binary_dir)
    return None


def get_executable_path() -> Optional[Path]:
    """
    Get the path to the executable if running frozen.
    
    CRITICAL: In Nuitka onefile mode, sys.executable points to python.exe
    in the temp extraction directory. Use sys.argv[0] for the actual exe!
    
    Returns:
        Path to the executable, or None if running from source.
    """
    if is_frozen():
        # sys.argv[0] contains the actual exe path, NOT sys.executable
        exe_path = sys.argv[0] if sys.argv else sys.executable
        return Path(exe_path).resolve()
    return None


def get_executable_dir() -> Path:
    """
    Get the directory containing the executable (or project root if from source).
    
    This is where PERSISTENT files (settings.yaml, plays/, logs/) should live.
    
    CRITICAL: In Nuitka onefile mode:
    - sys.executable points to python.exe in temp extraction dir (WRONG for persistent data!)
    - sys.argv[0] points to the actual exe (CORRECT)
    - __nuitka_binary_dir also points to exe location if available
    
    Returns:
        Path to the directory containing the exe, or project root if from source.
    """
    if is_frozen():
        # First try Nuitka's binary dir (most reliable for onefile)
        nuitka_dir = get_nuitka_binary_dir()
        if nuitka_dir is not None:
            return nuitka_dir
        # Fall back to sys.argv[0] (NOT sys.executable which is python.exe in temp!)
        exe_path = sys.argv[0] if sys.argv else sys.executable
        return Path(exe_path).resolve().parent
    else:
        # From source: go up from utils/ to goldflipper/ to project root
        return Path(__file__).resolve().parent.parent.parent


def get_application_dir() -> Path:
    """
    Get the application's base directory.
    
    When running from exe: Returns the directory containing the executable.
    When running from source: Returns the goldflipper package directory.
    
    Returns:
        Path to the application directory.
    """
    if is_frozen():
        # Use sys.argv[0] for actual exe location (not sys.executable which is python.exe in temp)
        exe_path = sys.argv[0] if sys.argv else sys.executable
        return Path(exe_path).resolve().parent
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
        # Use sys.argv[0] for actual exe location
        exe_path = sys.argv[0] if sys.argv else sys.executable
        return Path(exe_path).resolve().parent
    else:
        # Go up from utils/ to goldflipper/ to project root
        return Path(__file__).resolve().parent.parent.parent


def get_bundled_data_dir() -> Path:
    """
    Get the directory where bundled data files are extracted in frozen mode.
    
    In Nuitka onefile builds, data files are extracted to a temp directory.
    This returns that temp directory (for reading bundled templates, reference data).
    
    Returns:
        Path to bundled data directory.
    """
    if is_frozen():
        # __file__ points to the extraction location for this module
        # Go up to the goldflipper package level within extraction
        return Path(__file__).resolve().parent.parent
    else:
        # From source: the goldflipper package directory
        return Path(__file__).resolve().parent.parent


def get_config_dir() -> Path:
    """
    Get the directory for configuration files.
    
    IMPORTANT: In frozen mode, this returns a path NEXT TO the exe (persistent).
    The bundled config templates are in the temp extraction, but user config
    should be stored next to the exe.
    
    If a custom data directory is configured, config goes there.
    
    Returns:
        Path to config directory (persistent, next to exe or in source tree).
    """
    custom_data_dir = get_custom_data_directory()
    if custom_data_dir:
        config_dir = custom_data_dir / "config"
    elif is_frozen():
        # Config lives next to the exe for persistence
        # Use sys.argv[0] for actual exe location (NOT sys.executable which is python.exe in temp!)
        exe_path = sys.argv[0] if sys.argv else sys.executable
        config_dir = Path(exe_path).resolve().parent / "config"
    else:
        # From source: goldflipper/config
        return Path(__file__).resolve().parent.parent / "config"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_settings_path() -> Path:
    """
    Get the path to settings.yaml.
    
    In frozen mode: settings.yaml lives NEXT TO the exe (persistent).
    In source mode: settings.yaml lives in goldflipper/config/.
    
    Returns:
        Path to settings.yaml
    """
    return get_config_dir() / "settings.yaml"


def get_settings_template_path() -> Path:
    """
    Get the path to the settings template file.
    
    In frozen mode: template is in the temp extraction directory.
    In source mode: template is in goldflipper/config/.
    
    Returns:
        Path to settings_template.yaml
    """
    if is_frozen():
        # Template is bundled in the extraction
        return get_bundled_data_dir() / "config" / "settings_template.yaml"
    else:
        return Path(__file__).resolve().parent.parent / "config" / "settings_template.yaml"


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
        # Use sys.argv[0] for actual exe location (NOT sys.executable which is python.exe in temp!)
        exe_path = sys.argv[0] if sys.argv else sys.executable
        return Path(exe_path).resolve().parent / dir_name
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
        # Try bundled location first (in extraction dir)
        bundled_icon = get_bundled_data_dir() / "goldflipper.ico"
        if bundled_icon.exists():
            return bundled_icon
        # Fall back to exe directory
        return get_executable_dir() / "goldflipper.ico"
    else:
        return get_package_root() / "goldflipper.ico"


def get_tools_dir() -> Path:
    """
    Get the directory containing tool scripts.
    
    In frozen mode: Returns the bundled tools directory (in temp extraction).
    In source mode: Returns goldflipper/tools/.
    
    Returns:
        Path to tools directory.
    """
    if is_frozen():
        return get_bundled_data_dir() / "tools"
    else:
        return Path(__file__).resolve().parent.parent / "tools"


def get_chart_dir() -> Path:
    """
    Get the directory containing chart modules.
    
    In frozen mode: Returns the bundled chart directory (in temp extraction).
    In source mode: Returns goldflipper/chart/.
    
    Returns:
        Path to chart directory.
    """
    if is_frozen():
        return get_bundled_data_dir() / "chart"
    else:
        return Path(__file__).resolve().parent.parent / "chart"


def get_trade_logging_dir() -> Path:
    """
    Get the directory containing trade logging modules.
    
    In frozen mode: Returns the bundled trade_logging directory (in temp extraction).
    In source mode: Returns goldflipper/trade_logging/.
    
    Returns:
        Path to trade_logging directory.
    """
    if is_frozen():
        return get_bundled_data_dir() / "trade_logging"
    else:
        return Path(__file__).resolve().parent.parent / "trade_logging"


def get_reference_dir() -> Path:
    """
    Get the directory containing reference data (CSV templates, etc.).
    
    In frozen mode: Returns the bundled reference directory (in temp extraction).
    In source mode: Returns goldflipper/reference/.
    
    Returns:
        Path to reference directory.
    """
    if is_frozen():
        return get_bundled_data_dir() / "reference"
    else:
        return Path(__file__).resolve().parent.parent / "reference"


def debug_paths() -> dict:
    """
    Return a dictionary of all resolved paths for debugging.
    
    Useful for diagnosing path issues in frozen builds.
    """
    # Check template file exists
    template_path = get_settings_template_path()
    settings_path = get_settings_path()
    
    return {
        'is_frozen': is_frozen(),
        'sys.executable': str(sys.executable),
        'sys.argv[0]': str(sys.argv[0]) if sys.argv else 'N/A',
        '__file__': str(__file__),
        'nuitka_binary_dir': str(get_nuitka_binary_dir()) if get_nuitka_binary_dir() else None,
        'custom_data_dir': str(get_custom_data_directory()) if get_custom_data_directory() else 'None (using default)',
        'data_location_cfg': str(get_data_location_config_path()),
        'data_location_cfg_exists': get_data_location_config_path().exists(),
        'executable_dir': str(get_executable_dir()),
        'bundled_data_dir': str(get_bundled_data_dir()),
        'config_dir': str(get_config_dir()),
        'settings_path': str(settings_path),
        'settings_exists': settings_path.exists(),
        'settings_template_path': str(template_path),
        'settings_template_exists': template_path.exists(),
        'plays_root': str(get_plays_root()),
        'plays_dir_active': str(get_plays_dir()),
        'logs_dir': str(get_logs_dir()),
        'tools_dir': str(get_tools_dir()),
        'icon_path': str(get_icon_path()),
    }


def get_plays_root() -> Path:
    """
    Get the root directory for all play files (contains account subdirectories).
    
    CRITICAL: In frozen mode, plays must persist NEXT TO the exe, not in temp extraction.
    If a custom data directory is configured, plays go there.
    
    Returns:
        Path to plays/ root directory (persistent).
    """
    custom_data_dir = get_custom_data_directory()
    if custom_data_dir:
        plays_dir = custom_data_dir / "plays"
    elif is_frozen():
        # Use sys.argv[0] for actual exe location (NOT sys.executable which is python.exe in temp!)
        exe_path = sys.argv[0] if sys.argv else sys.executable
        plays_dir = Path(exe_path).resolve().parent / "plays"
    else:
        # From source: project_root/plays/
        plays_dir = get_package_root() / "plays"
    
    # Ensure base plays directory exists
    plays_dir.mkdir(parents=True, exist_ok=True)
    return plays_dir


def get_plays_dir(account_name: Optional[str] = None, strategy: str = "shared") -> Path:
    """
    Get the plays directory for the active account and strategy.
    
    Directory structure:
        plays/
        ├── account_1/                    # Live account
        │   ├── shared/                   # Shared pool (legacy/cross-strategy)
        │   │   ├── new/
        │   │   ├── open/
        │   │   └── ...
        │   ├── option_swings/            # Strategy-specific (future)
        │   └── ...
        ├── account_2/                    # Paper account 1
        │   └── ...
        └── ...
    
    Args:
        account_name: Optional account name override (e.g., 'live', 'paper_1').
                      If None, uses the active account from config.
        strategy: Strategy name for strategy-specific directories.
                  Default is "shared" for the legacy shared pool.
    
    Returns:
        Path to plays/{account_dir}/{strategy}/ directory.
    """
    from goldflipper.config.config import get_active_account_dir, get_account_dir
    
    plays_root = get_plays_root()
    
    # Determine account directory
    if account_name:
        account_dir = get_account_dir(account_name)
    else:
        account_dir = get_active_account_dir()
    
    # Build full path: plays/{account_dir}/{strategy}/
    plays_dir = plays_root / account_dir / strategy
    plays_dir.mkdir(parents=True, exist_ok=True)
    
    return plays_dir


def get_play_subdir(subdir: str, account_name: Optional[str] = None, strategy: str = "shared") -> Path:
    """
    Get a specific play subdirectory (new, open, closed, etc.) for an account/strategy.
    
    Args:
        subdir: Subdirectory name (new, open, pending-opening, pending-closing, closed, expired, temp)
        account_name: Optional account name override. If None, uses active account.
        strategy: Strategy name. Default is "shared".
        
    Returns:
        Path to the play subdirectory (created if doesn't exist).
    """
    play_subdir = get_plays_dir(account_name=account_name, strategy=strategy) / subdir
    play_subdir.mkdir(parents=True, exist_ok=True)
    return play_subdir


def get_all_account_plays_dirs() -> dict:
    """
    Get plays directories for all enabled accounts.
    
    Returns:
        Dict mapping account names to their plays directory paths.
        E.g., {'paper_1': Path('plays/account_2/shared'), ...}
    """
    from goldflipper.config.config import get_enabled_accounts, get_account_dir
    
    plays_root = get_plays_root()
    result = {}
    
    for account_name in get_enabled_accounts():
        account_dir = get_account_dir(account_name)
        result[account_name] = plays_root / account_dir / "shared"
    
    return result


def ensure_account_plays_structure(account_name: Optional[str] = None) -> Path:
    """
    Ensure the full plays directory structure exists for an account.
    
    Creates:
        plays/{account_dir}/shared/new/
        plays/{account_dir}/shared/pending-opening/
        plays/{account_dir}/shared/open/
        plays/{account_dir}/shared/pending-closing/
        plays/{account_dir}/shared/closed/
        plays/{account_dir}/shared/expired/
        plays/{account_dir}/shared/temp/
    
    Args:
        account_name: Optional account name. If None, uses active account.
        
    Returns:
        Path to the account's shared plays directory.
    """
    plays_dir = get_plays_dir(account_name=account_name, strategy="shared")
    
    # Create all standard subdirectories
    subdirs = ['new', 'pending-opening', 'open', 'pending-closing', 'closed', 'expired', 'temp']
    for subdir in subdirs:
        (plays_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    return plays_dir


def get_logs_dir() -> Path:
    """
    Get the directory for log files.
    
    CRITICAL: In frozen mode, logs must persist NEXT TO the exe, not in temp extraction.
    
    Returns:
        Path to logs/ directory (persistent).
    """
    custom_data_dir = get_custom_data_directory()
    if custom_data_dir:
        logs_dir = custom_data_dir / "logs"
    elif is_frozen():
        # Use sys.argv[0] for actual exe location (NOT sys.executable which is python.exe in temp!)
        exe_path = sys.argv[0] if sys.argv else sys.executable
        logs_dir = Path(exe_path).resolve().parent / "logs"
    else:
        logs_dir = get_package_root() / "logs"
    
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


# =============================================================================
# CUSTOM DATA DIRECTORY SUPPORT
# =============================================================================
# Users can choose a custom directory for all persistent data (config, plays, logs)
# This is stored in a simple config file next to the exe.

# Cache the custom data directory to avoid repeated file reads
_CUSTOM_DATA_DIR: Optional[Path] = None
_CUSTOM_DATA_DIR_CHECKED: bool = False


def get_data_location_config_path() -> Path:
    """
    Get the path to the data location config file.
    
    This file stores the custom data directory if the user chose one.
    Always stored next to the exe (or project root in source mode).
    
    Returns:
        Path to data_location.cfg
    """
    if is_frozen():
        # Use sys.argv[0] for actual exe location (not sys.executable which is python.exe in temp)
        exe_path = sys.argv[0] if sys.argv else sys.executable
        return Path(exe_path).resolve().parent / "data_location.cfg"
    else:
        return get_package_root() / "data_location.cfg"


def get_custom_data_directory() -> Optional[Path]:
    """
    Get the custom data directory if one was configured.
    
    Returns:
        Path to custom data directory, or None if using default location.
    """
    global _CUSTOM_DATA_DIR, _CUSTOM_DATA_DIR_CHECKED
    
    # Return cached result if already checked
    if _CUSTOM_DATA_DIR_CHECKED:
        return _CUSTOM_DATA_DIR
    
    _CUSTOM_DATA_DIR_CHECKED = True
    
    config_path = get_data_location_config_path()
    if config_path.exists():
        try:
            custom_path = config_path.read_text().strip()
            if custom_path:
                custom_path_obj = Path(custom_path)
                # Create the directory if it doesn't exist (user might have deleted it)
                if not custom_path_obj.exists():
                    try:
                        custom_path_obj.mkdir(parents=True, exist_ok=True)
                        print(f"[exe_utils] Created missing custom data directory: {custom_path}")
                    except Exception as e:
                        print(f"[exe_utils] WARNING: Custom data directory '{custom_path}' doesn't exist and couldn't be created: {e}")
                        print(f"[exe_utils] Falling back to default location")
                        return None
                _CUSTOM_DATA_DIR = custom_path_obj
                return _CUSTOM_DATA_DIR
        except Exception as e:
            print(f"[exe_utils] Error reading custom data config: {e}")
    
    return None


def set_custom_data_directory(directory: Optional[Path]) -> None:
    """
    Set a custom data directory for all persistent data.
    
    Args:
        directory: Path to use for data, or None to use default location.
    """
    global _CUSTOM_DATA_DIR, _CUSTOM_DATA_DIR_CHECKED
    
    config_path = get_data_location_config_path()
    
    if directory is None:
        # Remove custom config to use defaults
        if config_path.exists():
            config_path.unlink()
        _CUSTOM_DATA_DIR = None
    else:
        # Save custom directory
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        config_path.write_text(str(directory))
        _CUSTOM_DATA_DIR = directory
    
    _CUSTOM_DATA_DIR_CHECKED = True


def get_default_data_directory() -> Path:
    """
    Get the default data directory (next to exe or project root).
    
    This is the location used if no custom directory is configured.
    
    Returns:
        Path to default data directory.
    """
    if is_frozen():
        # Use sys.argv[0] for actual exe location
        exe_path = sys.argv[0] if sys.argv else sys.executable
        return Path(exe_path).resolve().parent
    else:
        return get_package_root()

"""
Configuration Management Module for Goldflipper

This module provides a centralized configuration management system using a singleton pattern.
It loads settings from a YAML file and provides both object-oriented and traditional access
to configuration values.

The Config class handles:
- Loading configuration from YAML
- Setting up directory structures
- Providing access to configuration values
- Maintaining backward compatibility with existing code

NOTE: This module uses exe-aware path utilities for frozen (exe) mode compatibility.
In frozen mode, settings.yaml persists NEXT TO the exe, while templates are bundled.
"""

import os
import yaml
import logging
import shutil

# Import exe-aware path utilities
from goldflipper.utils.exe_utils import (
    is_frozen,
    get_settings_path,
    get_settings_template_path,
    get_config_dir,
    get_executable_dir,
)

# Flag to track if settings file was just created
settings_just_created = False

def reset_settings_created_flag():
    """Reset the settings_just_created flag after successful configuration."""
    global settings_just_created
    settings_just_created = False

def load_config(auto_create: bool = False):
    """
    Load configuration from settings.yaml.
    
    Args:
        auto_create: If True, automatically create settings from template if missing.
                     If False (default), return empty config if settings don't exist.
                     This allows the first-run wizard to handle settings creation.
    """
    global settings_just_created
    
    # Use exe-aware path utilities
    config_path = str(get_settings_path())
    template_path = str(get_settings_template_path())
    
    # Check if settings.yaml exists
    if not os.path.exists(config_path):
        if auto_create:
            # Auto-create mode: copy template to settings.yaml
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"Neither settings.yaml nor template file found at {template_path}")
            
            # Ensure config directory exists (important for frozen mode)
            config_dir = get_config_dir()
            os.makedirs(config_dir, exist_ok=True)
                
            try:
                # Copy the template to settings.yaml
                shutil.copy2(template_path, config_path)
                settings_just_created = True
                logging.info(f"Created new settings file from template at {config_path}")
                print(f"\nCreated new settings file from template at {config_path}")
                print(f"Please review and update the settings with your API keys and preferences.")
            except Exception as e:
                raise IOError(f"Error creating settings file from template: {e}")
        else:
            # No auto-create: return empty config, let first-run wizard handle it
            # This prevents config loading from bypassing the setup wizard
            return {}
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}  # Settings don't exist yet - first-run wizard will create them
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML configuration: {e}")


def reload_config(auto_create: bool = False):
    """
    Reload the global config after settings have been created/modified.
    
    Call this after the first-run wizard creates settings.yaml.
    """
    global config
    
    # If config is a Config class instance, use its reload method
    if hasattr(config, 'reload'):
        config.reload()  # type: ignore[union-attr]
        return config
    
    # Otherwise reload as dict (fallback)
    config = load_config(auto_create=auto_create)
    return config


def is_config_loaded() -> bool:
    """
    Check if config has been properly loaded with actual settings.
    
    Returns False if settings.yaml doesn't exist (config is empty).
    Works with both dict (from load_config) and Config class instance.
    """
    if isinstance(config, dict):
        return bool(config) and 'alpaca' in config
    elif hasattr(config, '_config'):
        # Config class instance
        return bool(config._config) and 'alpaca' in config._config
    return False


# Initial config load (may be empty if settings.yaml doesn't exist yet)
config = load_config()

class Config:
    """
    Singleton configuration class that manages all Goldflipper settings.
    
    This class provides:
    - Singleton pattern implementation
    - YAML configuration loading
    - Directory structure setup
    - Backward-compatible access to settings
    - Dot notation access to nested settings
    
    Attributes:
        _instance (Config): Singleton instance
        _config (dict): Loaded configuration data
    """
    
    _instance = None
    _config = None

    def __new__(cls):
        """
        Implement singleton pattern and initialize configuration.
        
        Returns:
            Config: Singleton instance of Config class
        """
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
            # Setup paths (with defaults if config is empty)
            cls._instance._setup_paths()
        return cls._instance

    def _load_config(self):
        """
        Load configuration from YAML file.
        
        Attempts to load settings.yaml from the config directory.
        Falls back to empty dict if file is not found or invalid.
        Does NOT auto-create settings - let the first-run wizard handle that.
        
        Uses exe-aware path utilities for frozen mode compatibility.
        """
        config_path = str(get_settings_path())
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
            if self._config:
                logging.info(f"Configuration loaded from {config_path}")
        except FileNotFoundError:
            # Settings don't exist yet - first-run wizard will create them
            self._config = {}
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")
            self._config = {}

    def reload(self):
        """Reload configuration from the settings.yaml file."""
        self._load_config()
        self._setup_paths()  # Re-setup paths with new config values

    def _setup_paths(self):
        """
        Setup absolute paths and create required directories.
        
        Converts relative paths from config to absolute paths and creates
        necessary directories if they don't exist.
        Sets default paths if config is empty (first-run before wizard).
        
        Uses exe-aware path utilities for frozen mode compatibility.
        """
        # In frozen mode: base_dir is next to exe (persistent)
        # In source mode: base_dir is the goldflipper package directory
        base_dir = str(get_executable_dir()) if is_frozen() else os.path.dirname(os.path.dirname(__file__))
        
        # Get paths from config or use defaults
        paths = self._config.get('paths', {}) if self._config else {}
        
        # Setup data paths (with defaults if config is empty)
        self.DATA_DIR = os.path.join(base_dir, paths.get('data_dir', 'data'))
        self.RAW_DATA_DIR = os.path.join(base_dir, paths.get('raw_data_dir', 'data/raw'))
        self.PROCESSED_DATA_DIR = os.path.join(base_dir, paths.get('processed_data_dir', 'data/processed'))
        
        # Setup log paths (with defaults if config is empty)
        self.LOG_DIR = os.path.join(base_dir, paths.get('log_dir', 'logs'))
        self.LOG_FILE = os.path.join(base_dir, paths.get('log_file', 'logs/goldflipper.log'))
        
        # Only create directories if config is loaded (not during first-run wizard)
        if self._config and 'paths' in self._config:
            for directory in [self.DATA_DIR, self.RAW_DATA_DIR, self.PROCESSED_DATA_DIR, self.LOG_DIR]:
                os.makedirs(directory, exist_ok=True)

    def get(self, *keys, default=None):
        """
        Get a configuration value using dot notation.
        
        Args:
            *keys: Variable number of keys for nested access
            default: Default value if key(s) not found
            
        Returns:
            Value from config or default if not found
            
        Example:
            config.get('market_data', 'interval', default='1m')
        """
        value = self._config
        for key in keys:
            try:
                value = value[key]
            except (KeyError, TypeError):
                return default
        return value

    # Properties for backward compatibility
    @property
    def ALPACA_API_KEY(self):
        """Alpaca API key from config."""
        return self.get('alpaca', 'api_key')

    @property
    def ALPACA_SECRET_KEY(self):
        """Alpaca secret key from config."""
        return self.get('alpaca', 'secret_key')

    @property
    def ALPACA_BASE_URL(self):
        """Alpaca API base URL from config."""
        return self.get('alpaca', 'base_url')

    @property
    def TRADE_SYMBOL(self):
        """Default trading symbol from config."""
        return self.get('trading', 'default_symbol')

    @property
    def TRADE_QUANTITY(self):
        """Default trade quantity from config."""
        return self.get('trading', 'default_quantity')

    @property
    def LOG_LEVEL(self):
        """Logging level from config."""
        return self.get('logging', 'level')

# Global config instance
config = Config()


# =============================================================================
# Account Helper Functions
# =============================================================================

# Account directory mapping: config name -> directory name
ACCOUNT_DIR_MAP = {
    'live': 'account_1',
    'paper_1': 'account_2',
    'paper_2': 'account_3',
    'paper_3': 'account_4',
}

# Reverse mapping: directory name -> config name
DIR_ACCOUNT_MAP = {v: k for k, v in ACCOUNT_DIR_MAP.items()}


def get_active_account_name() -> str:
    """
    Get the name of the currently active account from config.
    
    Returns:
        Account name (e.g., 'live', 'paper_1', 'paper_2', 'paper_3')
    """
    return config.get('alpaca', 'active_account', default='paper_1')


def get_active_account_dir() -> str:
    """
    Get the directory name for the currently active account.
    
    Returns:
        Account directory name (e.g., 'account_1', 'account_2', etc.)
    """
    account_name = get_active_account_name()
    return ACCOUNT_DIR_MAP.get(account_name, 'account_2')  # Default to paper_1's dir


def get_account_dir(account_name: str) -> str:
    """
    Get the directory name for a specific account.
    
    Args:
        account_name: Account name from config (e.g., 'live', 'paper_1')
        
    Returns:
        Account directory name (e.g., 'account_1', 'account_2', etc.)
    """
    return ACCOUNT_DIR_MAP.get(account_name, 'account_2')


def get_enabled_accounts() -> list:
    """
    Get list of enabled account names.
    
    Returns:
        List of enabled account names (e.g., ['paper_1', 'paper_2'])
    """
    accounts = config.get('alpaca', 'accounts', default={})
    enabled = []
    for name, settings in accounts.items():
        if settings.get('enabled', False):
            enabled.append(name)
    return enabled


def get_account_nickname(account_name: str) -> str:
    """
    Get the display nickname for an account.
    
    Args:
        account_name: Account name from config (e.g., 'live', 'paper_1')
        
    Returns:
        Account nickname (e.g., 'Live Trading', 'Paper 1')
    """
    return config.get('alpaca', 'accounts', account_name, 'nickname', default=account_name)


# For backward compatibility
ALPACA_API_KEY = config.ALPACA_API_KEY
ALPACA_SECRET_KEY = config.ALPACA_SECRET_KEY
ALPACA_BASE_URL = config.ALPACA_BASE_URL
DATA_DIR = config.DATA_DIR
RAW_DATA_DIR = config.RAW_DATA_DIR
PROCESSED_DATA_DIR = config.PROCESSED_DATA_DIR
LOG_DIR = config.LOG_DIR
LOG_FILE = config.LOG_FILE
LOG_LEVEL = config.LOG_LEVEL
TRADE_SYMBOL = config.TRADE_SYMBOL
TRADE_QUANTITY = config.TRADE_QUANTITY

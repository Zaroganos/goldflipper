"""
Configuration Management Module for GoldFlipper

This module provides a centralized configuration management system using a singleton pattern.
It loads settings from a YAML file and provides both object-oriented and traditional access
to configuration values.

The Config class handles:
- Loading configuration from YAML
- Setting up directory structures
- Providing access to configuration values
- Maintaining backward compatibility with existing code
"""

import os
import yaml
import logging
import shutil

# Flag to track if settings file was just created
settings_just_created = False

def reset_settings_created_flag():
    """Reset the settings_just_created flag after successful configuration."""
    global settings_just_created
    settings_just_created = False

def load_config():
    global settings_just_created
    config_path = os.path.join(os.path.dirname(__file__), 'settings.yaml')
    
    # Check if settings.yaml exists, if not, create it from template
    if not os.path.exists(config_path):
        template_path = os.path.join(os.path.dirname(__file__), 'settings_template.yaml')
        
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Neither settings.yaml nor template file found at {template_path}")
            
        try:
            # Copy the template to settings.yaml
            shutil.copy2(template_path, config_path)
            settings_just_created = True
            logging.info(f"Created new settings file from template at {config_path}")
            print(f"\nCreated new settings file from template at {config_path}")
            print(f"Please review and update the settings with your API keys and preferences.")
        except Exception as e:
            raise IOError(f"Error creating settings file from template: {e}")
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML configuration: {e}")

config = load_config()

class Config:
    """
    Singleton configuration class that manages all GoldFlipper settings.
    
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
            cls._instance._setup_paths()
        return cls._instance

    def _load_config(self):
        """
        Load configuration from YAML file.
        
        Attempts to load settings.yaml from the config directory.
        Falls back to empty dict if file is not found or invalid.
        """
        config_path = os.path.join(os.path.dirname(__file__), 'settings.yaml')
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            logging.info(f"Configuration loaded from {config_path}")
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")
            self._config = {}

    def reload(self):
        """Reload configuration from the settings.yaml file."""
        self._load_config()

    def _setup_paths(self):
        """
        Setup absolute paths and create required directories.
        
        Converts relative paths from config to absolute paths and creates
        necessary directories if they don't exist.
        """
        base_dir = os.path.dirname(os.path.dirname(__file__))
        
        # Setup data/log paths with safe defaults when 'paths' missing in settings.yaml
        paths_cfg = self._config.get('paths', {}) if isinstance(self._config, dict) else {}
        self.DATA_DIR = os.path.join(base_dir, paths_cfg.get('data_dir', 'data'))
        self.RAW_DATA_DIR = os.path.join(base_dir, paths_cfg.get('raw_data_dir', 'data/raw'))
        self.PROCESSED_DATA_DIR = os.path.join(base_dir, paths_cfg.get('processed_data_dir', 'data/processed'))
        
        # Setup log paths
        self.LOG_DIR = os.path.join(base_dir, paths_cfg.get('log_dir', 'logs'))
        default_log_file = os.path.join('logs', 'app.log')
        self.LOG_FILE = os.path.join(base_dir, paths_cfg.get('log_file', default_log_file))
        
        # Create directories if they don't exist
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

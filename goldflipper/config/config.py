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

    def _setup_paths(self):
        """
        Setup absolute paths and create required directories.
        
        Converts relative paths from config to absolute paths and creates
        necessary directories if they don't exist.
        """
        base_dir = os.path.dirname(os.path.dirname(__file__))
        
        # Setup data paths
        self.DATA_DIR = os.path.join(base_dir, self._config['paths']['data_dir'])
        self.RAW_DATA_DIR = os.path.join(base_dir, self._config['paths']['raw_data_dir'])
        self.PROCESSED_DATA_DIR = os.path.join(base_dir, self._config['paths']['processed_data_dir'])
        
        # Setup log paths
        self.LOG_DIR = os.path.join(base_dir, self._config['paths']['log_dir'])
        self.LOG_FILE = os.path.join(base_dir, self._config['paths']['log_file'])
        
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

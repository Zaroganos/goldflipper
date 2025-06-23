from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import yaml
import os
from .providers.base import MarketDataProvider
from .providers.marketdataapp_provider import MarketDataAppProvider
from .providers.yfinance_provider import YFinanceProvider
from .providers.alpaca_provider import AlpacaProvider
from .cache import CycleCache
from .errors import *
from goldflipper.utils.display import TerminalDisplay as display
import pandas as pd

class MarketDataManager:
    """Central manager for market data operations"""
    
    def __init__(self, provider: Optional[MarketDataProvider] = None):
        self.logger = logging.getLogger(__name__)
        # Get absolute path to project root (one level up from 'goldflipper' package)
        current_dir = os.path.dirname(os.path.abspath(__file__))  # /market
        package_dir = os.path.dirname(os.path.dirname(current_dir))  # /goldflipper
        project_root = os.path.dirname(package_dir)  # project root
        
        self.config_path = os.path.join(project_root, 'goldflipper', 'config', 'settings.yaml')
        self.config = self._load_config(self.config_path)
        self.cache = CycleCache(self.config)
        self.providers = self._initialize_providers()
        self.provider = provider or self.providers[self.config['primary_provider']]
        
    def _load_config(self, config_path: str) -> dict:
        """Load market data provider configuration"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config['market_data_providers']
        except Exception as e:
            self.logger.error(f"Failed to load config from {config_path}: {str(e)}")
            raise
        
    def _initialize_providers(self) -> Dict[str, MarketDataProvider]:
        """Initialize all enabled providers"""
        providers = {}
        provider_classes = {
            'marketdataapp': MarketDataAppProvider,
            'yfinance': YFinanceProvider,
            'alpaca': AlpacaProvider
        }
        
        for name, settings in self.config['providers'].items():
            if settings.get('enabled', False) and name in provider_classes:
                try:
                    provider_class = provider_classes[name]
                    if name == 'alpaca':
                        providers[name] = provider_class()  # No config_path
                    else:
                        providers[name] = provider_class(self.config_path)
                    self.logger.info(f"Initialized {name} provider")
                except Exception as e:
                    self.logger.error(f"Failed to initialize {name} provider: {str(e)}")
                    
        if not providers:
            raise ValueError("No market data providers were successfully initialized")
                    
        return providers
        
    def _try_providers(self, operation: str, *args) -> Optional[Any]:
        """Try operation with fallback providers"""
        if not self.config['fallback']['enabled']:
            try:
                return getattr(self.provider, operation)(*args)
            except MarketDataError as e:
                self.logger.error(str(e))
                display.error(str(e))
                return None
                
        errors = []
        provider_order = self.config['fallback']['order']
        max_attempts = self.config['fallback']['max_attempts']
        
        for provider_name in provider_order[:max_attempts]:
            if provider_name not in self.providers:
                continue
                
            provider = self.providers[provider_name]
            try:
                result = getattr(provider, operation)(*args)
                if result is not None:
                    return result
            except MarketDataError as e:
                errors.append(str(e))
                continue
                
        self.logger.error(f"All providers failed: {'; '.join(errors)}")
        display.error(f"All providers failed: {'; '.join(errors)}")
        return None
        
    def get_stock_price(self, symbol: str, regular_hours_only: bool = False) -> Optional[float]:
        """Get current stock price with cycle caching
        
        Args:
            symbol: Stock ticker symbol
            regular_hours_only: If True, excludes extended hours data and returns
                               the last primary session close when markets are closed
        """
        try:
            # Include regular_hours_only in cache key to separate cached values
            cache_key = f"stock_price:{symbol}:regular_only_{regular_hours_only}"
            if cached_price := self.cache.get(cache_key):
                return cached_price
                
            pricing_mode = "regular hours only" if regular_hours_only else "including extended hours"
            self.logger.info(f"Fetching stock price for {symbol} ({pricing_mode})")
            price = self._try_providers('get_stock_price', symbol, regular_hours_only)
            
            if price is not None:
                self.cache.set(cache_key, price)
                return price
                
            self.logger.error(f"Failed to get price for {symbol}")
            display.error(f"Failed to get price for {symbol}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting stock price for {symbol}: {str(e)}")
            display.error(f"Error getting stock price for {symbol}: {str(e)}")
            return None
            
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict[str, float]]:
        """Get option quote data with cycle caching"""
        try:
            cache_key = f"option_quote:{contract_symbol}"
            if cached_quote := self.cache.get(cache_key):
                return cached_quote
                
            quote = self._try_providers('get_option_quote', contract_symbol)
            
            if quote is not None and not quote.empty:
                result = {
                    'premium': quote.iloc[0].get('last', 0.0),
                    'bid': quote.iloc[0].get('bid', 0.0),
                    'ask': quote.iloc[0].get('ask', 0.0),
                    'delta': quote.iloc[0].get('delta', 0.0),
                    'theta': quote.iloc[0].get('theta', 0.0)
                }
                self.cache.set(cache_key, result)
                return result
                
            self.logger.error(f"No option quote available for {contract_symbol}")
            display.error(f"No option quote available for {contract_symbol}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting option quote for {contract_symbol}: {str(e)}")
            display.error(f"Error getting option quote for {contract_symbol}: {str(e)}")
            return None
        
    def start_new_cycle(self):
        """Start a new market data cycle, clearing the cache"""
        self.logger.info("Starting new market data cycle")
        self.cache.new_cycle()
        
    def get_option_chain(self, symbol: str, expiration_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """Get option chain data with cycle caching"""
        try:
            cache_key = f"option_chain:{symbol}:{expiration_date or 'nearest'}"
            if cached_chain := self.cache.get(cache_key):
                return cached_chain
                
            self.logger.info(f"Fetching option chain for {symbol}")
            chain = self._try_providers('get_option_chain', symbol, expiration_date)
            
            if chain is not None:
                self.cache.set(cache_key, chain)
                return chain
                
            self.logger.error(f"Failed to get option chain for {symbol}")
            display.error(f"Failed to get option chain for {symbol}")
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
            
        except Exception as e:
            self.logger.error(f"Error getting option chain for {symbol}: {str(e)}")
            display.error(f"Error getting option chain for {symbol}: {str(e)}")
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()} 
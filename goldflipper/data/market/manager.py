from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
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
from goldflipper.utils.exe_utils import get_settings_path

class MarketDataManager:
    """Central manager for market data operations"""
    
    def __init__(self, provider: Optional[MarketDataProvider] = None):
        self.logger = logging.getLogger(__name__)
        # Use exe-aware path for Nuitka compatibility
        # CRITICAL: In Nuitka onefile mode, __file__ points to temp extraction,
        # but settings.yaml should be read from next to the exe
        self.config_path = str(get_settings_path())
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
        
    def get_stock_price(self, symbol: str) -> Optional[float]:
        """Get current stock price with cycle caching"""
        try:
            cache_key = f"stock_price:{symbol}"
            if cached_price := self.cache.get(cache_key):
                return cached_price
                
            self.logger.info(f"Fetching stock price for {symbol}")
            price = self._try_providers('get_stock_price', symbol)
            
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
                row = quote.iloc[0]
                bid = float(row.get('bid', 0.0) or 0.0)
                ask = float(row.get('ask', 0.0) or 0.0)
                last = float(row.get('last', 0.0) or 0.0)
                
                # Calculate mid price
                mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0
                
                result = {
                    'bid': bid,
                    'ask': ask,
                    'last': last,
                    'mid': mid,
                    'premium': last,  # Keep for backward compatibility, but will be replaced
                    'delta': float(row.get('delta', 0.0) or 0.0),
                    'theta': float(row.get('theta', 0.0) or 0.0),
                    'volume': float(row.get('volume', 0.0) or 0.0),
                    'open_interest': float(row.get('open_interest', 0.0) or 0.0)
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
            
    def get_option_expirations(self, symbol: str) -> Optional[list]:
        """Get available option expirations with cycle caching and fallback"""
        try:
            cache_key = f"expirations:{symbol}"
            if cached := self.cache.get(cache_key):
                return cached

            expirations = self._try_providers('get_option_expirations', symbol)
            if expirations:
                self.cache.set(cache_key, expirations)
                return expirations
            return []
        except Exception as e:
            self.logger.error(f"Error getting expirations for {symbol}: {str(e)}")
            return []

    def get_next_earnings_date(self, symbol: str):
        """Get the next upcoming earnings date for a symbol, if supported by the provider.

        Returns a datetime.date or None if unavailable.
        """
        try:
            cache_key = f"earnings_next:{symbol}"
            if cached := self.cache.get(cache_key):
                return cached

            # Prefer MarketDataAppProvider if initialized, since it exposes earnings.
            provider = self.providers.get('marketdataapp')
            if provider is None:
                self.logger.info("MarketDataApp provider not available; earnings lookup skipped")
                return None

            if not hasattr(provider, 'get_next_earnings_date'):
                self.logger.info("Selected provider does not support earnings endpoint; skipping earnings validation")
                return None

            self.logger.info(f"Fetching next earnings date for {symbol}")
            next_date = provider.get_next_earnings_date(symbol)

            if next_date is not None:
                self.cache.set(cache_key, next_date)

            return next_date
        except Exception as e:
            self.logger.error(f"Error getting next earnings date for {symbol}: {str(e)}")
            return None
        
    def start_new_cycle(self):
        """Start a new market data cycle, clearing the cache"""
        self.logger.info("Starting new market data cycle")
        self.cache.new_cycle()
    
    def get_previous_close(self, symbol: str) -> Optional[float]:
        """
        Get the previous trading day's closing price for a symbol.
        
        Uses historical data provider with caching.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Previous close price or None if unavailable
        """
        try:
            cache_key = f"previous_close:{symbol}"
            if cached := self.cache.get(cache_key):
                return cached
            
            self.logger.info(f"Fetching previous close for {symbol}")
            
            # Get last 5 days of data to ensure we have previous close
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            historical = self._try_providers(
                'get_historical_data',
                symbol,
                start_date,
                end_date,
                '1d'  # Daily interval
            )
            
            if historical is not None and not historical.empty and len(historical) >= 2:
                # Get the second-to-last row's close
                # (last row is current/partial day)
                close_col = 'close' if 'close' in historical.columns else 'Close'
                if close_col in historical.columns:
                    previous_close = float(historical[close_col].iloc[-2])
                    self.cache.set(cache_key, previous_close)
                    return previous_close
            
            self.logger.warning(f"Could not get previous close for {symbol}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting previous close for {symbol}: {str(e)}")
            return None
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import yaml
import os
from .providers.base import MarketDataProvider
from .providers.marketdataapp_provider import MarketDataAppProvider
from .providers.yfinance_provider import YFinanceProvider
from .providers.alpaca_provider import AlpacaProvider
from .symbol_mappings import translate_symbol
from .cache import CycleCache
from .errors import *
from goldflipper.utils.display import TerminalDisplay as display
import pandas as pd
from sqlalchemy import text as sql_text
from goldflipper.database.connection import get_db_connection
from .providers.vix_utils_adapter import (
    get_vix_futures_price_for_option_expiry_on_date,
)

class MarketDataManager:
    """Central manager for market data operations"""
    
    def __init__(self, provider: Optional[MarketDataProvider] = None):
        self.logger = logging.getLogger(__name__)
        # Get absolute path to project root (one level up from 'goldflipper' package)
        current_dir = os.path.dirname(os.path.abspath(__file__))  # /market
        package_dir = os.path.dirname(os.path.dirname(current_dir))  # /goldflipper
        project_root = os.path.dirname(package_dir)  # project root
        
        # Load provider config strictly from DuckDB (no YAML)
        self.config = self._load_config(None)
        self.cache = CycleCache(self.config)
        self.providers = self._initialize_providers()
        self.provider = provider or self.providers[self.config['primary_provider']]
        
    def _load_config(self, config_path: str) -> dict:
        """Load market data provider configuration from DuckDB only (no YAML fallbacks)."""
        try:
            # Read flattened settings from DB
            with get_db_connection() as session:
                rows = session.execute(
                    sql_text("SELECT key, value FROM user_settings WHERE category = :cat"),
                    {"cat": "market_data_providers"}
                ).fetchall()

            if not rows:
                raise KeyError("No 'market_data_providers' settings found in DuckDB.user_settings")

            import json
            cfg: Dict[str, Any] = {}
            for key, raw_val in rows:
                # Decode JSON values when possible; keep raw otherwise
                val: Any = raw_val
                if isinstance(raw_val, str):
                    try:
                        val = json.loads(raw_val)
                    except Exception:
                        pass

                # Support nested dot-keys: providers.yfinance.enabled -> cfg['providers']['yfinance']['enabled']
                parts = key.split('.') if key else []
                if not parts:
                    # If key is empty, merge object if applicable
                    if isinstance(val, dict):
                        cfg.update(val)
                    continue
                cursor = cfg
                for part in parts[:-1]:
                    cursor = cursor.setdefault(part, {})
                cursor[parts[-1]] = val

            # Validate required top-level keys
            missing: List[str] = []
            for req in ("primary_provider", "providers", "fallback", "expiration_provider"):
                if req not in cfg or (req in ("providers", "fallback") and not isinstance(cfg.get(req), dict)):
                    missing.append(req)
            if missing:
                raise KeyError(
                    f"Missing required market_data_providers keys in DB: {missing}. Present keys: {list(cfg.keys())}"
                )

            return cfg
        except Exception as e:
            self.logger.error(f"Failed to load market data provider config from DB: {e}")
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
                    if name == 'marketdataapp':
                        providers[name] = provider_class(settings)
                    elif name == 'yfinance':
                        providers[name] = provider_class()
                    elif name == 'alpaca':
                        providers[name] = provider_class()
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

    def get_available_expirations(self, symbol: str) -> Optional[list[str]]:
        """Get available option expiration dates for a symbol using configured provider.

        Selection is controlled by config['expiration_provider'] with fallback order
        under config['fallback'] when enabled.
        """
        try:
            provider_name = self.config.get('expiration_provider', 'yfinance')
            # Try chosen provider first
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                try:
                    sym = translate_symbol(provider_name, symbol)
                    expirations = provider.get_available_expirations(sym)
                    if expirations:
                        return expirations
                except Exception as e:
                    self.logger.warning(f"Expiration provider {provider_name} failed: {e}")

            # Fallback if enabled: try other providers that implement the method
            if self.config['fallback']['enabled']:
                for name in self.config['fallback']['order']:
                    if name == provider_name:
                        continue
                    if name not in self.providers:
                        continue
                    provider = self.providers[name]
                    if not hasattr(provider, 'get_available_expirations'):
                        continue
                    try:
                        sym = translate_symbol(name, symbol)
                        expirations = provider.get_available_expirations(sym)
                        if expirations:
                            return expirations
                    except Exception:
                        continue

            self.logger.error(f"No expirations available for {symbol} from any provider")
            return None
        except Exception as e:
            self.logger.error(f"Error getting expirations for {symbol}: {e}")
            return None
        
    def start_new_cycle(self):
        """Start a new market data cycle, clearing the cache"""
        self.logger.info("Starting new market data cycle")
        self.cache.new_cycle()
        
    def get_option_chain(self, symbol: str, expiration_date: Optional[str] = None, date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """Get option chain data with cycle caching
        
        Args:
            symbol: Underlying symbol
            expiration_date: Filter by expiration date (YYYY-MM-DD)
            date: Historical date for option chain (YYYY-MM-DD). If None, gets current data
            
        Returns:
            Dictionary with 'calls' and 'puts' DataFrames
        """
        try:
            cache_key = f"option_chain:{symbol}:{expiration_date or 'nearest'}:{date or 'current'}"
            if cached_chain := self.cache.get(cache_key):
                return cached_chain
                
            self.logger.info(f"Fetching option chain for {symbol}, expiry {expiration_date}, date {date}")
            chain = self._try_providers('get_option_chain', symbol, expiration_date, date)
            
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

    # Removed get_vix_futures_price (we only use provider spot/futures or Yahoo chart fallback)

    def get_vix_futures_price_on_date(self, vix_option_expiration: Optional[str], ref_date: Optional[str]) -> Optional[float]:
        """Get the VIX futures price for a given option expiry as of a reference date (YYYY-MM-DD).

        Strategy:
        1) Provider-based retrieval via yfinance for VX=F (front-month) close on ref_date.
        If provider data unavailable, return None.
        """
        try:
            if not vix_option_expiration or not ref_date:
                return None
            from datetime import datetime as _dt
            exp_date = _dt.strptime(vix_option_expiration, '%Y-%m-%d').date()
            rdate = _dt.strptime(ref_date, '%Y-%m-%d').date()
            # 1) Try yfinance provider for VX=F close on ref_date
            self.logger.info(f"VIX VX=F Friday close request: expiry={vix_option_expiration}, ref_date={ref_date}")
            try:
                yf_provider = self.providers.get('yfinance')
                if yf_provider and hasattr(yf_provider, 'get_historical_data'):
                    # Fetch a small window including ref_date
                    from datetime import timedelta as _td
                    start = _dt.combine(rdate - _td(days=2), _dt.min.time())
                    end = _dt.combine(rdate + _td(days=1), _dt.min.time())
                    df = yf_provider.get_historical_data('VX=F', start, end, interval='1d')
                    self.logger.info(f"VX=F yfinance result empty={df is None or getattr(df,'empty',True)}")
                    if df is not None and not df.empty:
                        try:
                            self.logger.info(f"VX=F yfinance rows={len(df)} cols={list(df.columns)}")
                        except Exception:
                            pass
                        # Pick the last row up to ref_date
                        # Ensure index is datetime
                        try:
                            df_idx = df
                            if 'timestamp' in df.columns:
                                df_idx = df.set_index('timestamp')
                            df_idx.index = pd.to_datetime(df_idx.index)
                            subset = df_idx.loc[df_idx.index.date <= rdate]
                            self.logger.info(f"VX=F subset rows up to {rdate}: {len(subset)}")
                            if subset is not None and not subset.empty:
                                if 'close' in subset.columns:
                                    val = float(subset.iloc[-1]['close'])
                                    self.logger.info(f"VX=F close (lowercase) on/before {rdate}: {val}")
                                    return val
                                if 'Close' in subset.columns:
                                    val = float(subset.iloc[-1]['Close'])
                                    self.logger.info(f"VX=F Close on/before {rdate}: {val}")
                                    return val
                        except Exception:
                            pass
            except Exception:
                pass

            # No provider data
            return None
        except Exception as e:
            self.logger.warning(f"Failed to get VIX futures price on {ref_date} for {vix_option_expiration}: {e}")
            return None
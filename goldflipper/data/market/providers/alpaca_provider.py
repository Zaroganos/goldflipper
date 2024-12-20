from datetime import datetime
import pandas as pd
from typing import Optional, Dict, Any, Callable, Set
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
import yaml
import os
import logging
import asyncio
import time
from threading import Lock as ThreadLock
from collections import OrderedDict
from asyncio import Lock as AsyncLock

from .base import MarketDataProvider

class LRUCache:
    """Least Recently Used (LRU) cache implementation"""
    
    def __init__(self, max_size: int):
        self.cache = OrderedDict()
        self.max_size = max_size
        self._lock = AsyncLock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache and move to end (most recently used)"""
        async with self._lock:
            if key not in self.cache:
                return None
            
            value, expiry = self.cache.pop(key)
            if expiry < time.time():
                return None
                
            self.cache[key] = (value, expiry)  # Move to end
            return value
    
    async def set(self, key: str, value: Any, ttl: int):
        """Add item to cache with expiration"""
        async with self._lock:
            if len(self.cache) >= self.max_size:
                # Remove oldest item
                self.cache.popitem(last=False)
            
            expiry = time.time() + ttl
            self.cache[key] = (value, expiry)

class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self, max_requests: int, time_window: int, buffer_percent: float = 10):
        self.max_requests = int(max_requests * (1 - buffer_percent / 100))
        self.time_window = time_window
        self.requests = []
        self._lock = AsyncLock()
    
    async def acquire(self):
        """Wait if we're over the rate limit"""
        async with self._lock:
            now = time.time()
            # Remove old requests
            self.requests = [t for t in self.requests if now - t < self.time_window]
            
            if len(self.requests) >= self.max_requests:
                # Wait until we can make another request
                wait_time = self.requests[0] + self.time_window - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    
            self.requests.append(now)

class AlpacaProvider(MarketDataProvider):
    """Alpaca implementation of market data provider"""
    
    def __init__(self):
        # Load settings from YAML
        self.settings = self._load_settings()
        
        # Get credentials from settings
        self.api_key = self.settings['alpaca']['api_key']
        self.secret_key = self.settings['alpaca']['secret_key']
        self.base_url = self.settings['alpaca']['base_url']
        
        # Use v2 endpoints for data and streaming
        self.data_url = 'https://data.alpaca.markets'
        self.stream_url = 'wss://stream.data.alpaca.markets/v2'
        
        # Initialize clients
        self.data_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        
        self.trading_client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=True,
            url_override=self.base_url
        )
        
        # WebSocket state management
        self.stream_client = None
        self._cache = {}  # Simple memory cache
        self._latest_data = {}  # Store latest data from WebSocket
        self._ws_connected = False
        self._ws_subscribed_symbols: Set[str] = set()
        self._ws_last_heartbeat = time.time()
        self._ws_lock = ThreadLock()
        self._reconnect_task = None
        self._health_check_task = None
        
        # Initialize cache and rate limiter
        provider_settings = self.settings['market_data_providers']['providers']['alpaca']
        cache_settings = provider_settings['cache']
        rate_limit_settings = provider_settings['rate_limiting']
        
        if cache_settings['enabled']:
            self.cache = LRUCache(max_size=cache_settings['max_size'])
        else:
            self.cache = None
            
        if rate_limit_settings['enabled']:
            self.rate_limiter = RateLimiter(
                max_requests=rate_limit_settings['quotes_per_minute'],
                time_window=60,  # 1 minute
                buffer_percent=rate_limit_settings['buffer_percent']
            )
        else:
            self.rate_limiter = None
    
    def _load_settings(self) -> dict:
        """Load settings from YAML file"""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        config_path = os.path.join(project_root, 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    async def _init_websocket(self):
        """Initialize WebSocket connection"""
        try:
            if self.stream_client is None:
                self.stream_client = StockDataStream(
                    api_key=self.api_key,
                    secret_key=self.secret_key
                )
                
                # Set up handlers
                self.stream_client.subscribe_trades(self._handle_trade)
                self.stream_client.subscribe_quotes(self._handle_quote)
                self.stream_client.subscribe_bars(self._handle_bar)
                
                # Connect
                await self.stream_client._connect()
                self._ws_connected = True
                self._ws_last_heartbeat = time.time()
                logging.info("AlpacaProvider WebSocket connected successfully")
                
        except Exception as e:
            self._ws_connected = False
            logging.error(f"Failed to initialize WebSocket: {str(e)}")
            raise
    
    async def _connect_with_retry(self, max_retries: int = 3, retry_delay: int = 2):
        """Connect to WebSocket with retry logic"""
        for attempt in range(max_retries):
            try:
                await self.stream_client._connect()
                self._ws_connected = True
                self._ws_last_heartbeat = time.time()
                logging.info("AlpacaProvider WebSocket connected successfully")
                
                # Subscribe to symbols
                if self._ws_subscribed_symbols:
                    await self._resubscribe_symbols()
                
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning(f"WebSocket connection attempt {attempt + 1} failed: {str(e)}")
                    await asyncio.sleep(retry_delay)
                else:
                    raise
    
    async def _monitor_connection_health(self):
        """Monitor WebSocket connection health"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self._ws_connected:
                    # Check last heartbeat
                    if time.time() - self._ws_last_heartbeat > 60:  # No heartbeat for 1 minute
                        logging.warning("WebSocket connection appears stale, initiating reconnect")
                        await self._reconnect()
                        
            except Exception as e:
                logging.error(f"Error in connection health monitor: {str(e)}")
    
    async def _reconnect(self):
        """Handle WebSocket reconnection"""
        async with self._ws_lock:
            try:
                self._ws_connected = False
                if self.stream_client:
                    try:
                        await self.stream_client.stop()
                    except:
                        pass
                
                self.stream_client = None
                await self._init_websocket()
                
            except Exception as e:
                logging.error(f"Failed to reconnect WebSocket: {str(e)}")
    
    async def _resubscribe_symbols(self):
        """Resubscribe to previously subscribed symbols"""
        if self._ws_subscribed_symbols and self._ws_connected:
            try:
                await self.stream_client.subscribe_trades(list(self._ws_subscribed_symbols))
                await self.stream_client.subscribe_quotes(list(self._ws_subscribed_symbols))
                await self.stream_client.subscribe_bars(list(self._ws_subscribed_symbols))
                logging.info(f"Resubscribed to {len(self._ws_subscribed_symbols)} symbols")
            except Exception as e:
                logging.error(f"Error resubscribing to symbols: {str(e)}")
    
    async def subscribe_symbol(self, symbol: str):
        """Subscribe to updates for a specific symbol"""
        if symbol not in self._ws_subscribed_symbols and self._ws_connected:
            try:
                await self.stream_client.subscribe_trades([symbol])
                await self.stream_client.subscribe_quotes([symbol])
                await self.stream_client.subscribe_bars([symbol])
                self._ws_subscribed_symbols.add(symbol)
                logging.info(f"Subscribed to {symbol}")
            except Exception as e:
                logging.error(f"Error subscribing to {symbol}: {str(e)}")
    
    async def _handle_trade(self, trade):
        """Handle trade updates"""
        try:
            symbol = trade.symbol
            self._latest_data[symbol] = {
                'last_trade': {
                    'price': trade.price,
                    'size': trade.size,
                    'timestamp': trade.timestamp
                }
            }
            self._ws_last_heartbeat = time.time()
            logging.debug(f"Trade update for {symbol}: {trade}")
        except Exception as e:
            logging.error(f"Error handling trade: {str(e)}")
    
    async def _handle_quote(self, quote):
        """Handle quote updates"""
        try:
            symbol = quote.symbol
            self._latest_data[symbol] = {
                'quote': {
                    'bid': quote.bid_price,
                    'ask': quote.ask_price,
                    'bid_size': quote.bid_size,
                    'ask_size': quote.ask_size,
                    'timestamp': quote.timestamp
                }
            }
            self._ws_last_heartbeat = time.time()
            logging.debug(f"Quote update for {symbol}: {quote}")
        except Exception as e:
            logging.error(f"Error handling quote: {str(e)}")
    
    async def _handle_bar(self, bar):
        """Handle bar updates"""
        try:
            symbol = bar.symbol
            self._latest_data[symbol] = {
                'bar': {
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'timestamp': bar.timestamp
                }
            }
            self._ws_last_heartbeat = time.time()
            logging.debug(f"Bar update for {symbol}: {bar}")
        except Exception as e:
            logging.error(f"Error handling bar: {str(e)}")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._health_check_task:
            self._health_check_task.cancel()
            
        if self.stream_client:
            try:
                await self.stream_client.stop()
            except:
                pass
            
        self.stream_client = None
        self._ws_connected = False
    
    async def get_stock_price(self, symbol: str) -> float:
        """Get current stock price for a symbol"""
        try:
            # Normalize symbol
            symbol = symbol.upper()
            
            # Try cache first
            if self.cache:
                cache_key = f"price_{symbol}"
                price = await self.cache.get(cache_key)
                if price is not None:
                    return price
            
            # Check rate limit
            if self.rate_limiter:
                await self.rate_limiter.acquire()
            
            # Get latest quote using REST API
            try:
                request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])  # Pass as list
                response = self.data_client.get_stock_latest_quote(request)
                
                if not response or symbol not in response:
                    raise ValueError(f"No quote data returned for {symbol}")
                    
                quote = response[symbol]
                
                # Access the quote attributes correctly
                ask_price = float(quote.ask_price) if quote.ask_price is not None else None
                bid_price = float(quote.bid_price) if quote.bid_price is not None else None
                
                # Calculate mid price from bid/ask
                if ask_price is not None and bid_price is not None:
                    price = (ask_price + bid_price) / 2
                else:
                    price = ask_price if ask_price is not None else bid_price
                    
                if price is None:
                    raise ValueError(f"No valid price data for {symbol}")
                
                # Cache the result
                if self.cache:
                    ttl = self.settings['market_data_providers']['providers']['alpaca']['cache']['ttl']['quotes']
                    await self.cache.set(cache_key, price, ttl)
                
                return price
                
            except Exception as e:
                logging.error(f"Error getting quote for {symbol}: {str(e)}")
                
                # Try WebSocket data as fallback
                if symbol in self._latest_data:
                    quote = self._latest_data[symbol].get('quote')
                    if quote:
                        ask = float(quote.get('ask_price', 0))
                        bid = float(quote.get('bid_price', 0))
                        if ask > 0 and bid > 0:
                            return (ask + bid) / 2
                        return ask if ask > 0 else bid
                
                raise
                
        except Exception as e:
            logging.error(f"Error getting stock price for {symbol}: {str(e)}")
            raise
    
    # Existing Historical API methods remain the same
    def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1Min"
    ) -> pd.DataFrame:
        """Get historical price data using Alpaca"""
        # Check cache first
        cache_key = f"{symbol}_{start_date}_{end_date}_{interval}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        # Convert interval string to Alpaca TimeFrame
        timeframe = self._convert_interval(interval)
        
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start_date,
            end=end_date
        )
        
        try:
            bars = self.data_client.get_stock_bars(request)
            df = bars.df
            
            # Cache the result
            self._cache[cache_key] = df
            return df
            
        except Exception as e:
            logging.error(f"Error getting historical data for {symbol}: {str(e)}")
            return pd.DataFrame()
            
    def get_option_chain(
        self,
        symbol: str,
        expiration_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Get option chain data using Alpaca"""
        try:
            request = GetOptionContractsRequest(
                underlying_symbols=[symbol],
                expiration_date=expiration_date
            )
            options = self.trading_client.get_option_contracts(request)
            
            # Separate calls and puts
            calls = pd.DataFrame([opt for opt in options if opt.type == 'call'])
            puts = pd.DataFrame([opt for opt in options if opt.type == 'put'])
            
            return {
                'calls': calls,
                'puts': puts
            }
            
        except Exception as e:
            logging.error(f"Error getting option chain for {symbol}: {str(e)}")
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
    
    def _convert_interval(self, interval: str) -> TimeFrame:
        """Convert common interval strings to Alpaca TimeFrame"""
        interval_map = {
            "1m": TimeFrame.Minute,
            "5m": TimeFrame.Minute * 5,
            "15m": TimeFrame.Minute * 15,
            "1h": TimeFrame.Hour,
            "1d": TimeFrame.Day
        }
        return interval_map.get(interval.lower(), TimeFrame.Minute) 
    
    def get_option_greeks(self, option_symbol: str) -> Dict[str, float]:
        """Get option Greeks from Alpaca"""
        # Alpaca doesn't provide Greeks directly, so we'll return empty values
        return {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
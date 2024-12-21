from datetime import datetime
import pandas as pd
from typing import Optional, Dict, Any, Callable, Set
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest, 
    StockLatestQuoteRequest,
    OptionBarsRequest,
    OptionTradesRequest,
    OptionLatestQuoteRequest,
    OptionLatestTradeRequest,
    OptionSnapshotRequest,
    OptionChainRequest
)
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from alpaca.data.live.option import OptionDataStream
from alpaca.data.enums import DataFeed
import yaml
import os
import logging
import asyncio
import time
import json
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
    
    COLUMN_MAPPING = {
        'symbol': 'symbol',
        'strike_price': 'strike',
        'expiration_date': 'expiration',
        'last_price': 'last',
        'bid_price': 'bid',
        'ask_price': 'ask',
        'volume': 'volume',
        'open_interest': 'open_interest',
        'implied_volatility': 'implied_volatility',
        'in_the_money': 'in_the_money'
    }
    
    def __init__(self):
        # Load settings from YAML
        self.settings = self._load_settings()
        
        # Get credentials from settings
        self.api_key = self.settings['alpaca']['api_key']
        self.secret_key = self.settings['alpaca']['secret_key']
        self.base_url = self.settings['alpaca']['base_url']
        
        # Use v2 endpoints for data and streaming
        self.data_url = 'https://data.alpaca.markets'
        self.stream_url = 'wss://stream.data.alpaca.markets/v2/'
        
        # Initialize clients
        self.stock_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        
        self.option_client = OptionHistoricalDataClient(
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
        
        # Initialize WebSocket for options
        self.option_stream = OptionDataStream(
            api_key=self.api_key,
            secret_key=self.secret_key,
            feed=DataFeed.IEX
        )
        
        # Store latest data from WebSocket
        self._latest_option_data = {}
        
        # Set up stream handlers
        self.option_stream.subscribe_trades(self._handle_option_trade)
        self.option_stream.subscribe_quotes(self._handle_option_quote)
    
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
                # Initialize both stock and option streams
                self.stream_client = StockDataStream(
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                    feed=DataFeed.SIP
                )
                
                self.option_stream = OptionDataStream(
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                    feed=DataFeed.IEX
                )
                
                logging.debug("Setting up WebSocket handlers...")
                
                # Stock data handlers
                async def stock_handler(data):
                    if 'trade' in data:
                        await self._handle_trade(data)
                    elif 'quote' in data:
                        await self._handle_quote(data)
                    elif 'bar' in data:
                        await self._handle_bar(data)
                    logging.debug(f"Received stock data: {data}")
                
                # Option data handlers
                async def option_handler(data):
                    logging.debug(f"Received option data: {data}")
                    if 'trade' in data:
                        await self._handle_option_trade(data)
                    elif 'quote' in data:
                        await self._handle_option_quote(data)
                
                # Set up handlers
                self.stream_client.subscribe_trades(stock_handler)
                self.stream_client.subscribe_quotes(stock_handler)
                self.stream_client.subscribe_bars(stock_handler)
                
                self.option_stream.subscribe_trades(option_handler)
                self.option_stream.subscribe_quotes(option_handler)
                
                # Start both connections
                logging.debug("Starting WebSocket connections...")
                self._stock_ws_task = asyncio.create_task(self.stream_client._run_forever())
                self._option_ws_task = asyncio.create_task(self.option_stream._run_forever())
                
                # Wait a moment for connections to establish
                await asyncio.sleep(1)
                
                self._ws_connected = True
                self._ws_last_heartbeat = time.time()
                logging.info("AlpacaProvider WebSocket connected successfully")
                
        except Exception as e:
            self._ws_connected = False
            logging.error(f"Failed to initialize WebSocket: {str(e)}")
            raise
    
    async def _maintain_connection(self):
        """Maintain WebSocket connection"""
        while True:
            try:
                # Keep the connection alive
                while True:
                    try:
                        message = await self.stream_client._ws.recv()
                        logging.debug(f"Received message: {message}")
                        # Process message if needed
                    except Exception as e:
                        logging.error(f"Error in WebSocket receive: {str(e)}")
                        break
                
            except Exception as e:
                logging.error(f"WebSocket connection error: {str(e)}")
                self._ws_connected = False
                
                # Try to reconnect
                try:
                    await self.stream_client._connect()
                    
                    # Re-authenticate
                    auth_message = [
                        {
                            "action": "auth",
                            "key": self.api_key,
                            "secret": self.secret_key
                        }
                    ]
                    await self.stream_client._ws.send(json.dumps(auth_message))
                    await self.stream_client._ws.recv()  # Wait for auth response
                    
                    self._ws_connected = True
                    
                    # Resubscribe to symbols
                    for symbol in self._ws_subscribed_symbols:
                        await self._resubscribe_symbol(symbol)
                except Exception as reconnect_error:
                    logging.error(f"Failed to reconnect: {str(reconnect_error)}")
                    
            await asyncio.sleep(1)  # Wait before retry
    
    async def _resubscribe_symbol(self, symbol: str):
        """Resubscribe to a symbol after reconnection"""
        subscription_message = [
            {
                "action": "subscribe",
                "trades": [symbol],
                "quotes": [symbol],
                "bars": [symbol]
            }
        ]
        await self.stream_client._ws.send(json.dumps(subscription_message))
    
    async def subscribe_symbol(self, symbol: str):
        """Subscribe to updates for a specific symbol"""
        if symbol not in self._ws_subscribed_symbols and self._ws_connected:
            try:
                logging.debug(f"Subscribing to {symbol}...")
                
                # Subscribe using SDK methods
                self.stream_client.subscribe_trades(self._handle_trade, symbol)
                self.stream_client.subscribe_quotes(self._handle_quote, symbol)
                self.stream_client.subscribe_bars(self._handle_bar, symbol)
                
                self._ws_subscribed_symbols.add(symbol)
                logging.info(f"Subscribed to {symbol}")
            except Exception as e:
                logging.error(f"Error subscribing to {symbol}: {str(e)}")
    
    async def _handle_trade(self, trade):
        """Handle trade updates"""
        try:
            logging.debug(f"Received trade data: {trade}")
            
            symbol = trade.symbol
            self._latest_data[symbol] = {
                'last_trade': {
                    'price': trade.price,
                    'size': trade.size,
                    'timestamp': trade.timestamp
                }
            }
            self._ws_last_heartbeat = time.time()
            logging.debug(f"Processed trade for {symbol}: {self._latest_data[symbol]}")
        except Exception as e:
            logging.error(f"Error handling trade: {str(e)}", exc_info=True)
    
    async def _handle_quote(self, quote):
        """Handle quote updates"""
        try:
            logging.debug(f"Received quote data: {quote}")
            
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
            logging.debug(f"Processed quote for {symbol}: {self._latest_data[symbol]}")
        except Exception as e:
            logging.error(f"Error handling quote: {str(e)}")
    
    async def _handle_bar(self, bar):
        """Handle bar updates"""
        try:
            logging.debug(f"Received bar data: {bar}")
            
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
            logging.debug(f"Processed bar for {symbol}: {bar}")
        except Exception as e:
            logging.error(f"Error handling bar: {str(e)}")
    
    async def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, '_ws_task'):
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            
        if self.stream_client:
            await self.stream_client.close()
            
        self.stream_client = None
        self._ws_connected = False
    
    async def get_stock_price(self, symbol: str) -> float:
        """Get current stock price for a symbol"""
        try:
            # Normalize symbol
            symbol = symbol.upper()
            
            # Subscribe to WebSocket updates for this symbol
            await self.subscribe_symbol(symbol)
            
            # Try WebSocket data first
            if symbol in self._latest_data:
                logging.debug(f"Using WebSocket data for {symbol}: {self._latest_data[symbol]}")
                
                # Try quote data first
                quote = self._latest_data[symbol].get('quote')
                if quote:
                    ask = float(quote.get('ask_price', 0))
                    bid = float(quote.get('bid_price', 0))
                    if ask > 0 and bid > 0:
                        price = (ask + bid) / 2
                        logging.debug(f"Using WebSocket quote for {symbol}: bid={bid}, ask={ask}, mid={price}")
                        return price
                
                # Try last trade if quote isn't available
                trade = self._latest_data[symbol].get('last_trade')
                if trade:
                    price = float(trade.get('price', 0))
                    if price > 0:
                        logging.debug(f"Using WebSocket trade for {symbol}: price={price}")
                        return price
            
            # Fallback to REST API
            logging.debug(f"No WebSocket data available for {symbol}, falling back to REST API")
            
            request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            response = self.stock_client.get_stock_latest_quote(request)
            
            logging.debug(f"REST API response for {symbol}: {response}")
            
            if not response or symbol not in response:
                raise ValueError(f"No quote data returned for {symbol}")
            
            quote = response[symbol]
            bid_price = float(quote.bid_price) if quote.bid_price is not None else None
            ask_price = float(quote.ask_price) if quote.ask_price is not None else None
            
            # Use bid price if ask is 0 or None
            if ask_price is None or ask_price == 0:
                price = bid_price
            else:
                price = (ask_price + bid_price) / 2
            
            if price is None or price == 0:
                raise ValueError(f"No valid price data for {symbol}")
            
            logging.debug(f"Calculated price for {symbol}: {price}")
            return price
            
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
            bars = self.stock_client.get_stock_bars(request)
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
        """Get option chain data using WebSocket data with REST API fallback"""
        try:
            # Try WebSocket data first
            chain_data = []
            for option_symbol, data in self._latest_option_data.items():
                if symbol in option_symbol:  # Basic filter for underlying
                    quote = data.get('quote', {})
                    trade = data.get('trade', {})
                    
                    # Extract expiry from option symbol
                    symbol_expiry = self._extract_expiry(option_symbol)
                    
                    # Skip if expiration_date is specified and doesn't match
                    if expiration_date and symbol_expiry != expiration_date:
                        continue
                    
                    chain_data.append({
                        'symbol': option_symbol,
                        'strike': self._extract_strike(option_symbol),
                        'expiration': symbol_expiry,
                        'type': 'call' if 'C' in option_symbol else 'put',
                        'bid': quote.get('bid_price', 0.0),
                        'ask': quote.get('ask_price', 0.0),
                        'last': trade.get('price', 0.0),
                        'volume': trade.get('size', 0),
                        'open_interest': 0,  # Not available in real-time
                        'implied_volatility': 0.0  # Not available in real-time
                    })
            
            contracts_df = pd.DataFrame(chain_data)
            
            # If WebSocket data is empty, fall back to REST API
            if contracts_df.empty:
                logging.debug(f"No WebSocket data available for {symbol} options, falling back to REST API")
                return self._get_option_chain_rest(symbol, expiration_date)
            
            # Separate calls and puts
            calls = contracts_df[contracts_df['type'] == 'call']
            puts = contracts_df[contracts_df['type'] == 'put']
            
            return {
                'calls': self.standardize_columns(calls),
                'puts': self.standardize_columns(puts)
            }
            
        except Exception as e:
            logging.error(f"Error getting option chain for {symbol}: {str(e)}")
            # Try REST API as fallback
            return self._get_option_chain_rest(symbol, expiration_date)

    def _get_option_chain_rest(
        self,
        symbol: str,
        expiration_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Fallback method to get option chain using REST API"""
        try:
            chain_data = []
            page_token = None
            
            while True:
                request = OptionChainRequest(
                    underlying_symbol=symbol,
                    expiration_date=datetime.strptime(expiration_date, '%Y-%m-%d').date() if expiration_date else None,
                    page_token=page_token
                )
                
                response = self.option_client.get_option_chain(request)
                logging.debug(f"Response type: {type(response)}")
                logging.debug(f"Response content: {response}")
                
                if not response:
                    break
                
                # If response is a dictionary with symbols as keys
                if isinstance(response, dict):
                    snapshots = response.values()
                else:
                    # If response is iterable but not a dict
                    snapshots = response if hasattr(response, '__iter__') else [response]
                
                # Process snapshots
                for snapshot in snapshots:
                    try:
                        logging.debug(f"Processing snapshot type: {type(snapshot)}")
                        logging.debug(f"Snapshot content: {snapshot}")
                        
                        # Skip if snapshot is just a string
                        if isinstance(snapshot, str):
                            continue
                        
                        # Access attributes directly from OptionsSnapshot object
                        option_symbol = snapshot.symbol
                        quote = snapshot.latest_quote
                        greeks = snapshot.greeks
                        trade = snapshot.latest_trade
                        
                        chain_data.append({
                            'symbol': option_symbol,
                            'strike': float(option_symbol[-8:]) / 1000,
                            'expiration': f"20{option_symbol[-15:-9][:2]}-{option_symbol[-15:-9][2:4]}-{option_symbol[-15:-9][4:6]}",
                            'type': 'call' if 'C' in option_symbol[-9] else 'put',
                            'bid': quote.bid_price if quote else 0.0,
                            'ask': quote.ask_price if quote else 0.0,
                            'last': trade.price if trade else 0.0,
                            'volume': trade.size if trade else 0,
                            'open_interest': 0,  # Not available in real-time
                            'implied_volatility': snapshot.implied_volatility if hasattr(snapshot, 'implied_volatility') else 0.0,
                            'delta': greeks.delta if greeks else 0.0,
                            'gamma': greeks.gamma if greeks else 0.0,
                            'theta': greeks.theta if greeks else 0.0,
                            'vega': greeks.vega if greeks else 0.0,
                            'rho': greeks.rho if greeks else 0.0
                        })
                        
                    except Exception as e:
                        logging.error(f"Error processing snapshot: {str(e)}")
                        logging.debug(f"Problematic snapshot: {snapshot}")
                        continue
                
                # Check for pagination
                if isinstance(response, dict):
                    page_token = response.get('next_page_token')
                else:
                    page_token = getattr(response, 'next_page_token', None)
                
                if not page_token:
                    break
            
            contracts_df = pd.DataFrame(chain_data)
            logging.debug(f"Created DataFrame with {len(contracts_df)} rows")
            
            if contracts_df.empty:
                return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
            
            # Separate calls and puts
            calls = contracts_df[contracts_df['type'] == 'call']
            puts = contracts_df[contracts_df['type'] == 'put']
            
            logging.debug(f"Found {len(calls)} calls and {len(puts)} puts")
            
            return {
                'calls': self.standardize_columns(calls),
                'puts': self.standardize_columns(puts)
            }
            
        except Exception as e:
            logging.error(f"Error getting option chain from REST API for {symbol}: {str(e)}")
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
    
    async def _handle_option_trade(self, trade):
        """Handle incoming option trade data"""
        symbol = trade.symbol
        if symbol not in self._latest_option_data:
            self._latest_option_data[symbol] = {}
        self._latest_option_data[symbol]['trade'] = {
            'price': trade.price,
            'size': trade.size,
            'timestamp': trade.timestamp
        }
        
    async def _handle_option_quote(self, quote):
        """Handle incoming option quote data"""
        symbol = quote.symbol
        if symbol not in self._latest_option_data:
            self._latest_option_data[symbol] = {}
        self._latest_option_data[symbol]['quote'] = {
            'bid_price': quote.bid_price,
            'bid_size': quote.bid_size,
            'ask_price': quote.ask_price,
            'ask_size': quote.ask_size,
            'timestamp': quote.timestamp
        }
    
    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names and formats"""
        # Make a copy to avoid modifying the original
        df = df.copy()
        
        # Ensure all required columns exist with proper names
        column_map = {
            'symbol': 'symbol',
            'strike': 'strike',
            'type': 'type',
            'expiration': 'expiration',
            'bid': 'bid',
            'ask': 'ask',
            'last': 'last',
            'volume': 'volume',
            'open_interest': 'open_interest',
            'implied_volatility': 'implied_volatility',
            'delta': 'delta',
            'gamma': 'gamma',
            'theta': 'theta',
            'vega': 'vega',
            'rho': 'rho'
        }
        
        # Rename columns if they exist
        df = df.rename(columns={old: new for old, new in column_map.items() if old in df.columns})
        
        # Add missing columns with default values
        for col in column_map.values():
            if col not in df.columns:
                df[col] = 0.0 if col not in ['symbol', 'type', 'expiration'] else ''
                
        # Ensure numeric columns are float
        numeric_cols = ['strike', 'bid', 'ask', 'last', 'volume', 'open_interest', 
                       'implied_volatility', 'delta', 'gamma', 'theta', 'vega', 'rho']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
        return df

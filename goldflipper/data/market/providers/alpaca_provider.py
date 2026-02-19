import asyncio
import json
import logging
import time
from asyncio import Lock as AsyncLock
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import datetime
from threading import Lock as ThreadLock
from typing import Any, cast

import pandas as pd
import yaml
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.data.live.option import OptionDataStream
from alpaca.data.requests import (
    OptionChainRequest,
    OptionSnapshotRequest,
    StockBarsRequest,
    StockLatestQuoteRequest,
)
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient

from .base import MarketDataProvider


class LRUCache:
    """Least Recently Used (LRU) cache implementation"""

    def __init__(self, max_size: int):
        self.cache = OrderedDict()
        self.max_size = max_size
        self._lock = AsyncLock()

    async def get(self, key: str) -> Any | None:
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
        "symbol": "symbol",
        "strike_price": "strike",
        "expiration_date": "expiration",
        "last_price": "last",
        "bid_price": "bid",
        "ask_price": "ask",
        "volume": "volume",
        "open_interest": "open_interest",
        "implied_volatility": "implied_volatility",
        "in_the_money": "in_the_money",
    }

    def __init__(self, config_path: str | None = None):
        super().__init__(config_path)

        # Load settings from YAML
        self.settings = self._load_settings()

        # Get active account credentials from settings
        # Structure: alpaca.accounts.<account_name>.{api_key, secret_key, base_url}
        active_account = self.settings.get("alpaca", {}).get("active_account", "paper_1")
        accounts = self.settings.get("alpaca", {}).get("accounts", {})
        account_settings = accounts.get(active_account, {})

        if not account_settings:
            raise ValueError(f"No credentials found for active account '{active_account}'")

        self.api_key = account_settings.get("api_key")
        self.secret_key = account_settings.get("secret_key")
        self.base_url = account_settings.get("base_url", "https://paper-api.alpaca.markets/v2")

        if not self.api_key or not self.secret_key:
            raise ValueError(f"Missing api_key or secret_key for account '{active_account}'")

        # Use v2 endpoints for data and streaming
        self.data_url = "https://data.alpaca.markets"
        self.stream_url = "wss://stream.data.alpaca.markets/v2/"

        # Initialize clients
        self.stock_client = StockHistoricalDataClient(api_key=self.api_key, secret_key=self.secret_key)

        self.option_client = OptionHistoricalDataClient(api_key=self.api_key, secret_key=self.secret_key)

        self.trading_client = TradingClient(api_key=self.api_key, secret_key=self.secret_key, paper=True, url_override=self.base_url)

        # WebSocket state management
        self.stream_client = None
        self._cache = {}  # Simple memory cache
        self._latest_data = {}  # Store latest data from WebSocket
        self._ws_connected = False
        self._ws_subscribed_symbols: set[str] = set()
        self._ws_last_heartbeat = time.time()
        self._ws_lock = ThreadLock()
        self._reconnect_task = None
        self._health_check_task = None
        self._stock_ws_task = None
        self._option_ws_task = None

        # Initialize cache and rate limiter
        provider_settings = self.settings["market_data_providers"]["providers"]["alpaca"]
        cache_settings = provider_settings["cache"]
        rate_limit_settings = provider_settings["rate_limiting"]

        if cache_settings["enabled"]:
            self.cache = LRUCache(max_size=cache_settings["max_size"])
        else:
            self.cache = None

        if rate_limit_settings["enabled"]:
            self.rate_limiter = RateLimiter(
                max_requests=rate_limit_settings["quotes_per_minute"],
                time_window=60,  # 1 minute
                buffer_percent=rate_limit_settings["buffer_percent"],
            )
        else:
            self.rate_limiter = None

        # Initialize WebSocket for options
        self.option_stream = OptionDataStream(api_key=self.api_key, secret_key=self.secret_key, feed=DataFeed.IEX)

        # Store latest data from WebSocket
        self._latest_option_data = {}

        # Set up stream handlers
        self.option_stream.subscribe_trades(self._handle_option_trade)
        self.option_stream.subscribe_quotes(self._handle_option_quote)

    def _load_settings(self) -> dict:
        """Load settings from YAML file"""
        # Use exe-aware path for Nuitka onefile compatibility
        from goldflipper.utils.exe_utils import get_settings_path

        config_path = str(get_settings_path())
        with open(config_path) as f:
            return yaml.safe_load(f)

    async def _init_websocket(self):
        """Initialize WebSocket connection"""
        try:
            if self.stream_client is None:
                # Initialize both stock and option streams
                self.stream_client = StockDataStream(api_key=self.api_key, secret_key=self.secret_key, feed=DataFeed.SIP)

                self.option_stream = OptionDataStream(api_key=self.api_key, secret_key=self.secret_key, feed=DataFeed.IEX)

                logging.debug("Setting up WebSocket handlers...")

                # Stock data handlers
                async def stock_handler(data):
                    if "trade" in data:
                        await self._handle_trade(data)
                    elif "quote" in data:
                        await self._handle_quote(data)
                    elif "bar" in data:
                        await self._handle_bar(data)
                    logging.debug(f"Received stock data: {data}")

                # Option data handlers
                async def option_handler(data):
                    logging.debug(f"Received option data: {data}")
                    if "trade" in data:
                        await self._handle_option_trade(data)
                    elif "quote" in data:
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
            stream_client = self.stream_client
            if stream_client is None:
                await asyncio.sleep(1)
                continue

            try:
                # Keep the connection alive
                while True:
                    try:
                        ws = getattr(stream_client, "_ws", None)
                        if ws is None:
                            raise RuntimeError("WebSocket is not initialized")
                        message = await ws.recv()
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
                    reconnect_fn = getattr(stream_client, "_connect", None)
                    if callable(reconnect_fn):
                        reconnect_coro = cast(Callable[[], Awaitable[Any]], reconnect_fn)
                        await reconnect_coro()
                    else:
                        raise RuntimeError("Stream client reconnect is unavailable")

                    # Re-authenticate
                    auth_message = [{"action": "auth", "key": self.api_key, "secret": self.secret_key}]
                    ws = getattr(stream_client, "_ws", None)
                    if ws is None:
                        raise RuntimeError("WebSocket is not initialized after reconnect")
                    await ws.send(json.dumps(auth_message))
                    await ws.recv()  # Wait for auth response

                    self._ws_connected = True

                    # Resubscribe to symbols
                    for symbol in self._ws_subscribed_symbols:
                        await self._resubscribe_symbol(symbol)
                except Exception as reconnect_error:
                    logging.error(f"Failed to reconnect: {str(reconnect_error)}")

            await asyncio.sleep(1)  # Wait before retry

    async def _resubscribe_symbol(self, symbol: str):
        """Resubscribe to a symbol after reconnection"""
        stream_client = self.stream_client
        if stream_client is None:
            return

        subscription_message = [{"action": "subscribe", "trades": [symbol], "quotes": [symbol], "bars": [symbol]}]
        ws = getattr(stream_client, "_ws", None)
        if ws is None:
            return
        await ws.send(json.dumps(subscription_message))

    async def subscribe_symbol(self, symbol: str):
        """Subscribe to updates for a specific symbol"""
        stream_client = self.stream_client
        if stream_client is None:
            logging.warning("Stream client is not initialized; cannot subscribe")
            return

        if symbol not in self._ws_subscribed_symbols and self._ws_connected:
            try:
                logging.debug(f"Subscribing to {symbol}...")

                # Subscribe using SDK methods
                stream_client.subscribe_trades(self._handle_trade, symbol)
                stream_client.subscribe_quotes(self._handle_quote, symbol)
                stream_client.subscribe_bars(self._handle_bar, symbol)

                self._ws_subscribed_symbols.add(symbol)
                logging.info(f"Subscribed to {symbol}")
            except Exception as e:
                logging.error(f"Error subscribing to {symbol}: {str(e)}")

    async def _handle_trade(self, trade):
        """Handle trade updates"""
        try:
            logging.debug(f"Received trade data: {trade}")

            symbol = trade.symbol
            self._latest_data[symbol] = {"last_trade": {"price": trade.price, "size": trade.size, "timestamp": trade.timestamp}}
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
                "quote": {
                    "bid": quote.bid_price,
                    "ask": quote.ask_price,
                    "bid_size": quote.bid_size,
                    "ask_size": quote.ask_size,
                    "timestamp": quote.timestamp,
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
                "bar": {"open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close, "volume": bar.volume, "timestamp": bar.timestamp}
            }
            self._ws_last_heartbeat = time.time()
            logging.debug(f"Processed bar for {symbol}: {bar}")
        except Exception as e:
            logging.error(f"Error handling bar: {str(e)}")

    async def cleanup(self):
        """Cleanup resources"""
        for task_name in ("_stock_ws_task", "_option_ws_task"):
            task = getattr(self, task_name, None)
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, task_name, None)

        if self.stream_client:
            await self.stream_client.close()

        self.stream_client = None
        self._ws_connected = False

    def get_stock_price(self, symbol: str) -> float:
        """Get current stock price for a symbol using REST API.

        Note: This method is synchronous to match the base class interface.
        WebSocket data is not used here to avoid async/sync mismatch issues.
        """
        try:
            # Normalize symbol
            symbol = symbol.upper()

            # Try cached WebSocket data first (if available from background streaming)
            if symbol in self._latest_data:
                logging.debug(f"Using cached WebSocket data for {symbol}: {self._latest_data[symbol]}")

                # Try quote data first
                quote = self._latest_data[symbol].get("quote")
                if quote:
                    ask = float(quote.get("ask_price", 0))
                    bid = float(quote.get("bid_price", 0))
                    if ask > 0 and bid > 0:
                        price = (ask + bid) / 2
                        logging.debug(f"Using cached WebSocket quote for {symbol}: bid={bid}, ask={ask}, mid={price}")
                        return float(price)

                # Try last trade if quote isn't available
                trade = self._latest_data[symbol].get("last_trade")
                if trade:
                    price = float(trade.get("price", 0))
                    if price > 0:
                        logging.debug(f"Using cached WebSocket trade for {symbol}: price={price}")
                        return float(price)

            # Use REST API (synchronous)
            logging.debug(f"No WebSocket data available for {symbol}, using REST API")

            request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            response = self.stock_client.get_stock_latest_quote(request)

            logging.debug(f"REST API response for {symbol}: {response}")

            if not response or symbol not in response:
                raise ValueError(f"No quote data returned for {symbol}")

            quote = response[symbol]
            bid_price = float(quote.bid_price) if quote.bid_price is not None else 0.0
            ask_price = float(quote.ask_price) if quote.ask_price is not None else 0.0

            # Use bid price if ask is 0
            if ask_price == 0:
                price = bid_price
            elif bid_price == 0:
                price = ask_price
            else:
                price = (ask_price + bid_price) / 2

            if price == 0:
                raise ValueError(f"No valid price data for {symbol}")

            logging.debug(f"Calculated price for {symbol}: {price}")
            return float(price)

        except Exception as e:
            logging.error(f"Error getting stock price for {symbol}: {str(e)}")
            raise

    # Existing Historical API methods remain the same
    def get_historical_data(self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1Min") -> pd.DataFrame:
        """Get historical price data using Alpaca"""
        # Check cache first
        cache_key = f"{symbol}_{start_date}_{end_date}_{interval}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Convert interval string to Alpaca TimeFrame
        timeframe = self._convert_interval(interval)

        request = StockBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, start=start_date, end=end_date)

        try:
            bars = self.stock_client.get_stock_bars(request)
            df = bars.df

            # Cache the result
            self._cache[cache_key] = df
            return df

        except Exception as e:
            logging.error(f"Error getting historical data for {symbol}: {str(e)}")
            return pd.DataFrame()

    def get_option_chain(self, symbol: str, expiration_date: str | None = None) -> dict[str, pd.DataFrame]:
        """Get option chain data using WebSocket data with REST API fallback"""
        try:
            # Try WebSocket data first
            chain_data = []
            for option_symbol, data in self._latest_option_data.items():
                if symbol in option_symbol:  # Basic filter for underlying
                    quote = data.get("quote", {})
                    trade = data.get("trade", {})

                    # Extract expiry from option symbol
                    symbol_expiry = self._extract_expiry(option_symbol)

                    # Skip if expiration_date is specified and doesn't match
                    if expiration_date and symbol_expiry != expiration_date:
                        continue

                    chain_data.append(
                        {
                            "symbol": option_symbol,
                            "strike": self._extract_strike(option_symbol),
                            "expiration": symbol_expiry,
                            "type": "call" if "C" in option_symbol else "put",
                            "bid": quote.get("bid_price", 0.0),
                            "ask": quote.get("ask_price", 0.0),
                            "last": trade.get("price", 0.0),
                            "volume": trade.get("size", 0),
                            "open_interest": 0,  # Not available in real-time
                            "implied_volatility": 0.0,  # Not available in real-time
                        }
                    )

            contracts_df = pd.DataFrame(chain_data)

            # If WebSocket data is empty, fall back to REST API
            if contracts_df.empty:
                logging.debug(f"No WebSocket data available for {symbol} options, falling back to REST API")
                return self._get_option_chain_rest(symbol, expiration_date)

            # Separate calls and puts
            calls = contracts_df[contracts_df["type"] == "call"]
            puts = contracts_df[contracts_df["type"] == "put"]

            return {"calls": self.standardize_columns(calls), "puts": self.standardize_columns(puts)}

        except Exception as e:
            logging.error(f"Error getting option chain for {symbol}: {str(e)}")
            # Try REST API as fallback
            return self._get_option_chain_rest(symbol, expiration_date)

    def _get_option_chain_rest(self, symbol: str, expiration_date: str | None = None) -> dict[str, pd.DataFrame]:
        """Fallback method to get option chain using REST API"""
        try:
            chain_data = []
            page_token = None

            while True:
                request = OptionChainRequest(
                    underlying_symbol=symbol,
                    expiration_date=datetime.strptime(expiration_date, "%Y-%m-%d").date() if expiration_date else None,
                    page_token=page_token,
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
                    snapshots = response if hasattr(response, "__iter__") else [response]

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

                        chain_data.append(
                            {
                                "symbol": option_symbol,
                                "strike": float(option_symbol[-8:]) / 1000,
                                "expiration": f"20{option_symbol[-15:-9][:2]}-{option_symbol[-15:-9][2:4]}-{option_symbol[-15:-9][4:6]}",
                                "type": "call" if "C" in option_symbol[-9] else "put",
                                "bid": quote.bid_price if quote else 0.0,
                                "ask": quote.ask_price if quote else 0.0,
                                "last": trade.price if trade else 0.0,
                                "volume": trade.size if trade else 0,
                                "open_interest": 0,  # Not available in real-time
                                "implied_volatility": snapshot.implied_volatility if hasattr(snapshot, "implied_volatility") else 0.0,
                                "delta": greeks.delta if greeks else 0.0,
                                "gamma": greeks.gamma if greeks else 0.0,
                                "theta": greeks.theta if greeks else 0.0,
                                "vega": greeks.vega if greeks else 0.0,
                                "rho": greeks.rho if greeks else 0.0,
                            }
                        )

                    except Exception as e:
                        logging.error(f"Error processing snapshot: {str(e)}")
                        logging.debug(f"Problematic snapshot: {snapshot}")
                        continue

                # Check for pagination
                if isinstance(response, dict):
                    page_token = response.get("next_page_token")
                else:
                    page_token = getattr(response, "next_page_token", None)

                if not page_token:
                    break

            contracts_df = pd.DataFrame(chain_data)
            logging.debug(f"Created DataFrame with {len(contracts_df)} rows")

            if contracts_df.empty:
                return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}

            # Separate calls and puts
            calls = contracts_df[contracts_df["type"] == "call"]
            puts = contracts_df[contracts_df["type"] == "put"]

            logging.debug(f"Found {len(calls)} calls and {len(puts)} puts")

            return {"calls": self.standardize_columns(calls), "puts": self.standardize_columns(puts)}

        except Exception as e:
            logging.error(f"Error getting option chain from REST API for {symbol}: {str(e)}")
            return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}

    def _convert_interval(self, interval: str) -> TimeFrame:
        """Convert common interval strings to Alpaca TimeFrame"""
        interval_map = {"1m": TimeFrame.Minute, "5m": TimeFrame.Minute * 5, "15m": TimeFrame.Minute * 15, "1h": TimeFrame.Hour, "1d": TimeFrame.Day}
        return interval_map.get(interval.lower(), TimeFrame.Minute)

    def _extract_strike(self, option_symbol: str) -> float:
        """Extract strike price from OCC option symbol.

        OCC format: SYMBOL + YYMMDD + C/P + 8-digit strike (in tenths of cents)
        Example: SPY251211C00590000 -> strike = 590.0
        """
        try:
            # Strike is last 8 characters, in tenths of cents
            strike_str = option_symbol[-8:]
            return float(strike_str) / 1000
        except (ValueError, IndexError):
            return 0.0

    def _extract_expiry(self, option_symbol: str) -> str:
        """Extract expiration date from OCC option symbol.

        OCC format: SYMBOL + YYMMDD + C/P + 8-digit strike
        Example: SPY251211C00590000 -> expiry = 2025-12-11
        """
        try:
            # Date is 6 characters before the C/P indicator (position -15 to -9)
            date_str = option_symbol[-15:-9]
            if len(date_str) == 6 and date_str.isdigit():
                return f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
            return ""
        except (ValueError, IndexError):
            return ""

    def get_option_greeks(self, option_symbol: str) -> dict[str, float]:
        """Get option Greeks from Alpaca"""
        # Alpaca doesn't provide Greeks directly, so we'll return empty values
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

    async def _handle_option_trade(self, trade):
        """Handle incoming option trade data"""
        symbol = trade.symbol
        if symbol not in self._latest_option_data:
            self._latest_option_data[symbol] = {}
        self._latest_option_data[symbol]["trade"] = {"price": trade.price, "size": trade.size, "timestamp": trade.timestamp}

    async def _handle_option_quote(self, quote):
        """Handle incoming option quote data"""
        symbol = quote.symbol
        if symbol not in self._latest_option_data:
            self._latest_option_data[symbol] = {}
        self._latest_option_data[symbol]["quote"] = {
            "bid_price": quote.bid_price,
            "bid_size": quote.bid_size,
            "ask_price": quote.ask_price,
            "ask_size": quote.ask_size,
            "timestamp": quote.timestamp,
        }

    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names and formats"""
        # Make a copy to avoid modifying the original
        df = df.copy()

        # Ensure all required columns exist with proper names
        column_map = {
            "symbol": "symbol",
            "strike": "strike",
            "type": "type",
            "expiration": "expiration",
            "bid": "bid",
            "ask": "ask",
            "last": "last",
            "volume": "volume",
            "open_interest": "open_interest",
            "implied_volatility": "implied_volatility",
            "delta": "delta",
            "gamma": "gamma",
            "theta": "theta",
            "vega": "vega",
            "rho": "rho",
        }

        # Rename columns if they exist
        df = df.rename(columns={old: new for old, new in column_map.items() if old in df.columns})

        # Add missing columns with default values
        for col in column_map.values():
            if col not in df.columns:
                df.loc[:, col] = 0.0 if col not in ["symbol", "type", "expiration"] else ""

        # Ensure numeric columns are float
        numeric_cols = ["strike", "bid", "ask", "last", "volume", "open_interest", "implied_volatility", "delta", "gamma", "theta", "vega", "rho"]
        for col in numeric_cols:
            if col in df.columns:
                df.loc[:, col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df

    def get_option_quote(self, contract_symbol: str):
        """Get single option quote for a specific contract symbol.

        Uses REST API to get real-time option snapshot data.
        Returns a DataFrame with standardized columns or an empty DataFrame if unavailable.
        """
        try:
            # Try cached WebSocket data first
            if contract_symbol in self._latest_option_data:
                data = self._latest_option_data[contract_symbol]
                quote = data.get("quote", {})
                trade = data.get("trade", {})
                if quote or trade:
                    row = {
                        "symbol": contract_symbol,
                        "strike": self._extract_strike(contract_symbol),
                        "expiration": self._extract_expiry(contract_symbol),
                        "type": "call" if "C" in contract_symbol[-9] else "put",
                        "bid": float(quote.get("bid_price", 0.0) or 0.0),
                        "ask": float(quote.get("ask_price", 0.0) or 0.0),
                        "last": float(trade.get("price", 0.0) or 0.0),
                        "volume": int(trade.get("size", 0) or 0),
                        "open_interest": 0,
                        "implied_volatility": 0.0,
                        "delta": 0.0,
                        "gamma": 0.0,
                        "theta": 0.0,
                        "vega": 0.0,
                        "rho": 0.0,
                    }
                    df = pd.DataFrame([row])
                    return self.standardize_columns(df)

            # Fall back to REST API for option snapshot
            logging.debug(f"Using REST API for option quote: {contract_symbol}")
            request = OptionSnapshotRequest(symbol_or_symbols=contract_symbol)
            response = self.option_client.get_option_snapshot(request)

            if not response or contract_symbol not in response:
                logging.warning(f"No option snapshot returned for {contract_symbol}")
                return pd.DataFrame()

            snapshot = response[contract_symbol]
            quote = snapshot.latest_quote
            trade = snapshot.latest_trade
            greeks = snapshot.greeks

            row = {
                "symbol": contract_symbol,
                "strike": self._extract_strike(contract_symbol),
                "expiration": self._extract_expiry(contract_symbol),
                "type": "call" if "C" in contract_symbol[-9] else "put",
                "bid": float(quote.bid_price) if quote and quote.bid_price else 0.0,
                "ask": float(quote.ask_price) if quote and quote.ask_price else 0.0,
                "last": float(trade.price) if trade and trade.price else 0.0,
                "volume": int(trade.size) if trade and trade.size else 0,
                "open_interest": 0,
                "implied_volatility": float(snapshot.implied_volatility) if snapshot.implied_volatility else 0.0,
                "delta": float(greeks.delta) if greeks and greeks.delta else 0.0,
                "gamma": float(greeks.gamma) if greeks and greeks.gamma else 0.0,
                "theta": float(greeks.theta) if greeks and greeks.theta else 0.0,
                "vega": float(greeks.vega) if greeks and greeks.vega else 0.0,
                "rho": float(greeks.rho) if greeks and greeks.rho else 0.0,
            }

            df = pd.DataFrame([row])
            return self.standardize_columns(df)

        except Exception as e:
            logging.error(f"Error getting option quote for {contract_symbol}: {str(e)}")
            return pd.DataFrame()

    def get_option_expirations(self, symbol: str) -> list:
        """Get available option expirations from Alpaca by querying option contracts."""
        try:
            # Query option contracts for this symbol to get available expirations
            from alpaca.trading.requests import GetOptionContractsRequest

            request = GetOptionContractsRequest(underlying_symbols=[symbol.upper()], status="active")

            response = self.trading_client.get_option_contracts(request)

            if not response or not response.option_contracts:
                logging.debug(f"No option contracts found for {symbol}")
                return []

            # Extract unique expiration dates
            expirations = set()
            for contract in response.option_contracts:
                if hasattr(contract, "expiration_date") and contract.expiration_date:
                    exp_str = str(contract.expiration_date)
                    expirations.add(exp_str)

            # Sort and return as list
            return sorted(expirations)

        except Exception as e:
            logging.error(f"Error getting option expirations for {symbol}: {str(e)}")
            return []

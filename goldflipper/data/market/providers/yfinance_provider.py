import yfinance as yf
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
from .base import MarketDataProvider
import asyncio
import logging

class YFinanceProvider(MarketDataProvider):
    """YFinance implementation of market data provider"""
    
    COLUMN_MAPPING = {
        'contractSymbol': 'symbol',
        'strike': 'strike',
        'lastTradeDate': 'expiration',
        'lastPrice': 'last',
        'bid': 'bid',
        'ask': 'ask',
        'volume': 'volume',
        'openInterest': 'open_interest',
        'impliedVolatility': 'implied_volatility',
        'inTheMoney': 'in_the_money'
    }
    
    def __init__(self):
        self._cache = {}  # Simple memory cache
        
    async def get_stock_price(self, symbol: str, regular_hours_only: bool = False) -> float:
        """Get current stock price
        
        Args:
            symbol: Stock ticker symbol
            regular_hours_only: Currently not supported by YFinance provider
        """
        if regular_hours_only:
            logging.warning(f"YFinance provider does not support regular_hours_only mode for {symbol}")
            
        try:
            ticker = yf.Ticker(symbol)
            
            # Run the potentially blocking operations in a thread pool
            loop = asyncio.get_event_loop()
            
            # Try multiple methods in order of reliability
            try:
                # Method 1: Fast info (most current)
                price = await loop.run_in_executor(
                    None,
                    lambda: ticker.fast_info['lastPrice']
                )
                logging.info(f"YFinance: Using real-time price from fast_info for {symbol}")
                return price
                
            except (KeyError, AttributeError):
                try:
                    # Method 2: Regular info
                    price = await loop.run_in_executor(
                        None,
                        lambda: ticker.info['currentPrice']
                    )
                    logging.info(f"YFinance: Using currentPrice from stock.info for {symbol}")
                    return price
                    
                except (KeyError, AttributeError):
                    # Method 3: Latest minute data
                    history = await loop.run_in_executor(
                        None,
                        lambda: ticker.history(period='1d', interval='1m')
                    )
                    if not history.empty:
                        price = history['Close'].iloc[-1]
                        logging.info(f"YFinance: Using most recent minute data for {symbol}")
                        return price
                    else:
                        raise ValueError(f"No price data available for {symbol}")
                        
        except Exception as e:
            logging.error(f"YFinance error getting price for {symbol}: {str(e)}")
            raise
        
    def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """Fetch historical data via yfinance with normalized columns.

        Returns a DataFrame with at least these columns when available:
        - 'timestamp' (datetime index retained; column also added)
        - 'Open'/'open', 'High'/'high', 'Low'/'low', 'Close'/'close', 'Volume'/'volume'
        """
        # Check cache first (only if non-empty)
        cache_key = f"{symbol}_{start_date}_{end_date}_{interval}"
        cached = self._cache.get(cache_key)
        if cached is not None and not getattr(cached, 'empty', True):
            return cached

        try:
            # Use history() for better control
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date, interval=interval, auto_adjust=False)
            logging.info(f"YFinance.history {symbol} {interval} {start_date.date()}->{end_date.date()} rows={0 if data is None else len(data)}")
            if data is None or data.empty:
                # Fallback to download
                data = yf.download(symbol, start=start_date, end=end_date, interval=interval, progress=False)
                logging.info(f"YFinance.download(range) {symbol} {interval} rows={0 if data is None else len(data)}")
        except Exception as e:
            logging.error(f"YFinance: error fetching historical for {symbol}: {e}")
            data = pd.DataFrame()

        # Final fallback: pull a broader window by period and filter locally
        if (data is None or data.empty) and interval in ("1d", "1wk", "1mo"):
            try:
                period = "2mo" if interval == "1d" else "6mo"
                wide = yf.download(symbol, period=period, interval=interval, progress=False)
                if wide is not None and not wide.empty:
                    # Filter by date range
                    try:
                        wide_idx = wide
                        if not isinstance(wide_idx.index, pd.DatetimeIndex):
                            wide_idx.index = pd.to_datetime(wide_idx.index, errors='coerce')
                        mask = (wide_idx.index >= pd.to_datetime(start_date)) & (wide_idx.index < pd.to_datetime(end_date))
                        data = wide_idx.loc[mask]
                        logging.info(f"YFinance.download(period={period}) {symbol} filtered rows={len(data)} total={len(wide)}")
                    except Exception:
                        data = wide
            except Exception as e:
                logging.warning(f"YFinance: period fallback failed for {symbol}: {e}")

        if data is None or data.empty:
            # Do not cache empty results
            return data

        # Ensure datetime index and add 'timestamp' column for consumers that expect it
        try:
            if not isinstance(data.index, pd.DatetimeIndex):
                data.index = pd.to_datetime(data.index, errors='coerce')
            data['timestamp'] = data.index
        except Exception:
            pass

        # Add lowercase duplicates for robustness
        for col in list(data.columns):
            low = col.lower() if isinstance(col, str) else col
            if isinstance(col, str) and low not in data.columns:
                data[low] = data[col]

        # Cache and return (only non-empty)
        if not data.empty:
            self._cache[cache_key] = data
        return data
        
    def get_option_chain(
        self,
        symbol: str,
        expiration_date: Optional[str] = None,
        date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        if date:
            logging.warning(f"YFinance provider does not support historical option data. Ignoring date parameter: {date}")
        
        try:
            ticker = yf.Ticker(symbol)
            
            if expiration_date:
                chain = ticker.option_chain(expiration_date)
            else:
                # Get the nearest expiration date
                dates = ticker.options
                if not dates:
                    return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
                chain = ticker.option_chain(dates[0])
            
            # Log the raw columns we get from YFinance
            logging.info(f"Raw columns from YFinance: {chain.calls.columns.tolist()}")
            
            # Standardize columns before returning
            calls = self.standardize_columns(chain.calls)
            puts = self.standardize_columns(chain.puts)
            
            # Log the standardized columns
            logging.info(f"Standardized columns: {calls.columns.tolist()}")
            
            return {
                'calls': calls.copy(),  # Use copy() to avoid SettingWithCopyWarning
                'puts': puts.copy()
            }
        except Exception as e:
            logging.error(f"Error getting option chain for {symbol}: {str(e)}")
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}

    def get_available_expirations(self, symbol: str) -> list[str]:
        """Return available option expiration dates for a symbol using yfinance.

        Returns a list of date strings in 'YYYY-MM-DD' format (already provided by yfinance).
        """
        try:
            ticker = yf.Ticker(symbol)
            dates = ticker.options or []
            # Ensure strings and sorted ascending
            result = sorted({str(d) for d in dates})
            logging.info(f"YFinance: {symbol} available expirations: {len(result)}")
            return result
        except Exception as e:
            logging.error(f"YFinance error getting expirations for {symbol}: {e}")
            return []

    def get_option_quote(self, contract_symbol: str, strike_price: float = None) -> pd.DataFrame:
        """Get option quote with proper Pandas filtering"""
        try:
            # Parse contract symbol to get underlying
            parts = contract_symbol.split('_')
            if len(parts) < 2:
                logging.error(f"Invalid contract symbol format: {contract_symbol}")
                return pd.DataFrame()
                
            symbol = parts[0]
            # Extract expiration date
            exp_date = None
            for part in parts[1:]:
                if part.endswith('C') or part.endswith('P'):
                    exp_date = part[:-1]  # Remove C/P
                    break
                    
            if not exp_date:
                logging.error(f"Could not extract expiration from contract symbol: {contract_symbol}")
                return pd.DataFrame()
                
            chain = self.get_option_chain(symbol, exp_date)
            
            # Determine if call or put
            is_call = 'C' in contract_symbol
            options_data = chain['calls'] if is_call else chain['puts']
            
            # Use proper Pandas filtering if strike price provided
            if strike_price is not None:
                filtered_data = options_data[options_data['strike'] == strike_price]
            else:
                filtered_data = options_data
                
            if filtered_data.empty:
                logging.warning(f"No matching options found for {contract_symbol}")
                return pd.DataFrame()
                
            return filtered_data.copy()  # Return a copy to avoid SettingWithCopyWarning
            
        except Exception as e:
            logging.error(f"Error getting option quote for {contract_symbol}: {str(e)}")
            return pd.DataFrame()
        
    def get_option_greeks(self, option_symbol: str) -> Dict[str, float]:
        """Get option Greeks from yfinance"""
        # YFinance doesn't provide Greeks directly
        return {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
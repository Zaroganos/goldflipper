import yfinance as yf
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
from .base import MarketDataProvider
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

    def __init__(self, config_path: str = None):
        self._cache = {}  # Simple memory cache
        self.config_path = config_path
        
    def get_stock_price(self, symbol: str) -> float:
        """Get current stock price"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Try multiple methods in order of reliability
            try:
                # Method 1: Fast info (most current)
                price = ticker.fast_info['lastPrice']
                logging.info(f"YFinance: Using real-time price from fast_info for {symbol}")
                return float(price)
                
            except (KeyError, AttributeError):
                try:
                    # Method 2: Regular info
                    price = ticker.info.get('currentPrice') or ticker.info.get('regularMarketPrice')
                    if price:
                        logging.info(f"YFinance: Using currentPrice from stock.info for {symbol}")
                        return float(price)
                    raise KeyError("No price in info")
                    
                except (KeyError, AttributeError):
                    # Method 3: Latest minute data
                    history = ticker.history(period='1d', interval='1m')
                    if not history.empty:
                        price = history['Close'].iloc[-1]
                        logging.info(f"YFinance: Using most recent minute data for {symbol}")
                        return float(price)
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
        # Check cache first
        cache_key = f"{symbol}_{start_date}_{end_date}_{interval}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        data = yf.download(
            symbol,
            start=start_date,
            end=end_date,
            interval=interval
        )
        
        # Cache the result
        self._cache[cache_key] = data
        return data
        
    def get_option_chain(
        self,
        symbol: str,
        expiration_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
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

    def get_option_expirations(self, symbol: str) -> list:
        """Return available option expirations from yfinance."""
        try:
            ticker = yf.Ticker(symbol)
            dates = ticker.options or []
            return list(dates)
        except Exception as e:
            logging.error(f"YFinance: error getting expirations for {symbol}: {str(e)}")
            return []
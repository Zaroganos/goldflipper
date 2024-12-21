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
        
    async def get_stock_price(self, symbol: str) -> float:
        """Get current stock price"""
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
            'calls': calls,
            'puts': puts
        }
        
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
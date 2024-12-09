import yfinance as yf
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
from .base import MarketDataProvider

class YFinanceProvider(MarketDataProvider):
    """YFinance implementation of market data provider"""
    
    def __init__(self):
        self._cache = {}  # Simple memory cache
        
    def get_stock_price(self, symbol: str) -> float:
        ticker = yf.Ticker(symbol)
        return ticker.info.get('regularMarketPrice', 0.0)
        
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
            
        return {
            'calls': chain.calls,
            'puts': chain.puts
        }
        
    def get_option_greeks(self, option_symbol: str) -> Dict[str, float]:
        # Implementation will depend on how we want to calculate Greeks
        # Could use existing Greek calculators from goldflipper/data/greeks/
        pass 
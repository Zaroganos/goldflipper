from typing import Optional, Dict, Any
from datetime import datetime
import pandas as pd
from .providers.base import MarketDataProvider
from .providers.yfinance_provider import YFinanceProvider

class MarketDataManager:
    """Central manager for market data operations"""
    
    def __init__(self, provider: Optional[MarketDataProvider] = None):
        self.provider = provider or YFinanceProvider()
        
    def get_current_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive current market data for a symbol"""
        price = self.provider.get_stock_price(symbol)
        
        # Get today's data
        today = datetime.now()
        today_data = self.provider.get_historical_data(
            symbol,
            today.replace(hour=0, minute=0),
            today,
            interval="1m"
        )
        
        return {
            'current_price': price,
            'today_data': today_data,
            'timestamp': datetime.now()
        }
        
    def get_option_data(self, symbol: str, expiration_date: Optional[str] = None):
        """Get option chain and related data"""
        chain = self.provider.get_option_chain(symbol, expiration_date)
        stock_price = self.provider.get_stock_price(symbol)
        
        return {
            'chain': chain,
            'underlying_price': stock_price,
            'timestamp': datetime.now()
        } 
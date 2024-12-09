from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List
import pandas as pd

class MarketDataProvider(ABC):
    """Base class for market data providers"""
    
    @abstractmethod
    def get_stock_price(self, symbol: str) -> float:
        """Get current stock price"""
        pass
        
    @abstractmethod
    def get_historical_data(
        self, 
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """Get historical price data"""
        pass
        
    @abstractmethod
    def get_option_chain(
        self,
        symbol: str,
        expiration_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Get option chain data"""
        pass
        
    @abstractmethod
    def get_option_greeks(
        self,
        option_symbol: str
    ) -> Dict[str, float]:
        """Get option Greeks"""
        pass 
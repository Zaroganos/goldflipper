from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List, ClassVar
import pandas as pd

class MarketDataProvider(ABC):
    """Base class for market data providers"""
    
    # Class variable for column mapping
    COLUMN_MAPPING: ClassVar[Dict[str, str]] = {
        # Default/standardized column names
        'Provider': 'Provider',
        'symbol': 'symbol',
        'strike': 'strike',
        'expiration': 'expiration',
        'type': 'type',
        'bid': 'bid',
        'ask': 'ask',
        'last': 'last',
        'volume': 'volume',
        'open_interest': 'open_interest',
        'implied_volatility': 'implied_volatility',
        # Add missing columns for Greeks
        'delta': 'delta',
        'gamma': 'gamma',
        'theta': 'theta',
        'vega': 'vega',
        'rho': 'rho'
    }
    
    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names using the provider's mapping"""
        # We want to map FROM provider's columns TO our standard columns
        return df.rename(columns=self.COLUMN_MAPPING)
    
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
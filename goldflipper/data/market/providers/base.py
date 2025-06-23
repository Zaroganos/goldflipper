from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List, ClassVar
import pandas as pd
from ..errors import *

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
        'delta': 'delta',
        'gamma': 'gamma',
        'theta': 'theta',
        'vega': 'vega',
        'rho': 'rho'
    }
    
    def __init__(self, config_path: str):
        self.name = self.__class__.__name__
        
    def _handle_error(self, error: Exception, context: str) -> None:
        """Convert provider-specific errors to standard MarketDataErrors"""
        if isinstance(error, MarketDataError):
            # Already a standard error, just add provider if missing
            if not error.provider:
                error.provider = self.name
            raise error
            
        # Map common error patterns to standard errors
        error_msg = str(error).lower()
        if any(x in error_msg for x in ['timeout', 'connection', 'network']):
            raise ProviderConnectionError(str(error), self.name)
        elif any(x in error_msg for x in ['not found', 'no data', 'invalid symbol']):
            raise QuoteNotFoundError(str(error), self.name)
        elif any(x in error_msg for x in ['rate limit', 'too many requests']):
            raise RateLimitError(str(error), self.name)
        else:
            raise MarketDataError(f"{context}: {str(error)}", self.name)
    
    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names using the provider's mapping"""
        # We want to map FROM provider's columns TO our standard columns
        return df.rename(columns=self.COLUMN_MAPPING)
    
    @abstractmethod
    def get_stock_price(self, symbol: str, regular_hours_only: bool = False) -> Optional[float]:
        """Get current stock price
        
        Args:
            symbol: Stock ticker symbol  
            regular_hours_only: If True, excludes extended hours data
        """
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
        
    @abstractmethod
    def get_option_quote(self, contract_symbol: str) -> Optional[Dict[str, Any]]:
        """Get option quote data"""
        pass 
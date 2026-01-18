from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List, ClassVar, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass
import pandas as pd
from ..errors import *


# =============================================================================
# STREAMING INTERFACE - PRELIMINARY DRAFT
# =============================================================================
# Status: NOT IMPLEMENTED / NOT REQUIRED
# 
# This section defines a proposed interface for real-time streaming data
# support in market data providers. It is a preliminary draft for future
# implementation and is NOT currently used by the MarketDataManager or
# any production code.
#
# Providers are NOT required to implement these methods. The existing
# synchronous REST API methods remain the active interface.
#
# When this interface is ready for production:
# 1. Move StreamingCapability check to MarketDataManager
# 2. Update providers to implement streaming methods
# 3. Add async streaming dispatch to manager
# 4. Remove this notice
#
# Draft Date: 2026-01-16
# =============================================================================

class StreamDataType(Enum):
    """Types of streaming data that can be subscribed to."""
    QUOTE = "quote"           # Bid/ask updates
    TRADE = "trade"           # Last trade price/volume
    BAR = "bar"               # OHLCV candle updates
    OPTION_QUOTE = "option_quote"  # Option bid/ask
    OPTION_TRADE = "option_trade"  # Option trades


@dataclass
class StreamUpdate:
    """
    Standardized streaming data update.
    
    All streaming providers should convert their native update format
    to this standard structure before invoking callbacks.
    """
    symbol: str
    data_type: StreamDataType
    timestamp: datetime
    data: Dict[str, Any]
    # Common fields extracted for convenience:
    # - For QUOTE: bid, ask, bid_size, ask_size
    # - For TRADE: price, size, exchange
    # - For BAR: open, high, low, close, volume, vwap
    # - For OPTION_*: includes contract_symbol, underlying, etc.


# Type alias for streaming callbacks
StreamCallback = Callable[[StreamUpdate], Awaitable[None]]

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
    def get_stock_price(self, symbol: str) -> Optional[float]:
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
    def get_option_expirations(self, symbol: str) -> List[str]:
        """Get available option expiration dates (YYYY-MM-DD) for a symbol"""
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
    
    # =========================================================================
    # STREAMING INTERFACE METHODS - PRELIMINARY DRAFT
    # =========================================================================
    # These methods are NOT abstract - providers are not required to implement
    # them. Default implementations return False/raise NotImplementedError.
    # 
    # When a provider supports streaming, it should override these methods.
    # The MarketDataManager does NOT currently call these methods.
    # =========================================================================
    
    def supports_streaming(self) -> bool:
        """
        [DRAFT] Check if this provider supports real-time streaming.
        
        Returns:
            True if streaming is supported, False otherwise.
            
        Note:
            Default implementation returns False. Providers with streaming
            capability should override this to return True.
        """
        return False
    
    def get_supported_stream_types(self) -> List[StreamDataType]:
        """
        [DRAFT] Get list of streaming data types this provider supports.
        
        Returns:
            List of StreamDataType enums supported by this provider.
            Empty list if streaming not supported.
            
        Example:
            A provider might return [StreamDataType.QUOTE, StreamDataType.TRADE]
            if it supports quote and trade streaming but not bar streaming.
        """
        return []
    
    async def connect_stream(self) -> bool:
        """
        [DRAFT] Establish streaming connection.
        
        Should be called before subscribing to any symbols. Handles
        authentication and connection setup.
        
        Returns:
            True if connection successful, False otherwise.
            
        Raises:
            NotImplementedError: If provider doesn't support streaming.
        """
        raise NotImplementedError(
            f"{self.name} does not implement streaming. "
            "Check supports_streaming() before calling."
        )
    
    async def disconnect_stream(self) -> None:
        """
        [DRAFT] Close streaming connection and clean up resources.
        
        Should unsubscribe from all symbols and close WebSocket connections.
        Safe to call even if not connected.
        """
        raise NotImplementedError(
            f"{self.name} does not implement streaming. "
            "Check supports_streaming() before calling."
        )
    
    async def subscribe(
        self,
        symbols: List[str],
        data_types: List[StreamDataType],
        callback: StreamCallback
    ) -> bool:
        """
        [DRAFT] Subscribe to streaming updates for symbols.
        
        Args:
            symbols: List of symbols to subscribe to (e.g., ["AAPL", "MSFT"])
            data_types: Types of data to receive (e.g., [StreamDataType.QUOTE])
            callback: Async function called with each StreamUpdate
            
        Returns:
            True if subscription successful, False otherwise.
            
        Example:
            async def on_update(update: StreamUpdate):
                print(f"{update.symbol}: {update.data}")
                
            await provider.subscribe(
                symbols=["AAPL"],
                data_types=[StreamDataType.QUOTE, StreamDataType.TRADE],
                callback=on_update
            )
        """
        raise NotImplementedError(
            f"{self.name} does not implement streaming. "
            "Check supports_streaming() before calling."
        )
    
    async def unsubscribe(
        self,
        symbols: List[str],
        data_types: Optional[List[StreamDataType]] = None
    ) -> bool:
        """
        [DRAFT] Unsubscribe from streaming updates.
        
        Args:
            symbols: List of symbols to unsubscribe from
            data_types: Specific data types to unsubscribe. If None,
                        unsubscribes from all data types for the symbols.
                        
        Returns:
            True if unsubscription successful, False otherwise.
        """
        raise NotImplementedError(
            f"{self.name} does not implement streaming. "
            "Check supports_streaming() before calling."
        )
    
    def is_stream_connected(self) -> bool:
        """
        [DRAFT] Check if streaming connection is active.
        
        Returns:
            True if connected and ready to receive data, False otherwise.
        """
        return False
    
    def get_subscribed_symbols(self) -> List[str]:
        """
        [DRAFT] Get list of currently subscribed symbols.
        
        Returns:
            List of symbol strings currently subscribed to streaming updates.
        """
        return []
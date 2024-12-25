from typing import Optional

class MarketDataError(Exception):
    """Base exception for market data operations"""
    def __init__(self, message: str, provider: Optional[str] = None):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider or 'Unknown'}] {message}")

class ProviderConnectionError(MarketDataError):
    """Failed to connect to provider"""
    pass

class QuoteNotFoundError(MarketDataError):
    """Requested quote not available"""
    pass

class RateLimitError(MarketDataError):
    """Provider rate limit exceeded"""
    pass

class ProviderConfigError(MarketDataError):
    """Provider configuration error"""
    pass

class InvalidSymbolError(MarketDataError):
    """Invalid symbol format or unsupported symbol"""
    pass 
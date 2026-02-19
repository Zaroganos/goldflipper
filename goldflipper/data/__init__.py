import logging

from goldflipper.utils.display import TerminalDisplay as display

from .market.manager import MarketDataManager
from .market.providers.marketdataapp_provider import MarketDataAppProvider


class MarketDataOperations:
    """Handles core market data operations for trading strategies"""

    def __init__(self, config_path: str):
        self.logger = logging.getLogger(__name__)
        self.provider = MarketDataAppProvider(config_path)
        self.manager = MarketDataManager(provider=self.provider)

    def get_stock_price(self, symbol: str) -> float | None:
        """Get current stock price with validation"""
        price = self.manager.get_stock_price(symbol)

        if price is not None and price > 0:
            return price

        self.logger.warning(f"Invalid stock price for {symbol}")
        return None

    def get_option_data(self, contract_symbol: str) -> dict[str, float] | None:
        """Get option data with validation"""
        quote = self.manager.get_option_quote(contract_symbol)

        if quote is None:
            return None

        # Validate the quote data
        if quote["bid"] <= 0 and quote["ask"] <= 0:
            self.logger.warning(f"Invalid bid/ask prices for {contract_symbol}")
            display.warning(f"Invalid bid/ask prices for {contract_symbol}")
            return None

        # If last price is 0 or missing, use mid price
        if quote["premium"] <= 0:
            quote["premium"] = (quote["bid"] + quote["ask"]) / 2

        return quote

"""
Lazy-initialized shared resources for MCP tools.

Each property initializes on first access so the MCP server starts fast
and only connects to external services when a tool actually needs them.

Usage from tool modules:
    from goldflipper.mcp_server.context import ctx
    price = ctx.market_data.get_stock_price("SPY")
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alpaca.trading.client import TradingClient
    from goldflipper.config.config import Config
    from goldflipper.data.market.manager import MarketDataManager
    from goldflipper.strategy.shared.play_manager import PlayManager

logger = logging.getLogger(__name__)


class MCPContext:
    """Lazy-initialized singleton holding shared resources for all MCP tools."""

    def __init__(self):
        self._config: "Config | None" = None
        self._market_data: "MarketDataManager | None" = None
        self._alpaca_client: "TradingClient | None" = None
        self._play_manager: "PlayManager | None" = None

    @property
    def config(self) -> "Config":
        if self._config is None:
            from goldflipper.config.config import Config

            self._config = Config()
            logger.info("MCP: Config loaded")
        return self._config

    @property
    def market_data(self) -> "MarketDataManager":
        if self._market_data is None:
            from goldflipper.data.market.manager import MarketDataManager

            self._market_data = MarketDataManager()
            logger.info("MCP: MarketDataManager initialized")
        return self._market_data

    @property
    def alpaca_client(self) -> "TradingClient":
        if self._alpaca_client is None:
            from goldflipper.alpaca_client import get_alpaca_client

            self._alpaca_client = get_alpaca_client()
            logger.info("MCP: Alpaca client initialized")
        return self._alpaca_client

    @property
    def play_manager(self) -> "PlayManager":
        if self._play_manager is None:
            from goldflipper.strategy.shared.play_manager import PlayManager

            self._play_manager = PlayManager()
            logger.info("MCP: PlayManager initialized")
        return self._play_manager


# Module-level singleton — all tool modules import this
ctx = MCPContext()

"""
Order Executor Module for Goldflipper Multi-Strategy System

This module provides centralized order execution logic:
- Opening positions (BUY_TO_OPEN or SELL_TO_OPEN)
- Closing positions (SELL_TO_CLOSE or BUY_TO_CLOSE)
- Order type handling (market, limit at bid/ask/mid/last)
- Position state management
- Support for both long (BTO/STC) and short (STO/BTC) strategies

The module extracts and consolidates order execution from core.py,
maintaining backward compatibility while enabling strategy-specific handling.

Trade Direction Support:
    - Long strategies (option_swings, momentum): BUY_TO_OPEN → SELL_TO_CLOSE
    - Short strategies (sell_puts): SELL_TO_OPEN → BUY_TO_CLOSE
    - Multi-leg strategies (spreads): Each leg has its own action

Usage:
    from goldflipper.strategy.shared.order_executor import OrderExecutor
    from goldflipper.strategy.base import OrderAction

    executor = OrderExecutor()

    # Long strategy (default)
    executor.create_entry_order(symbol, qty, order_type, option_data)

    # Short strategy (explicit action)
    executor.create_entry_order(
        symbol, qty, order_type, option_data,
        action=OrderAction.SELL_TO_OPEN
    )
"""

import logging
from datetime import datetime
from typing import Any, cast

from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
from alpaca.trading.requests import ClosePositionRequest, LimitOrderRequest, MarketOrderRequest

from goldflipper.config.config import config

# Import OrderAction for trade direction support
from goldflipper.strategy.base import OrderAction
from goldflipper.utils.display import TerminalDisplay as display

# ==================================================
# Order Action to Side Conversion
# ==================================================


def order_action_to_side(action: OrderAction) -> OrderSide:
    """
    Convert an OrderAction to the corresponding Alpaca OrderSide.

    Args:
        action: OrderAction enum value

    Returns:
        OrderSide.BUY for BTO/BTC, OrderSide.SELL for STO/STC

    Example:
        side = order_action_to_side(OrderAction.BUY_TO_OPEN)  # OrderSide.BUY
        side = order_action_to_side(OrderAction.SELL_TO_OPEN) # OrderSide.SELL
    """
    if action.is_buy():
        return OrderSide.BUY
    return OrderSide.SELL


def get_order_side_for_entry(action: OrderAction | None = None) -> OrderSide:
    """
    Get the order side for entry based on action.

    Args:
        action: OrderAction or None (defaults to BUY_TO_OPEN)

    Returns:
        OrderSide for the entry order
    """
    if action is None:
        action = OrderAction.BUY_TO_OPEN
    return order_action_to_side(action)


def get_order_side_for_exit(action: OrderAction | None = None) -> OrderSide:
    """
    Get the order side for exit based on action.

    Args:
        action: OrderAction or None (defaults to SELL_TO_CLOSE)

    Returns:
        OrderSide for the exit order
    """
    if action is None:
        action = OrderAction.SELL_TO_CLOSE
    return order_action_to_side(action)


# ==================================================
# Order Type Helpers
# ==================================================


def determine_limit_price(
    order_type: str, option_data: dict[str, Any], fallback_price: float | None = None, price_settings_key: str = "entry"
) -> tuple[float | None, str]:
    """
    Determine the limit price based on order type and option data.

    Args:
        order_type: Order type string (e.g., 'limit at bid', 'limit at ask', 'limit at mid', 'limit at last')
        option_data: Option data dictionary with bid/ask/mid/last prices
        fallback_price: Fallback price if requested price is not available
        price_settings_key: Config key for bid price settings ('entry', 'take_profit', 'stop_loss')

    Returns:
        Tuple of (limit_price, price_source_description)

    Example:
        price, source = determine_limit_price('limit at bid', option_data)
        logging.info(f"Using {source} for limit order: ${price:.2f}")
    """
    use_bid_price_settings = config.get("orders", "bid_price_settings", price_settings_key, default=True)

    if order_type == "limit at bid":
        if use_bid_price_settings and option_data.get("bid") is not None:
            return option_data["bid"], "bid price"
        elif option_data.get("last") is not None:
            return option_data["last"], "last traded price (bid settings disabled)"
        return fallback_price, "fallback price"

    elif order_type == "limit at ask":
        if use_bid_price_settings and option_data.get("ask") is not None:
            return option_data["ask"], "ask price"
        return fallback_price, "fallback price"

    elif order_type == "limit at mid":
        if use_bid_price_settings:
            bid = option_data.get("bid")
            ask = option_data.get("ask")
            if bid is not None and ask is not None:
                return (bid + ask) / 2, "mid price"
        return fallback_price, "fallback price (mid calculation failed)"

    elif order_type == "limit at last":
        if option_data.get("last") is not None:
            return option_data["last"], "last traded price"
        return fallback_price, "fallback price"

    elif order_type == "market":
        # Market orders don't need a limit price
        return None, "market order"

    else:
        logging.warning(f"Unknown order type: {order_type}. Using fallback price.")
        return fallback_price, f"fallback price (unknown order type: {order_type})"


def get_entry_premium(play: dict[str, Any], option_data: dict[str, Any]) -> float:
    """
    Get the entry premium based on the play's entry order type.

    Args:
        play: Play data dictionary
        option_data: Option data dictionary with bid/ask/mid/last prices

    Returns:
        Entry premium value
    """
    entry_order_type = play.get("entry_point", {}).get("order_type", "limit at bid")

    if entry_order_type == "limit at bid":
        return option_data.get("bid", 0.0)
    elif entry_order_type == "limit at ask":
        return option_data.get("ask", 0.0)
    elif entry_order_type == "limit at mid":
        bid = option_data.get("bid", 0.0)
        ask = option_data.get("ask", 0.0)
        return (bid + ask) / 2 if bid and ask else option_data.get("last", 0.0)
    else:  # 'limit at last' or 'market'
        return option_data.get("last", 0.0)


# ==================================================
# Order Executor Class
# ==================================================


class OrderExecutor:
    """
    Centralized executor for order placement operations.

    Handles:
    - Opening positions with market/limit orders
    - Closing positions for take profit or stop loss
    - Order type determination based on play settings
    - Position state tracking

    This class is designed to be used by both core.py (via thin wrappers)
    and strategy runners (directly).
    """

    def __init__(self, client=None, market_data=None):
        """
        Initialize the OrderExecutor.

        Args:
            client: Alpaca TradingClient instance. If None, will be loaded on demand.
            market_data: MarketDataManager instance. If None, will be loaded on demand.
        """
        self.logger = logging.getLogger(__name__)
        self._client = client
        self._market_data = market_data

    @property
    def client(self):
        """Get or create the Alpaca client."""
        if self._client is None:
            from goldflipper.alpaca_client import get_alpaca_client

            self._client = get_alpaca_client()
        return self._client

    @property
    def market_data(self):
        """Get or create the MarketDataManager."""
        if self._market_data is None:
            from goldflipper.data.market.manager import MarketDataManager

            self._market_data = MarketDataManager()
        return self._market_data

    # =========================================================================
    # Helper Functions
    # =========================================================================

    def get_option_contract(self, play: dict[str, Any]):
        """
        Get the option contract for a play.

        Args:
            play: Play data dictionary

        Returns:
            Option contract object or None if not found
        """
        from alpaca.trading.enums import AssetStatus
        from alpaca.trading.requests import GetOptionContractsRequest

        symbol = play["symbol"]
        expiration_date = datetime.strptime(play["expiration_date"], "%m/%d/%Y").date()
        strike_price = play["strike_price"]

        req = GetOptionContractsRequest(
            underlying_symbols=[symbol],
            expiration_date=expiration_date,
            strike_price_gte=strike_price,
            strike_price_lte=strike_price,
            type=play["trade_type"].lower(),
            status=AssetStatus.ACTIVE,
        )

        res = cast(Any, self.client.get_option_contracts(req))
        contracts = cast(list[Any], getattr(res, "option_contracts", []))

        if contracts:
            self.logger.info(f"Option contract found: {contracts[0]}")
            display.success(f"Option contract found: {contracts[0].symbol}")
            return contracts[0]
        else:
            self.logger.error(f"No option contract found for {symbol} with given parameters")
            display.error(f"No option contract found for {symbol} with given parameters")
            return None

    def get_stock_price(self, symbol: str) -> float | None:
        """
        Get current stock price for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Current stock price or None if unavailable
        """
        try:
            return self.market_data.get_stock_price(symbol)
        except Exception as e:
            self.logger.error(f"Error getting stock price for {symbol}: {e}")
            return None

    def get_option_data(self, option_contract_symbol: str) -> dict[str, Any] | None:
        """
        Get option data for a contract.

        Args:
            option_contract_symbol: Option contract symbol

        Returns:
            Option data dictionary or None if unavailable
        """
        try:
            return self.market_data.get_option_quote(option_contract_symbol)
        except Exception as e:
            self.logger.error(f"Error getting option data for {option_contract_symbol}: {e}")
            return None

    # =========================================================================
    # Entry Order Creation
    # =========================================================================

    def create_entry_order(
        self, contract_symbol: str, qty: int, order_type: str, option_data: dict[str, Any], action: OrderAction | None = None
    ) -> tuple[Any, bool]:
        """
        Create an entry order request.

        Args:
            contract_symbol: Option contract symbol
            qty: Number of contracts
            order_type: Order type (e.g., 'limit at bid', 'market')
            option_data: Option data for price determination
            action: OrderAction for this entry (default: BUY_TO_OPEN)
                   - BUY_TO_OPEN: Buy to open long position (default)
                   - SELL_TO_OPEN: Sell to open short position

        Returns:
            Tuple of (order_request, is_limit_order)
        """
        # Determine order side from action
        order_side = get_order_side_for_entry(action)
        action_name = (action or OrderAction.BUY_TO_OPEN).name

        is_limit_order = order_type != "market"

        if is_limit_order:
            limit_price, price_source = determine_limit_price(order_type, option_data, option_data.get("last", 0.0), "entry")
            # Handle None case (fallback to last price)
            if limit_price is None:
                limit_price = option_data.get("last", 0.0)
            limit_price = round(limit_price, 2)

            self.logger.info(f"Creating {action_name} limit order: {contract_symbol} {qty} @ ${limit_price:.2f} ({price_source})")

            order_req = LimitOrderRequest(
                symbol=contract_symbol,
                qty=qty,
                limit_price=limit_price,
                side=order_side,
                type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
            )
        else:
            self.logger.info(f"Creating {action_name} market order: {contract_symbol} {qty}")

            order_req = MarketOrderRequest(
                symbol=contract_symbol,
                qty=qty,
                side=order_side,
                type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
            )

        return order_req, is_limit_order

    # =========================================================================
    # Exit Order Creation
    # =========================================================================

    def create_exit_order(
        self,
        contract_symbol: str,
        qty: int,
        order_type: str,
        option_data: dict[str, Any],
        fallback_price: float,
        price_settings_key: str = "take_profit",
        action: OrderAction | None = None,
    ) -> tuple[Any, bool]:
        """
        Create an exit order request.

        Args:
            contract_symbol: Option contract symbol
            qty: Number of contracts
            order_type: Order type (e.g., 'limit at bid', 'market')
            option_data: Option data for price determination
            fallback_price: Fallback price if limit price cannot be determined
            price_settings_key: Config key for price settings ('take_profit', 'stop_loss')
            action: OrderAction for this exit (default: SELL_TO_CLOSE)
                   - SELL_TO_CLOSE: Sell to close long position (default)
                   - BUY_TO_CLOSE: Buy to close short position

        Returns:
            Tuple of (order_request or None for market close, is_limit_order)
        """
        # Determine order side from action
        order_side = get_order_side_for_exit(action)
        action_name = (action or OrderAction.SELL_TO_CLOSE).name

        is_limit_order = order_type.lower().startswith("limit") if order_type else False

        if is_limit_order:
            limit_price, price_source = determine_limit_price(order_type, option_data, fallback_price, price_settings_key)

            if limit_price is None:
                limit_price = fallback_price

            limit_price = round(limit_price, 2)

            self.logger.info(f"Creating {action_name} exit limit order: {contract_symbol} {qty} @ ${limit_price:.2f} ({price_source})")

            order_req = LimitOrderRequest(
                symbol=contract_symbol,
                qty=qty,
                limit_price=limit_price,
                side=order_side,
                type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
            )
            return order_req, True
        else:
            # For market orders, return None - caller should use close_position API
            self.logger.info(f"Creating {action_name} market exit for: {contract_symbol}")
            return None, False

    def close_position_market(self, contract_symbol: str, qty: int) -> Any:
        """
        Close a position using a market order.

        Args:
            contract_symbol: Option contract symbol
            qty: Number of contracts to close

        Returns:
            Order response from Alpaca
        """
        return self.client.close_position(symbol_or_asset_id=contract_symbol, close_options=ClosePositionRequest(qty=str(qty)))

    # =========================================================================
    # Position State Management
    # =========================================================================

    def initialize_play_status(self, play: dict[str, Any]) -> None:
        """
        Initialize status fields for a play before opening.

        Args:
            play: Play data dictionary (modified in place)
        """
        if "status" not in play:
            play["status"] = {}

        play["status"].update(
            {
                "order_id": None,
                "order_status": None,
                "position_exists": False,
            }
        )

    def initialize_closing_status(self, play: dict[str, Any]) -> None:
        """
        Initialize closing status fields for a play.

        Args:
            play: Play data dictionary (modified in place)
        """
        play["status"]["closing_order_id"] = None
        play["status"]["closing_order_status"] = None
        play["status"]["contingency_order_id"] = None
        play["status"]["contingency_order_status"] = None

    def update_logging_on_close(
        self, play: dict[str, Any], close_type: str, close_condition: str, stock_price: float | None, premium: float | None
    ) -> None:
        """
        Update play logging fields when closing a position.

        Args:
            play: Play data dictionary (modified in place)
            close_type: Type of close ('TP', 'SL', 'SL(C)')
            close_condition: Condition type ('stock', 'stock_pct', 'premium_pct')
            stock_price: Current stock price
            premium: Current option premium
        """
        if "logging" not in play:
            play["logging"] = {}

        play["logging"].update(
            {
                "datetime_atClose": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "price_atClose": stock_price if stock_price is not None else 0.0,
                "premium_atClose": premium if premium is not None else 0.0,
                "close_type": close_type,
                "close_condition": close_condition,
            }
        )

    def determine_close_condition(self, play: dict[str, Any], close_conditions: dict[str, Any]) -> str:
        """
        Determine what condition triggered the close.

        Args:
            play: Play data dictionary
            close_conditions: Close condition flags from evaluation

        Returns:
            Close condition string ('stock', 'stock_pct', 'premium_pct')
        """
        if close_conditions["is_profit"]:
            if play["take_profit"].get("stock_price") or play["take_profit"].get("stock_price_pct"):
                return "stock_pct" if play["take_profit"].get("stock_price_pct") else "stock"
            else:
                return "premium_pct"
        else:
            if play["stop_loss"].get("stock_price") or play["stop_loss"].get("stock_price_pct"):
                return "stock_pct" if play["stop_loss"].get("stock_price_pct") else "stock"
            else:
                return "premium_pct"


# ==================================================
# Standalone Functions (Backward Compatibility)
# ==================================================

# Shared executor instance
_default_executor: OrderExecutor | None = None


def _get_default_executor() -> OrderExecutor:
    """Get or create the default OrderExecutor instance."""
    global _default_executor
    if _default_executor is None:
        _default_executor = OrderExecutor()
    return _default_executor


def get_option_contract(play: dict[str, Any]):
    """
    Get the option contract for a play.

    Backward-compatible function wrapping OrderExecutor.get_option_contract().
    """
    return _get_default_executor().get_option_contract(play)

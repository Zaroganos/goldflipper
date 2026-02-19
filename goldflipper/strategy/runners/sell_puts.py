"""
Sell Puts Strategy Runner

This module implements a cash-secured put selling strategy inspired by
TastyTrade methodology. The strategy sells out-of-the-money puts on
quality underlyings to collect premium.

Trade Direction: SELL_TO_OPEN → BUY_TO_CLOSE (short premium)

This strategy SELLS puts to collect premium. It profits when:
- The underlying stays above strike (put expires worthless)
- Premium decreases (can buy back cheaper)

Risk Profile:
- Max profit: Premium collected (credit received)
- Max loss: Strike price - premium (if assigned at $0)
- Requires cash/margin to cover potential assignment

Key Features:
- Target delta selection (e.g., 30 delta puts)
- DTE range filtering (30-45 DTE)
- Minimum premium requirements
- 50% profit taking (buy back at half premium)
- 21 DTE management (close before expiration)
- Collateral tracking for cash-secured positions

Configuration section: sell_puts (in settings.yaml)
Playbooks: strategy/playbooks/sell_puts/
"""

from datetime import datetime
from typing import Any

from goldflipper.strategy.base import BaseStrategy, OrderAction
from goldflipper.strategy.registry import register_strategy

# Import shared utilities
from goldflipper.strategy.shared import (
    # Play management
    OrderExecutor,
)


@register_strategy("sell_puts")
class SellPutsStrategy(BaseStrategy):
    """
    Cash-Secured Put Selling Strategy (TastyTrade Style).

    Trade Direction: SELL_TO_OPEN → BUY_TO_CLOSE (short premium)

    This strategy SELLS puts to collect premium. It profits when:
    - The underlying stays above strike (put expires worthless)
    - Premium decreases (can buy back cheaper)

    Risk Profile:
    - Max profit: Premium collected
    - Max loss: Strike price - premium (if assigned at $0)
    - Requires cash/margin to cover potential assignment

    Exit Conditions (inverted from long strategies):
    - Take Profit: Premium DECREASES by X% (e.g., 50% = buy back at half)
    - Stop Loss: Premium INCREASES by X% (e.g., 200% = loss is 2x credit)
    - DTE Management: Close at 21 DTE to avoid assignment risk

    Configuration section: sell_puts
    """

    def __init__(self, config: dict[str, Any], market_data: Any, brokerage_client: Any):
        """Initialize the Sell Puts strategy."""
        super().__init__(config, market_data, brokerage_client)

        # Initialize order executor
        self._order_executor = OrderExecutor(client=brokerage_client, market_data=market_data)

        # Cache for strategy-specific config
        self._strategy_config: dict[str, Any] | None = None

        self.logger.info(f"SellPutsStrategy initialized (enabled={self.is_enabled()})")

    # =========================================================================
    # Abstract Method Implementations
    # =========================================================================

    def get_name(self) -> str:
        """Return unique strategy identifier."""
        return "sell_puts"

    def get_config_section(self) -> str:
        """Return the configuration section name."""
        return "sell_puts"

    def get_plays_base_dir(self) -> str:
        """Return base directory for play files."""
        return "plays"

    def get_priority(self) -> int:
        """Return execution priority (lower = higher priority)."""
        return 50  # Medium-high priority (after option_swings)

    # =========================================================================
    # Order Action Overrides - This strategy SELLS premium
    # =========================================================================

    def get_default_entry_action(self) -> OrderAction:
        """
        Return SELL_TO_OPEN as this strategy sells puts to collect premium.

        Unlike option_swings which buys options (BTO), sell_puts writes options
        to collect premium, requiring SELL_TO_OPEN for entry.
        """
        return OrderAction.SELL_TO_OPEN

    def get_default_exit_action(self) -> OrderAction:
        """
        Return BUY_TO_CLOSE to exit short put positions.

        To close a short put position, we must buy it back.
        """
        return OrderAction.BUY_TO_CLOSE

    # =========================================================================
    # Entry Evaluation
    # =========================================================================

    def evaluate_new_plays(self, plays: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Evaluate plays in NEW status for entry conditions.

        For sell_puts, checks:
        1. Stock price is in acceptable range for selling puts
        2. Play hasn't expired
        3. Required fields are present
        4. DTE is within acceptable range
        5. Premium meets minimum requirements (from playbook)

        Args:
            plays: List of play dictionaries from 'new' folder

        Returns:
            List of plays that should be opened (entry conditions met)
        """
        plays_to_open = []

        for play in plays:
            play_file = play.get("_play_file", "")
            symbol = play.get("symbol", "")

            try:
                # Validate required fields
                if not self.validate_play(play):
                    self.logger.warning(f"Play validation failed: {play_file}")
                    continue

                # Check for play expiration
                if self._is_play_expired(play):
                    self.logger.info(f"Play expired, skipping: {symbol}")
                    continue

                # Check DTE is acceptable
                if not self._is_dte_acceptable(play):
                    self.logger.debug(f"DTE outside range for: {symbol}")
                    continue

                # Evaluate entry conditions
                should_enter = self._evaluate_entry_conditions(play)

                if should_enter:
                    self.log_trade_action(
                        "ENTRY_SIGNAL",
                        play,
                        {
                            "action": "STO",
                            "entry_point": play.get("entry_point", {}).get("stock_price"),
                            "order_type": play.get("entry_point", {}).get("order_type"),
                            "premium": play.get("entry_point", {}).get("entry_premium"),
                        },
                    )
                    plays_to_open.append(play)

            except Exception as e:
                self.logger.error(f"Error evaluating new play {symbol}: {e}")
                continue

        return plays_to_open

    def _evaluate_entry_conditions(self, play: dict[str, Any]) -> bool:
        """
        Evaluate if entry conditions are met for a sell_puts play.

        For selling puts, we typically want:
        - Stock price at or above entry target (selling puts on pullback)
        - Premium meets minimum threshold
        - Acceptable bid-ask spread

        Args:
            play: Play dictionary

        Returns:
            True if entry conditions met
        """
        symbol = play.get("symbol", "")
        entry_point = play.get("entry_point", {})
        entry_stock_price = entry_point.get("stock_price", 0)

        # Get current stock price
        current_price = self._get_stock_price(symbol)
        if current_price is None:
            self.logger.error(f"Could not get current price for {symbol}")
            return False

        # Get config buffer (default to 0.05 for 5 cent tolerance)
        from goldflipper.config.config import config

        buffer = config.get("entry_strategy", "buffer", default=0.05)

        # For sell_puts, entry is when stock is near target (within buffer)
        lower_bound = entry_stock_price - buffer
        upper_bound = entry_stock_price + buffer

        condition_met = lower_bound <= current_price <= upper_bound

        if condition_met:
            self.logger.info(f"[SELL_PUTS] Entry condition met: {symbol} @ ${current_price:.2f} (target: ${lower_bound:.2f}-${upper_bound:.2f})")

            # Check premium requirements if option data available
            option_symbol = play.get("option_contract_symbol")
            if option_symbol:
                option_data = self._get_option_data(option_symbol)
                if option_data:
                    # Get minimum premium from playbook or play
                    min_premium = self.get_playbook_setting(play, "entry.min_premium", play.get("entry_point", {}).get("min_premium", 0.50))
                    current_premium = option_data.get("bid", 0)

                    if current_premium < min_premium:
                        self.logger.info(f"Premium ${current_premium:.2f} below minimum ${min_premium:.2f}")
                        return False
        else:
            self.logger.debug(f"[SELL_PUTS] Entry not met: {symbol} @ ${current_price:.2f} (target: ${lower_bound:.2f}-${upper_bound:.2f})")

        return condition_met

    # =========================================================================
    # Exit Evaluation
    # =========================================================================

    def evaluate_open_plays(self, plays: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """
        Evaluate open positions for exit conditions.

        For sell_puts (short premium), exit conditions are INVERTED:
        - Take Profit: Premium DECREASED (can buy back cheaper)
        - Stop Loss: Premium INCREASED (losing money)

        Also checks:
        - DTE management (close at 21 DTE)
        - ITM management (roll or close if put goes ITM)

        Args:
            plays: List of play dictionaries from 'open' folder

        Returns:
            List of tuples: (play, close_conditions) for plays that should close
        """
        plays_to_close = []

        for play in plays:
            play_file = play.get("_play_file", "")
            symbol = play.get("symbol", "")

            try:
                # Evaluate exit conditions
                close_conditions = self._evaluate_exit_conditions(play, play_file)

                if close_conditions.get("should_close", False):
                    # Determine close type for logging
                    close_type = "TP" if close_conditions.get("is_profit") else "SL"
                    if close_conditions.get("is_dte_exit"):
                        close_type = "DTE_MGMT"
                    elif close_conditions.get("is_itm_exit"):
                        close_type = "ITM_MGMT"

                    self.log_trade_action(
                        f"EXIT_SIGNAL_{close_type}",
                        play,
                        {"action": "BTC", "is_profit": close_conditions.get("is_profit"), "reason": close_conditions.get("exit_reason")},
                    )

                    plays_to_close.append((play, close_conditions))

            except Exception as e:
                self.logger.error(f"Error evaluating open play {symbol}: {e}")
                continue

        return plays_to_close

    def _evaluate_exit_conditions(self, play: dict[str, Any], play_file: str | None = None) -> dict[str, Any]:
        """
        Evaluate exit conditions for a short put position.

        For SHORT positions (sell_puts), profit/loss logic is INVERTED:
        - PROFIT: Premium DECREASES (we can buy back cheaper than we sold)
        - LOSS: Premium INCREASES (we have to pay more to close)

        Args:
            play: Play dictionary
            play_file: Path to play file

        Returns:
            Dict with condition flags
        """
        symbol = play.get("symbol", "")
        option_symbol = play.get("option_contract_symbol", "")

        # Initialize result
        result = {
            "should_close": False,
            "is_profit": False,
            "is_primary_loss": False,
            "is_contingency_loss": False,
            "is_dte_exit": False,
            "is_itm_exit": False,
            "exit_reason": None,
            "sl_type": play.get("stop_loss", {}).get("SL_type", "LIMIT"),
        }

        # Get option data
        option_data = self._get_option_data(option_symbol)
        if not option_data:
            self.logger.warning(f"Could not get option data for {option_symbol}")
            return result

        current_premium = option_data.get("ask", 0)  # For BTC, we pay the ask

        # Get entry premium (credit received when we sold)
        entry_premium = play.get("entry_point", {}).get("entry_premium", 0)
        if entry_premium <= 0:
            entry_premium = play.get("logging", {}).get("premium_atOpen", 0)

        if entry_premium <= 0:
            self.logger.warning(f"No entry premium recorded for {symbol}")
            return result

        # =================================================================
        # CHECK DTE MANAGEMENT (Priority 1)
        # =================================================================
        dte_exit = self._check_dte_management(play)
        if dte_exit:
            result["should_close"] = True
            result["is_dte_exit"] = True
            result["is_profit"] = current_premium < entry_premium
            result["exit_reason"] = "DTE management - closing before expiration"
            return result

        # =================================================================
        # CHECK ITM STATUS (Priority 2)
        # =================================================================
        itm_exit = self._check_itm_status(play)
        if itm_exit:
            result["should_close"] = True
            result["is_itm_exit"] = True
            result["is_primary_loss"] = True
            result["exit_reason"] = "Put went ITM - closing to avoid assignment"
            return result

        # =================================================================
        # CHECK TAKE PROFIT (Premium decreased)
        # =================================================================
        # For SHORT positions: profit when premium DECREASES
        # If we sold at $1.00 and TP is 50%, we close when premium is $0.50

        tp_pct = play.get("take_profit", {}).get("premium_pct")
        if tp_pct is None:
            tp_pct = self.get_playbook_setting(play, "exit.take_profit_pct", 50.0)

        if tp_pct and entry_premium > 0:
            # TP target: premium should drop by this percentage
            # If TP is 50%, target premium = entry * (1 - 0.50) = 50% of entry
            target_premium = entry_premium * (1 - tp_pct / 100)

            if current_premium <= target_premium:
                profit_pct = ((entry_premium - current_premium) / entry_premium) * 100
                result["should_close"] = True
                result["is_profit"] = True
                result["exit_reason"] = f"Take Profit: Premium dropped from ${entry_premium:.2f} to ${current_premium:.2f} ({profit_pct:.1f}% profit)"

                self.logger.info(f"[SELL_PUTS] TP hit for {symbol}: {result['exit_reason']}")
                return result

        # =================================================================
        # CHECK STOP LOSS (Premium increased)
        # =================================================================
        # For SHORT positions: loss when premium INCREASES
        # If we sold at $1.00 and SL is 200%, we close when premium is $3.00

        sl_pct = play.get("stop_loss", {}).get("premium_pct")
        if sl_pct is None:
            sl_pct = self.get_playbook_setting(play, "exit.stop_loss_pct", 200.0)

        max_loss_multiple = play.get("stop_loss", {}).get("max_loss_multiple")
        if max_loss_multiple is None:
            max_loss_multiple = self.get_playbook_setting(play, "exit.max_loss_multiple", 2.0)

        if entry_premium > 0:
            # Method 1: Premium percentage increase
            if sl_pct:
                # SL target: premium should NOT exceed this increase
                # If SL is 200%, target premium = entry * (1 + 2.00) = 3x entry
                sl_target = entry_premium * (1 + sl_pct / 100)

                if current_premium >= sl_target:
                    loss_pct = ((current_premium - entry_premium) / entry_premium) * 100
                    result["should_close"] = True
                    result["is_primary_loss"] = True
                    result["exit_reason"] = f"Stop Loss: Premium rose from ${entry_premium:.2f} to ${current_premium:.2f} ({loss_pct:.1f}% loss)"

                    self.logger.warning(f"[SELL_PUTS] SL hit for {symbol}: {result['exit_reason']}")
                    return result

            # Method 2: Max loss multiple (e.g., 2x credit received)
            elif max_loss_multiple:
                max_loss_premium = entry_premium * (1 + max_loss_multiple)

                if current_premium >= max_loss_premium:
                    result["should_close"] = True
                    result["is_primary_loss"] = True
                    result["exit_reason"] = (
                        f"Max Loss Multiple: Premium at ${current_premium:.2f} exceeds {max_loss_multiple}x credit (${max_loss_premium:.2f})"
                    )

                    self.logger.warning(f"[SELL_PUTS] Max loss for {symbol}: {result['exit_reason']}")
                    return result

        # No exit conditions met
        self.logger.debug(f"[SELL_PUTS] Hold {symbol}: premium ${current_premium:.2f} (entry: ${entry_premium:.2f})")

        return result

    def _check_dte_management(self, play: dict[str, Any]) -> bool:
        """
        Check if position should be closed due to DTE management.

        TastyTrade methodology: Close at 21 DTE to avoid gamma risk
        and potential assignment.

        Args:
            play: Play dictionary

        Returns:
            True if should close due to DTE
        """
        expiration_str = play.get("expiration_date")
        if not expiration_str:
            return False

        try:
            expiration = datetime.strptime(expiration_str, "%m/%d/%Y").date()
            today = datetime.now().date()
            dte = (expiration - today).days

            # Get close_at_dte from play, playbook, or default to 21
            close_at_dte = play.get("management", {}).get("close_at_dte")
            if close_at_dte is None:
                close_at_dte = self.get_playbook_setting(play, "exit.close_before_dte", 21)

            if dte <= close_at_dte:
                self.logger.info(f"DTE management triggered: {dte} DTE <= {close_at_dte}")
                return True

        except ValueError:
            self.logger.warning(f"Invalid expiration date format: {expiration_str}")

        return False

    def _check_itm_status(self, play: dict[str, Any]) -> bool:
        """
        Check if put has gone in-the-money (stock below strike).

        If roll_if_itm is True and put is ITM, signal for closure
        (rolling would be handled separately).

        Args:
            play: Play dictionary

        Returns:
            True if should close due to ITM status
        """
        symbol = play.get("symbol", "")
        strike_price = play.get("strike_price", 0)

        # Check if we should exit on ITM
        roll_if_itm = play.get("management", {}).get("roll_if_itm")
        if roll_if_itm is None:
            roll_if_itm = self.get_playbook_setting(play, "sell_puts_config.roll_if_itm", True)

        if not roll_if_itm:
            return False

        current_price = self._get_stock_price(symbol)
        if current_price is None:
            return False

        # Put is ITM if stock price < strike price
        if current_price < strike_price:
            self.logger.warning(f"Put ITM: {symbol} @ ${current_price:.2f} < strike ${strike_price:.2f}")
            return True

        return False

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_play(self, play: dict[str, Any]) -> bool:
        """
        Validate play data structure for sell_puts strategy.
        """
        # Base validation
        if not super().validate_play(play):
            return False

        # Sell puts specific required fields
        required_fields = ["strike_price", "expiration_date", "contracts", "entry_point", "take_profit", "stop_loss"]

        for field in required_fields:
            if field not in play:
                self.logger.warning(f"Play missing required field: {field}")
                return False

        # Validate trade_type is PUT
        if play.get("trade_type", "").upper() != "PUT":
            self.logger.warning("sell_puts strategy requires trade_type: PUT")
            return False

        # Validate action is STO (if specified)
        action = play.get("action", "STO").upper()
        if action not in ("STO", "SELL_TO_OPEN"):
            self.logger.warning(f"sell_puts requires action: STO, got: {action}")
            return False

        return True

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_stock_price(self, symbol: str) -> float | None:
        """Get current stock price."""
        try:
            price = self.market_data.get_stock_price(symbol)
            if price is not None:
                if hasattr(price, "item"):
                    price = float(price.item())
                return float(price)
            return None
        except Exception as e:
            self.logger.error(f"Error getting stock price for {symbol}: {e}")
            return None

    def _get_option_data(self, option_symbol: str) -> dict[str, float] | None:
        """Get current option quote data."""
        try:
            return self.market_data.get_option_quote(option_symbol)
        except Exception as e:
            self.logger.error(f"Error getting option data for {option_symbol}: {e}")
            return None

    def _is_play_expired(self, play: dict[str, Any]) -> bool:
        """Check if play has passed its expiration date."""
        play_expiration = play.get("play_expiration_date")
        if not play_expiration:
            return False

        try:
            exp_date = datetime.strptime(play_expiration, "%m/%d/%Y").date()
            return exp_date < datetime.now().date()
        except ValueError:
            self.logger.warning(f"Invalid play_expiration_date: {play_expiration}")
            return False

    def _is_dte_acceptable(self, play: dict[str, Any]) -> bool:
        """
        Check if option DTE is within acceptable range.

        Uses playbook settings if available.
        """
        expiration_str = play.get("expiration_date")
        if not expiration_str:
            return True  # No expiration = allow

        try:
            expiration = datetime.strptime(expiration_str, "%m/%d/%Y").date()
            today = datetime.now().date()
            dte = (expiration - today).days

            # Get DTE range from playbook or defaults
            dte_min = self.get_playbook_setting(play, "entry.dte_min", 30)
            dte_max = self.get_playbook_setting(play, "entry.dte_max", 60)

            return dte_min <= dte <= dte_max

        except ValueError:
            return True

    def _calculate_collateral(self, play: dict[str, Any]) -> float:
        """
        Calculate cash collateral required for a cash-secured put.

        Collateral = Strike Price × 100 × Number of Contracts

        Args:
            play: Play dictionary

        Returns:
            Required collateral amount
        """
        strike = play.get("strike_price", 0)
        contracts = play.get("contracts", 1)
        return strike * 100 * contracts

    def get_strategy_config(self) -> dict[str, Any]:
        """Get cached strategy configuration."""
        if self._strategy_config is None:
            config_section = self.config.get(self.get_config_section())
            self._strategy_config = config_section if config_section is not None else {}
        return self._strategy_config if self._strategy_config is not None else {}

    # =========================================================================
    # Order Execution Methods
    # =========================================================================

    def open_position(self, play: dict[str, Any], play_file: str) -> bool:
        """
        Open a short put position.

        Args:
            play: Play data dictionary
            play_file: Path to play file

        Returns:
            True if position opened successfully
        """
        # Import here to avoid circular dependency
        from goldflipper.core import open_position as core_open_position

        return core_open_position(play, play_file)

    def close_position(self, play: dict[str, Any], close_conditions: dict[str, Any], play_file: str) -> bool:
        """
        Close an open short put position.

        Args:
            play: Play data dictionary
            close_conditions: Exit conditions from evaluate_open_plays
            play_file: Path to play file

        Returns:
            True if position closed successfully
        """
        # Import here to avoid circular dependency
        from goldflipper.core import close_position as core_close_position

        return core_close_position(play, close_conditions, play_file)


__all__ = ["SellPutsStrategy"]

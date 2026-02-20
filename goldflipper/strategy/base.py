"""
Base Strategy Module for Goldflipper Multi-Strategy System

This module defines the abstract base class that all trading strategies must implement.
It provides a consistent interface for strategy evaluation, execution, and lifecycle management.

Usage:
    from goldflipper.strategy.base import BaseStrategy
    from goldflipper.strategy.registry import register_strategy

    @register_strategy('my_strategy')
    class MyStrategy(BaseStrategy):
        def get_name(self) -> str:
            return "my_strategy"
        # ... implement other abstract methods
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any


class StrategyPhase(Enum):
    """
    Phases a strategy can operate in during its lifecycle.

    SCANNING: Looking for new opportunities (not yet implemented)
    ENTRY: Evaluating entry conditions for pending plays
    MONITORING: Managing open positions
    EXIT: Evaluating exit conditions
    """

    SCANNING = "scanning"
    ENTRY = "entry"
    MONITORING = "monitoring"
    EXIT = "exit"


class OrderAction(Enum):
    """
    Options order action types representing the four fundamental order directions.

    For LONG positions (buying premium):
        BUY_TO_OPEN: Establish long position by buying option
        SELL_TO_CLOSE: Exit long position by selling option

    For SHORT positions (selling/writing premium):
        SELL_TO_OPEN: Establish short position by selling/writing option
        BUY_TO_CLOSE: Exit short position by buying back option

    Usage:
        - option_swings (buy calls/puts): BUY_TO_OPEN → SELL_TO_CLOSE
        - sell_puts (cash-secured): SELL_TO_OPEN → BUY_TO_CLOSE
        - spreads: Multiple legs with different actions
        - covered_calls: SELL_TO_OPEN → BUY_TO_CLOSE

    The action affects:
        - Order submission (buy vs sell)
        - P&L calculation (profit = premium up vs down)
        - Risk profile (limited vs unlimited risk)
        - Margin requirements
    """

    BUY_TO_OPEN = "BTO"  # Long: buy premium to open position
    SELL_TO_CLOSE = "STC"  # Close long: sell premium to exit
    SELL_TO_OPEN = "STO"  # Short: collect premium by writing option
    BUY_TO_CLOSE = "BTC"  # Close short: buy back to exit

    @classmethod
    def from_string(cls, value: str) -> "OrderAction":
        """
        Convert string to OrderAction enum.

        Args:
            value: String value (e.g., 'BTO', 'buy_to_open', 'BUY_TO_OPEN')

        Returns:
            OrderAction enum value

        Raises:
            ValueError: If string doesn't match any action
        """
        value_upper = value.upper().replace(" ", "_").replace("-", "_")

        # Try direct match to value (BTO, STC, etc.)
        for action in cls:
            if action.value == value_upper:
                return action

        # Try match to name (BUY_TO_OPEN, etc.)
        for action in cls:
            if action.name == value_upper:
                return action

        raise ValueError(f"Unknown OrderAction: {value}")

    def is_opening(self) -> bool:
        """Return True if this action opens a position."""
        return self in (OrderAction.BUY_TO_OPEN, OrderAction.SELL_TO_OPEN)

    def is_closing(self) -> bool:
        """Return True if this action closes a position."""
        return self in (OrderAction.SELL_TO_CLOSE, OrderAction.BUY_TO_CLOSE)

    def is_long(self) -> bool:
        """Return True if this action is for a long position."""
        return self in (OrderAction.BUY_TO_OPEN, OrderAction.SELL_TO_CLOSE)

    def is_short(self) -> bool:
        """Return True if this action is for a short position."""
        return self in (OrderAction.SELL_TO_OPEN, OrderAction.BUY_TO_CLOSE)

    def is_buy(self) -> bool:
        """Return True if this action results in a buy order."""
        return self in (OrderAction.BUY_TO_OPEN, OrderAction.BUY_TO_CLOSE)

    def is_sell(self) -> bool:
        """Return True if this action results in a sell order."""
        return self in (OrderAction.SELL_TO_OPEN, OrderAction.SELL_TO_CLOSE)

    def get_closing_action(self) -> "OrderAction":
        """
        Get the corresponding closing action for an opening action.

        Returns:
            The closing OrderAction that would exit a position opened with this action.

        Raises:
            ValueError: If called on a closing action
        """
        if self == OrderAction.BUY_TO_OPEN:
            return OrderAction.SELL_TO_CLOSE
        elif self == OrderAction.SELL_TO_OPEN:
            return OrderAction.BUY_TO_CLOSE
        else:
            raise ValueError(f"Cannot get closing action for {self.name} - already a closing action")

    def get_opening_action(self) -> "OrderAction":
        """
        Get the corresponding opening action for a closing action.

        Returns:
            The opening OrderAction that would have established this position.

        Raises:
            ValueError: If called on an opening action
        """
        if self == OrderAction.SELL_TO_CLOSE:
            return OrderAction.BUY_TO_OPEN
        elif self == OrderAction.BUY_TO_CLOSE:
            return OrderAction.SELL_TO_OPEN
        else:
            raise ValueError(f"Cannot get opening action for {self.name} - already an opening action")


class PlayStatus(Enum):
    """
    Standard play status values used across all strategies.
    Maps to folder structure in plays/ directory.
    """

    NEW = "NEW"
    PENDING_OPENING = "PENDING-OPENING"
    OPEN = "OPEN"
    PENDING_CLOSING = "PENDING-CLOSING"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    TEMP = "TEMP"


class PositionSide(Enum):
    """
    Position side indicating whether a position is long or short.

    LONG: Bought premium, profit when premium increases
    SHORT: Sold/wrote premium, profit when premium decreases (or expires worthless)
    """

    LONG = "long"
    SHORT = "short"

    @classmethod
    def from_order_action(cls, action: OrderAction) -> "PositionSide":
        """Determine position side from the opening order action."""
        if action.is_long():
            return cls.LONG
        return cls.SHORT


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies in Goldflipper.

    Each strategy must implement the abstract methods to define:
    - Strategy identification (name, config section)
    - Play directory structure
    - Entry evaluation logic
    - Exit evaluation logic

    Optionally override:
    - on_cycle_start(): Called at start of each monitoring cycle
    - on_cycle_end(): Called at end of each monitoring cycle
    - get_priority(): Execution priority (lower = earlier)
    - validate_play(): Custom play validation

    Attributes:
        config (Dict[str, Any]): Full application configuration dictionary
        market_data: MarketDataManager instance for price/quote data
        client: Alpaca TradingClient instance for order execution
        logger: Logger instance for this strategy

    Example:
        @register_strategy('option_swings')
        class OptionSwingsStrategy(BaseStrategy):
            def get_name(self) -> str:
                return "option_swings"

            def get_config_section(self) -> str:
                return "options_swings"

            def get_plays_base_dir(self) -> str:
                return "plays"

            def evaluate_new_plays(self, plays):
                # Check entry conditions
                return [p for p in plays if self._should_enter(p)]

            def evaluate_open_plays(self, plays):
                # Check exit conditions
                results = []
                for play in plays:
                    conditions = self._check_exit(play)
                    if conditions['should_close']:
                        results.append((play, conditions))
                return results
    """

    def __init__(
        self,
        config: dict[str, Any],
        market_data: Any,  # MarketDataManager
        brokerage_client: Any,  # TradingClient
    ):
        """
        Initialize the strategy with shared resources.

        Args:
            config: Full application configuration dictionary
            market_data: MarketDataManager instance for fetching prices/quotes
            brokerage_client: Alpaca TradingClient for order execution
        """
        self.config = config
        self.market_data = market_data
        self.client = brokerage_client
        self.logger = logging.getLogger(f"goldflipper.strategy.{self.get_name()}")
        self._enabled: bool | None = None
        self._last_cycle_time: datetime | None = None
        self.capital_manager: Any | None = None  # Injected by orchestrator after init

    # =========================================================================
    # Abstract Methods - MUST be implemented by subclasses
    # =========================================================================

    @abstractmethod
    def get_name(self) -> str:
        """
        Return unique strategy identifier.

        This name is used for:
        - Logging and display
        - Registry lookup
        - Configuration mapping

        Returns:
            str: Unique strategy name (e.g., 'option_swings', 'momentum')

        Example:
            def get_name(self) -> str:
                return "option_swings"
        """
        pass

    @abstractmethod
    def get_config_section(self) -> str:
        """
        Return the configuration section name for this strategy.

        This maps to a top-level key in settings.yaml where strategy-specific
        settings are defined.

        Returns:
            str: Config section key (e.g., 'options_swings', 'momentum')

        Example:
            def get_config_section(self) -> str:
                return "options_swings"  # maps to settings.yaml options_swings: {...}
        """
        pass

    @abstractmethod
    def get_plays_base_dir(self) -> str:
        """
        Return base directory for this strategy's play files.

        Can be:
        - Shared directory: "plays" (all strategies share same folders)
        - Strategy-specific: "plays/option_swings" (isolated folders)

        The directory should contain subfolders: new/, open/, closed/, etc.

        Returns:
            str: Relative path from goldflipper package root

        Example:
            def get_plays_base_dir(self) -> str:
                return "plays"  # Uses shared structure
        """
        pass

    @abstractmethod
    def evaluate_new_plays(self, plays: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Evaluate plays awaiting entry and return those that should be opened.

        This method is called with plays from the 'new' folder. Implement your
        entry condition logic here.

        Args:
            plays: List of play dictionaries from the 'new' folder

        Returns:
            List of plays that meet entry conditions and should be opened.
            Each play should include its file path in 'play_file' key.

        Example:
            def evaluate_new_plays(self, plays):
                plays_to_open = []
                for play in plays:
                    if self._check_entry_conditions(play):
                        plays_to_open.append(play)
                return plays_to_open
        """
        pass

    @abstractmethod
    def evaluate_open_plays(self, plays: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """
        Evaluate open positions and return those that should be closed.

        This method is called with plays from the 'open' folder. Implement your
        exit condition logic (TP/SL) here.

        Args:
            plays: List of play dictionaries from the 'open' folder

        Returns:
            List of tuples: (play, close_conditions)

            close_conditions should be a dict with at least:
            - 'should_close': bool - Whether to close the position
            - 'is_profit': bool - True if closing for take profit
            - 'is_primary_loss': bool - True if closing for stop loss
            - 'is_contingency_loss': bool - True if closing for contingency SL

        Example:
            def evaluate_open_plays(self, plays):
                plays_to_close = []
                for play in plays:
                    conditions = self._check_exit_conditions(play)
                    if conditions['should_close']:
                        plays_to_close.append((play, conditions))
                return plays_to_close
        """
        pass

    # =========================================================================
    # Optional Override Methods
    # =========================================================================

    def get_priority(self) -> int:
        """
        Return execution priority for this strategy.

        Lower values = higher priority (runs earlier in cycle).
        Used by orchestrator to determine execution order.

        Default: 100

        Returns:
            int: Priority value (lower runs first)

        Example priorities:
            - 10: High priority (e.g., main trading strategy)
            - 50: Medium priority
            - 100: Default priority
            - 200: Low priority (e.g., cleanup tasks)
        """
        return 100

    def is_enabled(self) -> bool:
        """
        Check if this strategy is enabled in configuration.

        Reads from the strategy's config section 'enabled' key.
        Result is cached after first call.

        Returns:
            bool: True if strategy should run, False otherwise
        """
        if self._enabled is None:
            self._enabled = self._load_enabled_state()
        return self._enabled

    def _load_enabled_state(self) -> bool:
        """
        Load enabled state from configuration.

        Override this method if your strategy uses a different config structure.

        Returns:
            bool: Whether strategy is enabled
        """
        section = self.config.get(self.get_config_section(), {})
        return section.get("enabled", False)

    def on_cycle_start(self) -> None:
        """
        Hook called at the start of each monitoring cycle.

        Use this for:
        - Refreshing cached data
        - Logging cycle start
        - Pre-cycle validation

        Default implementation logs cycle start.
        """
        self._last_cycle_time = datetime.now()
        self.logger.debug(f"Strategy {self.get_name()} starting cycle")

    def on_cycle_end(self) -> None:
        """
        Hook called at the end of each monitoring cycle.

        Use this for:
        - Cleanup operations
        - Metrics collection
        - Logging cycle completion

        Default implementation logs cycle end.
        """
        self.logger.debug(f"Strategy {self.get_name()} completed cycle")

    def validate_play(self, play: dict[str, Any]) -> bool:
        """
        Validate play data structure.

        Override to add strategy-specific validation beyond the base requirements.

        Args:
            play: Play dictionary to validate

        Returns:
            bool: True if play is valid, False otherwise
        """
        # Base required fields for all strategies
        required_fields = ["symbol", "trade_type", "status"]

        for field in required_fields:
            if field not in play:
                self.logger.warning(f"Play missing required field: {field}")
                return False

        # Validate status is a dictionary
        if not isinstance(play.get("status"), dict):
            self.logger.warning("Play 'status' field must be a dictionary")
            return False

        return True

    # =========================================================================
    # Order Action Methods
    # =========================================================================

    def get_default_entry_action(self) -> OrderAction:
        """
        Return the default order action for opening positions in this strategy.

        Override this method to change the default entry action.
        Strategies can also read the action from play files to allow per-play override.

        Default: BUY_TO_OPEN (long premium)

        Returns:
            OrderAction: Default action for opening new positions

        Example overrides:
            - SellPutsStrategy: return OrderAction.SELL_TO_OPEN
            - CoveredCallsStrategy: return OrderAction.SELL_TO_OPEN
        """
        return OrderAction.BUY_TO_OPEN

    def get_default_exit_action(self) -> OrderAction:
        """
        Return the default order action for closing positions in this strategy.

        Override this method to change the default exit action.
        Should correspond to get_default_entry_action().

        Default: SELL_TO_CLOSE (close long position)

        Returns:
            OrderAction: Default action for closing positions
        """
        return OrderAction.SELL_TO_CLOSE

    def get_position_side(self) -> PositionSide:
        """
        Return the position side for this strategy based on default entry action.

        Returns:
            PositionSide.LONG for BTO strategies
            PositionSide.SHORT for STO strategies
        """
        return PositionSide.from_order_action(self.get_default_entry_action())

    def get_entry_action_for_play(self, play: dict[str, Any]) -> OrderAction:
        """
        Get the entry action for a specific play.

        Checks play for explicit 'action' or 'entry_action' field.
        Falls back to strategy default if not specified.

        Args:
            play: Play dictionary

        Returns:
            OrderAction for opening this play's position
        """
        # Check for explicit action in play
        action_str = play.get("action") or play.get("entry_action")

        if action_str:
            try:
                return OrderAction.from_string(action_str)
            except ValueError:
                self.logger.warning(f"Invalid action '{action_str}' in play, using strategy default")

        return self.get_default_entry_action()

    def get_exit_action_for_play(self, play: dict[str, Any]) -> OrderAction:
        """
        Get the exit action for a specific play.

        Derives from entry action to ensure correct pairing.

        Args:
            play: Play dictionary

        Returns:
            OrderAction for closing this play's position
        """
        entry_action = self.get_entry_action_for_play(play)
        return entry_action.get_closing_action()

    def is_long_strategy(self) -> bool:
        """Return True if this strategy primarily takes long positions (buys premium)."""
        return self.get_default_entry_action().is_long()

    def is_short_strategy(self) -> bool:
        """Return True if this strategy primarily takes short positions (sells/writes premium)."""
        return self.get_default_entry_action().is_short()

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_strategy_config(self) -> dict[str, Any]:
        """
        Get the configuration section for this strategy.

        Returns:
            Dict containing strategy-specific configuration
        """
        return self.config.get(self.get_config_section(), {})

    def get_plays_dir(self, status: PlayStatus) -> str:
        """
        Get the full path to a play status directory.

        Uses account-aware path resolution from exe_utils for proper support of:
        - Multi-account directory structure (plays/account_X/shared/...)
        - Nuitka onefile mode (persistent data next to exe)

        Args:
            status: PlayStatus enum value

        Returns:
            str: Full path to the directory (e.g., plays/account_2/shared/new/)
        """
        # Import here to avoid circular imports
        from goldflipper.utils.exe_utils import get_play_subdir

        # Map status to folder name
        folder_map = {
            PlayStatus.NEW: "new",
            PlayStatus.PENDING_OPENING: "pending-opening",
            PlayStatus.OPEN: "open",
            PlayStatus.PENDING_CLOSING: "pending-closing",
            PlayStatus.CLOSED: "closed",
            PlayStatus.EXPIRED: "expired",
            PlayStatus.TEMP: "temp",
        }

        folder = folder_map.get(status, status.value.lower())

        # Use exe-aware, account-aware path resolution
        # This returns: plays/{active_account_dir}/shared/{folder}/
        return str(get_play_subdir(folder))

    def log_trade_action(self, action: str, play: dict[str, Any], details: dict[str, Any] | None = None) -> None:
        """
        Log a trade action with consistent formatting.

        Args:
            action: Action type (e.g., 'ENTRY', 'EXIT', 'TP', 'SL')
            play: Play dictionary
            details: Optional additional details to log
        """
        symbol = play.get("symbol", "UNKNOWN")
        trade_type = play.get("trade_type", "UNKNOWN")

        msg = f"[{self.get_name().upper()}] {action}: {symbol} {trade_type}"

        if details:
            detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
            msg += f" ({detail_str})"

        self.logger.info(msg)

    # =========================================================================
    # Playbook Methods
    # =========================================================================

    def get_playbook_for_play(self, play: dict[str, Any]) -> Any | None:
        """
        Load the playbook associated with a play.

        Looks for 'playbook' field in the play data. If not found, returns
        the default playbook for this strategy.

        Args:
            play: Play dictionary

        Returns:
            Playbook instance or None if not found
        """
        try:
            from goldflipper.strategy.playbooks import load_playbook, load_playbook_for_play

            # Try to load playbook referenced in play
            playbook = load_playbook_for_play(play)

            if playbook:
                return playbook

            # Fall back to default playbook for this strategy
            return load_playbook(self.get_name(), "default")

        except ImportError:
            self.logger.debug("Playbook module not available")
            return None
        except Exception as e:
            self.logger.warning(f"Error loading playbook for play: {e}")
            return None

    def get_default_playbook(self) -> Any | None:
        """
        Load the default playbook for this strategy.

        Returns:
            Playbook instance or None if not found
        """
        try:
            from goldflipper.strategy.playbooks import load_playbook

            return load_playbook(self.get_name(), "default")
        except ImportError:
            self.logger.debug("Playbook module not available")
            return None
        except Exception as e:
            self.logger.warning(f"Error loading default playbook: {e}")
            return None

    def get_playbook_setting(self, play: dict[str, Any], setting_path: str, default: Any = None) -> Any:
        """
        Get a setting from the play's playbook.

        Navigates the playbook using dot-notation path.

        Args:
            play: Play dictionary
            setting_path: Dot-notation path (e.g., 'exit.take_profit_pct')
            default: Default value if setting not found

        Returns:
            Setting value or default

        Example:
            tp_pct = self.get_playbook_setting(play, 'exit.take_profit_pct', 50.0)
        """
        playbook = self.get_playbook_for_play(play)

        if not playbook:
            return default

        # Navigate the path
        parts = setting_path.split(".")
        current = playbook

        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current if current is not None else default

    def __repr__(self) -> str:
        """String representation of strategy."""
        return f"<{self.__class__.__name__} name='{self.get_name()}' enabled={self.is_enabled()} priority={self.get_priority()}>"

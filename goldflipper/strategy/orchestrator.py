"""
Strategy Orchestrator for Goldflipper Multi-Strategy System

This module coordinates the execution of multiple trading strategies, managing
their lifecycle, execution order, and shared resource access.

The orchestrator supports two execution modes:
- Sequential: Strategies run one after another (safer, easier to debug)
- Parallel: Strategies run concurrently using thread pools (faster)

Usage:
    from goldflipper.strategy.orchestrator import StrategyOrchestrator

    orchestrator = StrategyOrchestrator()
    orchestrator.initialize()

    # Run one cycle
    orchestrator.run_cycle()

    # Or run continuous monitoring
    orchestrator.run_continuous()
"""

import logging
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from typing import Any

from goldflipper.strategy.base import BaseStrategy, PlayStatus
from goldflipper.strategy.registry import StrategyRegistry
from goldflipper.utils.exe_utils import get_plays_dir


class ExecutionMode(Enum):
    """Execution mode for strategy orchestration."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class OrchestratorState(Enum):
    """State of the orchestrator."""

    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class StrategyOrchestrator:
    """
    Coordinates execution of multiple trading strategies.

    The orchestrator is responsible for:
    - Loading and initializing enabled strategies
    - Managing execution order based on priority
    - Coordinating shared resources (market data cache, brokerage client)
    - Supporting both parallel and sequential execution
    - Providing dry-run mode for testing

    Attributes:
        strategies (List[BaseStrategy]): Loaded and enabled strategies
        state (OrchestratorState): Current orchestrator state
        market_data: Shared MarketDataManager instance
        client: Shared Alpaca TradingClient instance

    Configuration (settings.yaml):
        strategy_orchestration:
          enabled: true
          mode: "sequential"  # or "parallel"
          max_parallel_workers: 3
          dry_run: false

    Example:
        # Initialize and run
        orchestrator = StrategyOrchestrator()
        orchestrator.initialize()

        while market_is_open():
            orchestrator.run_cycle()
            time.sleep(30)
    """

    def __init__(self, config: dict[str, Any] | None = None, market_data: Any | None = None, brokerage_client: Any | None = None):
        """
        Initialize the orchestrator.

        Args:
            config: Application configuration. If None, loaded from config module.
            market_data: MarketDataManager instance. If None, created on initialize().
            brokerage_client: Alpaca client. If None, created on initialize().
        """
        self.logger = logging.getLogger(__name__)
        self._config = config
        self._market_data = market_data
        self._client = brokerage_client

        self.strategies: list[BaseStrategy] = []
        self.state = OrchestratorState.UNINITIALIZED
        self._registry = StrategyRegistry()

        # Execution settings (loaded on initialize)
        self._execution_mode = ExecutionMode.SEQUENTIAL
        self._max_workers = 3
        self._enabled = False
        self._dry_run = False

        # Cycle tracking
        self._cycle_count = 0
        self._last_cycle_time: datetime | None = None
        self._cycle_errors: list[dict[str, Any]] = []

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def config(self) -> dict[str, Any]:
        """Get configuration dictionary, loading if necessary."""
        if self._config is None:
            from goldflipper.config.config import config as app_config

            self._config = app_config._config
        return self._config

    @property
    def market_data(self):
        """Get MarketDataManager instance."""
        return self._market_data

    @property
    def client(self):
        """Get brokerage client instance."""
        return self._client

    @property
    def is_enabled(self) -> bool:
        """Check if orchestrator is enabled in config."""
        return self._enabled

    @property
    def is_dry_run(self) -> bool:
        """Check if orchestrator is in dry-run mode."""
        return self._dry_run

    @property
    def cycle_count(self) -> int:
        """Get number of cycles executed."""
        return self._cycle_count

    # =========================================================================
    # Initialization
    # =========================================================================

    def initialize(self) -> bool:
        """
        Initialize the orchestrator and load strategies.

        This method:
        1. Loads configuration settings
        2. Creates shared resources (market data, brokerage) if not provided
        3. Discovers and loads enabled strategies
        4. Sorts strategies by priority

        Returns:
            bool: True if initialization successful

        Raises:
            RuntimeError: If initialization fails critically
        """
        self.logger.info("Initializing strategy orchestrator...")

        try:
            # Load orchestration settings
            self._load_settings()

            if not self._enabled:
                self.logger.info("Strategy orchestration is disabled in config")
                self.state = OrchestratorState.STOPPED
                return False

            # Initialize shared resources
            self._initialize_resources()

            # Discover and load strategies
            self._load_strategies()

            # Sort by priority
            self.strategies.sort(key=lambda s: s.get_priority())

            self.state = OrchestratorState.INITIALIZED
            dry_run_msg = " [DRY-RUN MODE]" if self._dry_run else ""
            self.logger.info(f"Orchestrator initialized: {len(self.strategies)} strategies ({self._execution_mode.value} mode){dry_run_msg}")

            return True

        except Exception as e:
            self.logger.error(f"Orchestrator initialization failed: {e}")
            self.state = OrchestratorState.ERROR
            raise RuntimeError(f"Failed to initialize orchestrator: {e}") from e

    def _load_settings(self) -> None:
        """Load orchestration settings from config."""
        orch_config = self.config.get("strategy_orchestration", {})

        self._enabled = orch_config.get("enabled", False)

        mode_str = orch_config.get("mode", "sequential").lower()
        self._execution_mode = ExecutionMode.PARALLEL if mode_str == "parallel" else ExecutionMode.SEQUENTIAL

        self._max_workers = orch_config.get("max_parallel_workers", 3)
        self._dry_run = orch_config.get("dry_run", False)

        self.logger.debug(
            f"Orchestrator settings: enabled={self._enabled}, mode={self._execution_mode.value}, workers={self._max_workers}, dry_run={self._dry_run}"
        )

    def _initialize_resources(self) -> None:
        """Initialize shared resources (market data, brokerage client)."""
        # Create market data manager if not provided
        if self._market_data is None:
            from goldflipper.data.market.manager import MarketDataManager

            self._market_data = MarketDataManager()
            self.logger.debug("Created MarketDataManager instance")

        # Create brokerage client if not provided
        if self._client is None:
            from goldflipper.alpaca_client import get_alpaca_client

            self._client = get_alpaca_client()
            self.logger.debug("Created Alpaca client instance")

    def _load_strategies(self) -> None:
        """Discover and instantiate enabled strategies."""
        # Discover all registered strategies
        self._registry.discover()

        available = self._registry.get_all_strategies()
        self.logger.debug(f"Found {len(available)} registered strategy classes")

        self.strategies = []

        for strategy_class in available:
            try:
                # Instantiate strategy with shared resources
                strategy = strategy_class(config=self.config, market_data=self._market_data, brokerage_client=self._client)

                if strategy.is_enabled():
                    self.strategies.append(strategy)
                    self.logger.info(f"Loaded strategy: {strategy.get_name()} (priority={strategy.get_priority()})")
                else:
                    self.logger.debug(f"Strategy disabled: {strategy.get_name()}")

            except Exception as e:
                self.logger.error(f"Failed to initialize strategy {strategy_class.__name__}: {e}")

        self.logger.info(f"Loaded {len(self.strategies)} enabled strategies: {[s.get_name() for s in self.strategies]}")

    # =========================================================================
    # Execution
    # =========================================================================

    def run_cycle(self) -> bool:
        """
        Execute one monitoring cycle for all strategies.

        A cycle consists of:
        1. Start new market data cache cycle
        2. Notify strategies of cycle start
        3. Execute each strategy's evaluation logic
        4. Notify strategies of cycle end

        Returns:
            bool: True if cycle completed successfully
        """
        if self.state not in (OrchestratorState.INITIALIZED, OrchestratorState.RUNNING):
            self.logger.warning(f"Cannot run cycle: orchestrator state is {self.state.value}")
            return False

        self.state = OrchestratorState.RUNNING
        self._cycle_count += 1
        self._last_cycle_time = datetime.now()
        cycle_errors = []

        dry_run_tag = " [DRY-RUN]" if self._dry_run else ""
        self.logger.info(f"Starting orchestrator cycle {self._cycle_count}{dry_run_tag}")

        try:
            # Start new cache cycle for market data
            if self._market_data is not None:
                self._market_data.start_new_cycle()

            # Notify strategies of cycle start
            for strategy in self.strategies:
                try:
                    strategy.on_cycle_start()
                except Exception as e:
                    self.logger.error(f"Error in {strategy.get_name()}.on_cycle_start(): {e}")
                    cycle_errors.append({"strategy": strategy.get_name(), "phase": "on_cycle_start", "error": str(e)})

            # Execute strategies based on mode
            if self._execution_mode == ExecutionMode.PARALLEL:
                execution_errors = self._run_parallel()
            else:
                execution_errors = self._run_sequential()

            cycle_errors.extend(execution_errors)

            # Notify strategies of cycle end
            for strategy in self.strategies:
                try:
                    strategy.on_cycle_end()
                except Exception as e:
                    self.logger.error(f"Error in {strategy.get_name()}.on_cycle_end(): {e}")
                    cycle_errors.append({"strategy": strategy.get_name(), "phase": "on_cycle_end", "error": str(e)})

            # Track errors
            self._cycle_errors = cycle_errors

            success = len(cycle_errors) == 0
            if success:
                self.logger.info(f"Orchestrator cycle {self._cycle_count} completed")
            else:
                self.logger.warning(f"Orchestrator cycle {self._cycle_count} completed with {len(cycle_errors)} error(s)")

            return success

        except Exception as e:
            self.logger.error(f"Critical error in cycle {self._cycle_count}: {e}")
            self.state = OrchestratorState.ERROR
            return False

    def _run_sequential(self) -> list[dict[str, Any]]:
        """
        Run strategies sequentially.

        Returns:
            List of error dictionaries
        """
        errors = []

        for strategy in self.strategies:
            try:
                self._execute_strategy(strategy)
            except Exception as e:
                self.logger.error(f"Error executing {strategy.get_name()}: {e}")
                errors.append({"strategy": strategy.get_name(), "phase": "execute", "error": str(e)})

        return errors

    def _run_parallel(self) -> list[dict[str, Any]]:
        """
        Run strategies in parallel using thread pool.

        Returns:
            List of error dictionaries
        """
        errors = []

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Submit all strategies for execution
            future_to_strategy = {executor.submit(self._execute_strategy, strategy): strategy for strategy in self.strategies}

            # Collect results
            for future in as_completed(future_to_strategy):
                strategy = future_to_strategy[future]
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Error in parallel execution of {strategy.get_name()}: {e}")
                    errors.append({"strategy": strategy.get_name(), "phase": "execute_parallel", "error": str(e)})

        return errors

    def _display_play_cards(self, strategy: BaseStrategy) -> None:
        """
        Display play cards with market data for all play types.

        Shows formatted cards for new, open, pending-opening, and pending-closing plays
        with current stock price and option premium data.

        Args:
            strategy: Strategy instance
        """
        from goldflipper.json_parser import load_play
        from goldflipper.utils.display import TerminalDisplay as display

        self.logger.debug(f"_display_play_cards called for strategy: {strategy.get_name()}")
        display.info(f"Loading play cards for {strategy.get_name()}...")

        # Map folder names to PlayStatus enum values
        play_type_map = {
            "new": PlayStatus.NEW,
            "open": PlayStatus.OPEN,
            "pending-opening": PlayStatus.PENDING_OPENING,
            "pending-closing": PlayStatus.PENDING_CLOSING,
        }

        for play_type, status_enum in play_type_map.items():
            try:
                play_dir = strategy.get_plays_dir(status_enum)
            except Exception as e:
                self.logger.debug(f"Could not get plays dir for {play_type}: {e}")
                continue

            if not os.path.exists(play_dir):
                self.logger.debug(f"Play dir does not exist: {play_dir}")
                continue

            try:
                play_files = [f for f in os.listdir(play_dir) if f.endswith(".json")]
                if play_files:
                    display.info(f"  Found {len(play_files)} {play_type} play(s)")

                for filename in play_files:
                    filepath = os.path.join(play_dir, filename)
                    play = load_play(filepath)

                    if not play:
                        continue

                    try:
                        market_data = self._market_data
                        if market_data is None:
                            self.logger.error("MarketDataManager is not initialized")
                            continue

                        # Get current stock price
                        current_price = market_data.get_stock_price(play["symbol"])
                        if current_price is None or current_price <= 0:
                            self.logger.error(f"Could not get valid share price for {play['symbol']}")
                            continue

                        # Get current option data
                        option_symbol = play.get("option_contract_symbol")
                        if not option_symbol:
                            continue

                        option_data = market_data.get_option_quote(option_symbol)
                        if option_data is None:
                            self.logger.error(f"Could not get option data for {option_symbol}")
                            continue

                        # Log detailed data
                        self.logger.info(
                            f"Play data for {play['symbol']}: Type={play_type}, "
                            f"Strike=${play.get('strike_price')}, Exp={play.get('expiration_date')}, "
                            f"Stock=${current_price:.2f}, Bid=${option_data['bid']:.2f}, "
                            f"Ask=${option_data['ask']:.2f}"
                        )

                        # Display formatted play card
                        play_name = play.get("play_name", "N/A")
                        border = "+" + "-" * 60 + "+"
                        display.status(border, show_timestamp=False)
                        display.status(f"|{play_name:^60}|", show_timestamp=False)
                        display.status(border, show_timestamp=False)
                        display.status(
                            f"Play: {play['symbol']} {play.get('trade_type', 'N/A')} "
                            f"{play.get('strike_price', 'N/A')} Strike {play.get('expiration_date', 'N/A')} Expiration"
                        )

                        # Map play types to display methods
                        status_display = {
                            "new": display.info,
                            "pending-opening": display.info,
                            "open": display.success,
                            "pending-closing": display.warning,
                        }
                        display_method = status_display.get(play_type.lower(), display.status)

                        play_status = play.get("status", {}).get("play_status")
                        play_expiration_date = play.get("play_expiration_date")

                        status_msg = f"Status: [{play_type}]"
                        if play_expiration_date and play_status in ("TEMP", "NEW"):
                            status_msg = f"Status: [{play_type}], Play expires: {play_expiration_date}"

                        display_method(status_msg, show_timestamp=False)
                        display.price(f"Stock price: ${current_price:.2f}")
                        display.price(
                            f"Option premium: Bid ${option_data['bid']:.2f} "
                            f"Ask ${option_data['ask']:.2f} Last ${option_data.get('premium', option_data.get('last', 0)):.2f}"
                        )
                        display.status(border, show_timestamp=False)

                    except Exception as e:
                        self.logger.error(f"Error displaying play card for {filepath}: {e}")

            except Exception as e:
                self.logger.error(f"Error listing plays in {play_dir}: {e}")

    def _execute_strategy(self, strategy: BaseStrategy) -> None:
        """
        Execute a single strategy's full evaluation cycle.

        This method:
        1. Displays play cards for all play types
        2. Loads plays for this strategy
        3. Handles expired plays
        4. Manages pending plays (pending-opening, pending-closing)
        5. Evaluates new plays for entry conditions and opens positions
        6. Evaluates open plays for exit conditions and closes positions

        Args:
            strategy: Strategy instance to execute
        """
        name = strategy.get_name()
        self.logger.debug(f"Executing strategy: {name}")

        try:
            # Display play cards with market data for all play types
            if self._market_data is not None:
                self._display_play_cards(strategy)

            # Get play directories
            new_dir = strategy.get_plays_dir(PlayStatus.NEW)
            open_dir = strategy.get_plays_dir(PlayStatus.OPEN)

            # Handle expired plays first
            self._handle_expired_plays(strategy, new_dir)

            # Manage pending plays (check order status, update play status)
            self._manage_pending_plays(strategy)

            # Load plays from directories
            new_plays = self._load_plays_from_dir(new_dir, strategy)
            open_plays = self._load_plays_from_dir(open_dir, strategy)

            self.logger.debug(f"[{name}] Found {len(new_plays)} new plays, {len(open_plays)} open plays")

            # Evaluate and execute new plays for entry
            if new_plays:
                plays_to_open = strategy.evaluate_new_plays(new_plays)
                self.logger.info(f"[{name}] {len(plays_to_open)} plays met entry conditions")

                # Execute opening for each play
                for play in plays_to_open:
                    play_file = play.get("_play_file", "")
                    symbol = play.get("symbol", "unknown")
                    option_symbol = play.get("option_symbol", "")
                    contracts = play.get("contracts", 1)
                    entry_price = play.get("entry_point", {}).get("target_price", "N/A")

                    # Dry-run mode: log but don't execute
                    if self._dry_run:
                        self.logger.info(
                            f"[{name}] [DRY-RUN] WOULD OPEN: {symbol} | Option: {option_symbol} | Contracts: {contracts} | Entry: ${entry_price}"
                        )
                        continue

                    try:
                        self.logger.info(f"[{name}] Opening position for {symbol}")
                        open_position_fn = getattr(strategy, "open_position", None)
                        if callable(open_position_fn):
                            success = open_position_fn(play, play_file)
                            if success:
                                self.logger.info(f"[{name}] Position opened for {symbol}")
                            else:
                                self.logger.warning(f"[{name}] Failed to open position for {symbol}")
                        else:
                            # Fallback to core.py
                            self._open_position_via_core(play, play_file)
                    except Exception as e:
                        self.logger.error(f"[{name}] Error opening position for {symbol}: {e}")

            # Evaluate and execute open plays for exit
            if open_plays:
                plays_to_close = strategy.evaluate_open_plays(open_plays)
                self.logger.info(f"[{name}] {len(plays_to_close)} plays met exit conditions")

                # Execute closing for each play
                for play, close_conditions in plays_to_close:
                    play_file = play.get("_play_file", "")
                    symbol = play.get("symbol", "unknown")
                    option_symbol = play.get("option_symbol", "")
                    contracts = play.get("contracts", 1)
                    close_type = "TP" if close_conditions.get("is_profit") else "SL"
                    close_reason = close_conditions.get("reason", "unknown")

                    # Dry-run mode: log but don't execute
                    if self._dry_run:
                        self.logger.info(
                            f"[{name}] [DRY-RUN] WOULD CLOSE ({close_type}): {symbol} | "
                            f"Option: {option_symbol} | Contracts: {contracts} | "
                            f"Reason: {close_reason}"
                        )
                        continue

                    try:
                        self.logger.info(f"[{name}] Closing position for {symbol} ({close_type})")
                        close_position_fn = getattr(strategy, "close_position", None)
                        if callable(close_position_fn):
                            success = close_position_fn(play, close_conditions, play_file)
                            if success:
                                self.logger.info(f"[{name}] Position closed for {symbol}")
                            else:
                                self.logger.warning(f"[{name}] Failed to close position for {symbol}")
                        else:
                            # Fallback to core.py
                            self._close_position_via_core(play, close_conditions, play_file)
                    except Exception as e:
                        self.logger.error(f"[{name}] Error closing position for {symbol}: {e}")

            self.logger.debug(f"Strategy {name} execution complete")

        except Exception as e:
            self.logger.error(f"Error executing strategy {name}: {e}")
            raise

    def _handle_expired_plays(self, strategy: BaseStrategy, new_dir: str) -> None:
        """
        Handle expired plays in the new folder by moving them to expired.

        Checks both the static play_expiration_date and the dynamic GTD
        effective_date (if enabled). The earliest of the two is used.

        Args:
            strategy: Strategy instance
            new_dir: Path to new plays directory
        """
        from datetime import datetime

        from goldflipper.json_parser import load_play
        from goldflipper.strategy.shared import move_play_to_expired

        if not os.path.exists(new_dir):
            return

        current_date = datetime.now().date()

        try:
            for filename in os.listdir(new_dir):
                if not filename.endswith(".json"):
                    continue

                filepath = os.path.join(new_dir, filename)
                play = load_play(filepath)

                if not play:
                    continue

                # Determine effective expiration: earliest of static and dynamic GTD
                effective_exp_date = None

                # Static play_expiration_date
                if "play_expiration_date" in play:
                    try:
                        effective_exp_date = datetime.strptime(play["play_expiration_date"], "%m/%d/%Y").date()
                    except ValueError as e:
                        self.logger.warning(f"Invalid expiration date format in {filepath}: {e}")

                # Dynamic GTD effective_date (if enabled and set)
                gtd_config = play.get("dynamic_gtd", {})
                if gtd_config.get("enabled", False) and gtd_config.get("effective_date"):
                    try:
                        gtd_date = datetime.strptime(gtd_config["effective_date"], "%m/%d/%Y").date()
                        # Use the earlier of static and dynamic dates
                        if effective_exp_date is None or gtd_date < effective_exp_date:
                            effective_exp_date = gtd_date
                    except ValueError as e:
                        self.logger.warning(f"Invalid dynamic GTD effective_date in {filepath}: {e}")

                if effective_exp_date is not None and effective_exp_date < current_date:
                    move_play_to_expired(filepath)
                    self.logger.info(f"Moved expired play to expired folder: {filepath}")
        except Exception as e:
            self.logger.error(f"Error handling expired plays: {e}")

    def _manage_pending_plays(self, strategy: BaseStrategy) -> None:
        """
        Manage plays in pending-opening and pending-closing states.

        Checks order status and updates play status accordingly.

        Args:
            strategy: Strategy instance
        """
        # For now, delegate to core.py's manage_pending_plays
        # This can be refactored to strategy-specific logic later
        try:
            from goldflipper.core import manage_pending_plays

            # Use exe-aware path for plays directory
            plays_dir = str(get_plays_dir())
            manage_pending_plays(plays_dir)

        except Exception as e:
            self.logger.error(f"Error managing pending plays: {e}")

    def _open_position_via_core(self, play: dict[str, Any], play_file: str) -> bool:
        """
        Fallback: Open position using core.py's open_position function.

        Args:
            play: Play data dictionary
            play_file: Path to play file

        Returns:
            True if position opened successfully
        """
        try:
            from goldflipper.core import open_position

            return open_position(play, play_file)
        except Exception as e:
            self.logger.error(f"Error in core.open_position: {e}")
            return False

    def _close_position_via_core(self, play: dict[str, Any], close_conditions: dict[str, Any], play_file: str) -> bool:
        """
        Fallback: Close position using core.py's close_position function.

        Args:
            play: Play data dictionary
            close_conditions: Exit conditions dict
            play_file: Path to play file

        Returns:
            True if position closed successfully
        """
        try:
            from goldflipper.core import close_position

            return close_position(play, close_conditions, play_file)
        except Exception as e:
            self.logger.error(f"Error in core.close_position: {e}")
            return False

    def _load_plays_from_dir(self, directory: str, strategy: BaseStrategy) -> list[dict[str, Any]]:
        """
        Load play files from a directory.

        Args:
            directory: Path to play directory
            strategy: Strategy instance for validation

        Returns:
            List of valid play dictionaries
        """
        plays = []

        if not os.path.exists(directory):
            return plays

        try:
            # Import here to avoid circular imports
            from goldflipper.json_parser import load_play

            for filename in os.listdir(directory):
                if not filename.endswith(".json"):
                    continue

                filepath = os.path.join(directory, filename)
                play = load_play(filepath)

                if play is not None and strategy.validate_play(play):
                    # Add file path to play for later use
                    play["_play_file"] = filepath
                    plays.append(play)

        except Exception as e:
            self.logger.error(f"Error loading plays from {directory}: {e}")

        return plays

    # =========================================================================
    # Continuous Operation
    # =========================================================================

    def run_continuous(self, interval_seconds: int = 30, market_hours_check: Callable[[], bool] | None = None, max_cycles: int | None = None) -> None:
        """
        Run continuous monitoring loop.

        This method runs the orchestrator in a loop, executing cycles at the
        specified interval. It can optionally check market hours before each cycle.

        Args:
            interval_seconds: Seconds between cycles
            market_hours_check: Optional callable that returns True if market is open
            max_cycles: Optional maximum number of cycles to run (for testing)

        Note:
            This is a blocking call. Use run_cycle() for single execution.
        """
        self.logger.info(f"Starting continuous monitoring (interval={interval_seconds}s)")

        cycles_run = 0

        try:
            while True:
                # Check max cycles limit
                if max_cycles is not None and cycles_run >= max_cycles:
                    self.logger.info(f"Reached max cycles ({max_cycles}), stopping")
                    break

                # Check market hours if callback provided
                if market_hours_check is not None:
                    if not market_hours_check():
                        self.logger.debug("Market closed, skipping cycle")
                        time.sleep(interval_seconds)
                        continue

                # Run one cycle
                self.run_cycle()
                cycles_run += 1

                # Wait for next cycle
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        finally:
            self.stop()

    # =========================================================================
    # Control Methods
    # =========================================================================

    def stop(self) -> None:
        """Stop the orchestrator."""
        self.logger.info("Stopping orchestrator...")
        self.state = OrchestratorState.STOPPED

    def reset(self) -> None:
        """Reset the orchestrator to uninitialized state."""
        self.strategies = []
        self.state = OrchestratorState.UNINITIALIZED
        self._cycle_count = 0
        self._cycle_errors = []
        self.logger.info("Orchestrator reset")

    # =========================================================================
    # Status and Diagnostics
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """
        Get orchestrator status information.

        Returns:
            Dict with status details
        """
        return {
            "state": self.state.value,
            "enabled": self._enabled,
            "dry_run": self._dry_run,
            "execution_mode": self._execution_mode.value,
            "strategy_count": len(self.strategies),
            "strategies": [
                {"name": s.get_name(), "enabled": s.is_enabled(), "priority": s.get_priority(), "config_section": s.get_config_section()}
                for s in self.strategies
            ],
            "cycle_count": self._cycle_count,
            "last_cycle_time": (self._last_cycle_time.isoformat() if self._last_cycle_time else None),
            "last_cycle_errors": self._cycle_errors,
        }

    def get_strategy(self, name: str) -> BaseStrategy | None:
        """
        Get a loaded strategy by name.

        Args:
            name: Strategy name

        Returns:
            Strategy instance or None
        """
        for strategy in self.strategies:
            if strategy.get_name() == name:
                return strategy
        return None

    def __repr__(self) -> str:
        """String representation."""
        return f"<StrategyOrchestrator state={self.state.value} strategies={len(self.strategies)} mode={self._execution_mode.value}>"

"""
Option Swings Strategy Runner

This module implements the manual option swings trading strategy as a BaseStrategy
subclass. It extracts the current option_swings logic from core.py into a discrete
strategy runner that can be managed by the StrategyOrchestrator.

This is a P0 (highest priority) strategy - it represents the existing/default
trading strategy that has been running in core.py.

Usage:
    The strategy is automatically discovered and registered when its module
    is imported by the StrategyRegistry.discover() method.
    
    # Manual instantiation (for testing)
    from goldflipper.strategy.runners.option_swings import OptionSwingsStrategy
    
    strategy = OptionSwingsStrategy(config, market_data, client)
    if strategy.is_enabled():
        plays_to_open = strategy.evaluate_new_plays(new_plays)
        plays_to_close = strategy.evaluate_open_plays(open_plays)
"""

import os
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from goldflipper.strategy.base import BaseStrategy, PlayStatus, OrderAction, PositionSide
from goldflipper.strategy.registry import register_strategy

# Import shared utilities (Phase 2)
from goldflipper.strategy.shared import (
    # Evaluation functions
    evaluate_opening_strategy,
    evaluate_closing_strategy,
    calculate_and_store_price_levels,
    calculate_and_store_premium_levels,
    # Play management
    PlayManager,
    save_play,
    save_play_improved,
    move_play_to_new,
    move_play_to_pending_opening,
    move_play_to_open,
    move_play_to_pending_closing,
    move_play_to_closed,
    move_play_to_expired,
    move_play_to_temp,
    # Order execution
    OrderExecutor,
    get_option_contract,
)


@register_strategy('option_swings')
class OptionSwingsStrategy(BaseStrategy):
    """
    Manual Option Swings Trading Strategy.
    
    Trade Direction: BUY_TO_OPEN → SELL_TO_CLOSE (long premium)
    
    This strategy BUYS options (calls or puts) and profits when the premium
    increases. It uses the base class default order actions (BTO/STC).
    
    This strategy handles:
    - Evaluating new plays for entry conditions (stock price vs entry point)
    - Opening positions via limit or market orders
    - Monitoring open positions for TP/SL conditions
    - Closing positions when exit conditions are met
    - Managing play lifecycle (new → pending-opening → open → pending-closing → closed)
    
    The strategy supports multiple TP/SL types:
    - STOCK_PRICE: Absolute stock price targets
    - STOCK_PRICE_PCT: Stock price percentage movement
    - PREMIUM_PCT: Option premium percentage change
    
    And multiple order types:
    - market
    - limit at bid
    - limit at ask
    - limit at mid
    - limit at last
    
    Configuration section: options_swings (in settings.yaml)
    
    Attributes:
        _order_executor (OrderExecutor): Handles order placement operations
        _play_manager (PlayManager): Handles play file operations (optional)
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        market_data: Any,
        brokerage_client: Any
    ):
        """
        Initialize the Option Swings strategy.
        
        Args:
            config: Full application configuration dictionary
            market_data: MarketDataManager instance
            brokerage_client: Alpaca TradingClient instance
        """
        super().__init__(config, market_data, brokerage_client)
        
        # Initialize order executor for this strategy
        self._order_executor = OrderExecutor(
            client=brokerage_client,
            market_data=market_data
        )
        
        # Cache for strategy-specific config
        self._strategy_config: Optional[Dict[str, Any]] = None
        
        self.logger.info(f"OptionSwingsStrategy initialized (enabled={self.is_enabled()})")
    
    # =========================================================================
    # Abstract Method Implementations
    # =========================================================================
    
    def get_name(self) -> str:
        """Return unique strategy identifier."""
        return "option_swings"
    
    def get_config_section(self) -> str:
        """
        Return the configuration section name.
        
        Note: Config uses 'options_swings' (with 's') for historical reasons.
        """
        return "options_swings"
    
    def get_plays_base_dir(self) -> str:
        """
        Return base directory for play files.
        
        Currently uses shared 'plays' directory for backward compatibility.
        In future, could use 'plays/option_swings' for isolation.
        """
        return "plays"
    
    def evaluate_new_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate plays in NEW status for entry conditions.
        
        For each play, checks if:
        1. Current stock price meets entry conditions
        2. Play hasn't expired
        3. Required fields are present
        
        Args:
            plays: List of play dictionaries from 'new' folder
        
        Returns:
            List of plays that should be opened (entry conditions met)
        """
        plays_to_open = []
        
        for play in plays:
            play_file = play.get('_play_file', '')
            symbol = play.get('symbol', '')
            
            try:
                # Validate required fields
                if not self.validate_play(play):
                    self.logger.warning(f"Play validation failed: {play_file}")
                    continue
                
                # Check for expiration
                if self._is_play_expired(play):
                    self.logger.info(f"Play expired, skipping: {symbol}")
                    continue
                
                # Evaluate entry conditions using shared module
                # The shared function uses dependency injection for market data
                should_enter = evaluate_opening_strategy(
                    symbol=symbol,
                    play=play,
                    get_stock_price_fn=self._get_stock_price
                )
                
                if should_enter:
                    self.log_trade_action('ENTRY_SIGNAL', play, {
                        'entry_point': play.get('entry_point', {}).get('stock_price'),
                        'order_type': play.get('entry_point', {}).get('order_type')
                    })
                    plays_to_open.append(play)
                    
            except Exception as e:
                self.logger.error(f"Error evaluating new play {symbol}: {e}")
                continue
        
        return plays_to_open
    
    def evaluate_open_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Evaluate open positions for exit conditions (TP/SL).
        
        For each play, checks:
        1. Take profit conditions (stock price, premium %, etc.)
        2. Stop loss conditions (primary and contingency)
        3. Trailing stop updates
        
        Args:
            plays: List of play dictionaries from 'open' folder
        
        Returns:
            List of tuples: (play, close_conditions) for plays that should close
            
            close_conditions dict contains:
            - should_close: bool
            - is_profit: bool (take profit triggered)
            - is_primary_loss: bool (stop loss triggered)
            - is_contingency_loss: bool (backup SL triggered)
            - sl_type: str (STOP, LIMIT, CONTINGENCY)
        """
        plays_to_close = []
        
        for play in plays:
            play_file = play.get('_play_file', '')
            symbol = play.get('symbol', '')
            
            try:
                # Evaluate exit conditions using shared module
                close_conditions = evaluate_closing_strategy(
                    symbol=symbol,
                    play=play,
                    play_file=play_file,
                    get_stock_price_fn=self._get_stock_price,
                    get_option_data_fn=self._get_option_data,
                    save_play_fn=save_play_improved
                )
                
                if close_conditions.get('should_close', False):
                    # Determine close type for logging
                    close_type = 'TP' if close_conditions.get('is_profit') else 'SL'
                    if close_conditions.get('is_contingency_loss'):
                        close_type = 'SL(CONTINGENCY)'
                    
                    self.log_trade_action(f'EXIT_SIGNAL_{close_type}', play, {
                        'is_profit': close_conditions.get('is_profit'),
                        'sl_type': close_conditions.get('sl_type')
                    })
                    
                    plays_to_close.append((play, close_conditions))
                    
            except Exception as e:
                self.logger.error(f"Error evaluating open play {symbol}: {e}")
                continue
        
        return plays_to_close
    
    # =========================================================================
    # Optional Override Methods
    # =========================================================================
    
    def get_priority(self) -> int:
        """
        Return execution priority.
        
        Option swings is the primary strategy, so it gets high priority (10).
        """
        return 10
    
    def on_cycle_start(self) -> None:
        """Hook called at start of monitoring cycle."""
        super().on_cycle_start()
        # Could refresh any cached data here
        self.logger.debug("Option swings cycle starting")
    
    def on_cycle_end(self) -> None:
        """Hook called at end of monitoring cycle."""
        super().on_cycle_end()
        self.logger.debug("Option swings cycle complete")
    
    def validate_play(self, play: Dict[str, Any]) -> bool:
        """
        Validate play data structure for option swings strategy.
        
        Extends base validation with strategy-specific requirements.
        """
        # Base validation
        if not super().validate_play(play):
            return False
        
        # Option swings specific required fields
        required_fields = [
            'strike_price',
            'expiration_date',
            'contracts',
            'entry_point',
            'take_profit',
            'stop_loss'
        ]
        
        for field in required_fields:
            if field not in play:
                self.logger.warning(f"Play missing required field: {field}")
                return False
        
        # Validate entry_point structure
        entry_point = play.get('entry_point', {})
        if 'order_type' not in entry_point:
            self.logger.warning("Play entry_point missing order_type")
            return False
        
        # Validate order type is valid
        valid_order_types = [
            'market', 
            'limit at bid', 
            'limit at ask', 
            'limit at mid', 
            'limit at last'
        ]
        if entry_point.get('order_type') not in valid_order_types:
            self.logger.warning(f"Invalid entry order type: {entry_point.get('order_type')}")
            return False
        
        return True
    
    # =========================================================================
    # Strategy-Specific Methods
    # =========================================================================
    
    def _get_stock_price(self, symbol: str) -> Optional[float]:
        """
        Get current stock price using market data manager.
        
        Args:
            symbol: Stock ticker symbol
        
        Returns:
            Current stock price or None if unavailable
        """
        try:
            price = self.market_data.get_stock_price(symbol)
            if price is not None:
                # Handle pandas Series if needed
                if hasattr(price, 'item'):
                    price = float(price.item())
                return float(price)
            return None
        except Exception as e:
            self.logger.error(f"Error getting stock price for {symbol}: {e}")
            return None
    
    def _get_option_data(self, option_symbol: str) -> Optional[Dict[str, float]]:
        """
        Get current option quote data.
        
        Args:
            option_symbol: Option contract symbol (e.g., 'AAPL241220C00200000')
        
        Returns:
            Dict with bid, ask, last, premium, delta, theta, etc. or None
        """
        try:
            option_data = self.market_data.get_option_quote(option_symbol)
            return option_data
        except Exception as e:
            self.logger.error(f"Error getting option data for {option_symbol}: {e}")
            return None
    
    def _is_play_expired(self, play: Dict[str, Any]) -> bool:
        """
        Check if play has passed its expiration date.
        
        Args:
            play: Play dictionary
        
        Returns:
            True if play is expired
        """
        play_expiration = play.get('play_expiration_date')
        if not play_expiration:
            return False
        
        try:
            exp_date = datetime.strptime(play_expiration, "%m/%d/%Y").date()
            return exp_date < datetime.now().date()
        except ValueError:
            self.logger.warning(f"Invalid play_expiration_date format: {play_expiration}")
            return False
    
    def get_strategy_config(self) -> Dict[str, Any]:
        """
        Get cached strategy configuration.
        
        Returns:
            Dict containing options_swings config section
        """
        if self._strategy_config is None:
            config_section = self.config.get(self.get_config_section())
            self._strategy_config = config_section if config_section is not None else {}
        return self._strategy_config if self._strategy_config is not None else {}
    
    # =========================================================================
    # Order Execution Methods (Delegate to core.py for now)
    # =========================================================================
    # 
    # Note: These methods are placeholders. The actual order execution still
    # happens in core.py via execute_trade(), open_position(), close_position().
    # 
    # In a future phase, we can move order execution into the strategy runner
    # using self._order_executor, but for now we maintain backward compatibility
    # by letting the orchestrator call back into core.py.
    #
    # The evaluate_* methods above provide the decision logic that determines
    # WHICH plays should be opened/closed. The actual execution is separate.
    # =========================================================================
    
    def open_position(self, play: Dict[str, Any], play_file: str) -> bool:
        """
        Open a position for the given play.
        
        Note: Currently delegates to core.py's open_position() for compatibility.
        This is a hook for future migration of order execution into the strategy.
        
        Args:
            play: Play data dictionary
            play_file: Path to play file
        
        Returns:
            True if position opened successfully
        """
        # Import here to avoid circular dependency
        from goldflipper.core import open_position as core_open_position
        return core_open_position(play, play_file)
    
    def close_position(
        self, 
        play: Dict[str, Any], 
        close_conditions: Dict[str, Any],
        play_file: str
    ) -> bool:
        """
        Close an open position.
        
        Note: Currently delegates to core.py's close_position() for compatibility.
        This is a hook for future migration of order execution into the strategy.
        
        Args:
            play: Play data dictionary
            close_conditions: Exit conditions dict from evaluate_open_plays
            play_file: Path to play file
        
        Returns:
            True if position closed successfully
        """
        # Import here to avoid circular dependency
        from goldflipper.core import close_position as core_close_position
        return core_close_position(play, close_conditions, play_file)


# Export the strategy class for direct imports
__all__ = ['OptionSwingsStrategy']

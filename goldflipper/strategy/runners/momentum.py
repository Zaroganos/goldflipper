"""
Momentum Strategy Runner

This module implements a general momentum-based trading strategy for
long premium positions (BTO → STC). The specific momentum TYPE is
determined by the playbook configuration.

Trade Direction: BUY_TO_OPEN → SELL_TO_CLOSE (long premium)

Supported Momentum Types (via playbook momentum_config.momentum_type):
- "gap" - Pre-market gap trading (gap continuation or fade)
- "squeeze" - TTM Squeeze breakout trading (FUTURE)
- "ema_cross" - EMA crossover momentum (FUTURE)
- "manual" - No auto-entry, manual plays only (default)

Risk Profile:
- Max profit: Unlimited (long options)
- Max loss: Premium paid

Key Features:
- Playbook-driven momentum type selection
- Gap trading: with_gap or fade_gap direction
- Confirmation period waiting (optional)
- Time-based exits (same-day, max hold days)
- DTE filtering for option selection
- Premium-based TP/SL with trailing support

Configuration section: momentum (in settings.yaml)
Playbooks: strategy/playbooks/momentum/
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional

from goldflipper.strategy.base import BaseStrategy, PlayStatus, OrderAction, PositionSide
from goldflipper.strategy.registry import register_strategy

# Import shared utilities
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
    # Order execution
    OrderExecutor,
    get_option_contract,
)


@register_strategy('momentum')
class MomentumStrategy(BaseStrategy):
    """
    Momentum-Based Trading Strategy.
    
    Trade Direction: BUY_TO_OPEN → SELL_TO_CLOSE (long premium)
    
    This strategy BUYS options based on momentum signals. The specific
    momentum type is determined by the playbook's momentum_config.momentum_type:
    
    Momentum Types:
    - "gap": Trade based on pre-market gaps (with_gap or fade_gap)
    - "squeeze": TTM Squeeze breakout signals (FUTURE)
    - "ema_cross": EMA crossover signals (FUTURE)
    - "manual": No auto-entry evaluation, manual plays only
    
    Entry Conditions (vary by momentum_type):
    - Stock price meets type-specific criteria
    - Optional: Wait for confirmation period
    - Stock price near entry target
    - DTE within acceptable range
    
    Exit Conditions:
    - Premium-based TP/SL (like option_swings)
    - Time-based: same-day exit or max hold days
    - Trailing stop support
    
    Configuration section: momentum
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        market_data: Any,
        brokerage_client: Any
    ):
        """Initialize the Momentum strategy."""
        super().__init__(config, market_data, brokerage_client)
        
        # Initialize order executor
        self._order_executor = OrderExecutor(
            client=brokerage_client,
            market_data=market_data
        )
        
        # Cache for strategy-specific config
        self._strategy_config: Optional[Dict[str, Any]] = None
        
        self.logger.info(f"MomentumStrategy initialized (enabled={self.is_enabled()})")
    
    # =========================================================================
    # Abstract Method Implementations
    # =========================================================================
    
    def get_name(self) -> str:
        """Return unique strategy identifier."""
        return "momentum"
    
    def get_config_section(self) -> str:
        """Return the configuration section name."""
        return "momentum"
    
    def get_plays_base_dir(self) -> str:
        """Return base directory for play files."""
        return "plays"
    
    def get_priority(self) -> int:
        """Return execution priority (lower = higher priority)."""
        return 50  # Medium-high priority (gap trades need quick execution)
    
    # =========================================================================
    # Entry Evaluation
    # =========================================================================
    
    def evaluate_new_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate plays in NEW status for entry conditions.
        
        Entry evaluation is dispatched based on the playbook's momentum_type:
        - "gap": Validates gap_info, gap size, direction, confirmation
        - "squeeze": Check TTM Squeeze signals (FUTURE)
        - "ema_cross": Check EMA crossover signals (FUTURE)
        - "manual": Skip auto-entry, require manual intervention
        
        Common checks for all types:
        1. Play hasn't expired
        2. DTE is acceptable
        3. Stock price near entry target
        
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
                
                # Check for play expiration
                if self._is_play_expired(play):
                    self.logger.info(f"Play expired, skipping: {symbol}")
                    continue
                
                # Check DTE is acceptable
                if not self._is_dte_acceptable(play):
                    self.logger.debug(f"DTE outside range for: {symbol}")
                    continue
                
                # Get momentum type from playbook (default: "manual")
                momentum_type = self.get_playbook_setting(
                    play, 'momentum_config.momentum_type', 'manual'
                )
                
                # Dispatch to type-specific evaluation
                should_enter, entry_details = self._evaluate_by_momentum_type(
                    play, momentum_type
                )
                
                if should_enter:
                    self.log_trade_action('ENTRY_SIGNAL', play, {
                        'action': 'BTO',
                        'momentum_type': momentum_type,
                        'entry_point': play.get('entry_point', {}).get('stock_price'),
                        'order_type': play.get('entry_point', {}).get('order_type'),
                        **entry_details
                    })
                    plays_to_open.append(play)
                    
            except Exception as e:
                self.logger.error(f"Error evaluating new play {symbol}: {e}")
                continue
        
        return plays_to_open
    
    def _evaluate_by_momentum_type(
        self, 
        play: Dict[str, Any], 
        momentum_type: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Dispatch entry evaluation to the appropriate momentum type handler.
        
        Args:
            play: Play dictionary
            momentum_type: Type from playbook (gap, squeeze, ema_cross, manual)
            
        Returns:
            Tuple of (should_enter: bool, entry_details: dict)
        """
        if momentum_type == "gap":
            return self._evaluate_gap_entry(play)
        elif momentum_type == "squeeze":
            return self._evaluate_squeeze_entry(play)
        elif momentum_type == "ema_cross":
            return self._evaluate_ema_cross_entry(play)
        elif momentum_type == "manual":
            # Manual plays - just check stock price entry conditions
            should_enter = self._evaluate_entry_conditions(play)
            return should_enter, {}
        else:
            self.logger.warning(f"Unknown momentum_type: {momentum_type}, using manual")
            should_enter = self._evaluate_entry_conditions(play)
            return should_enter, {}
    
    # =========================================================================
    # Gap Momentum Type Evaluation
    # =========================================================================
    
    def _evaluate_gap_entry(
        self, 
        play: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate entry conditions for gap momentum type.
        
        Checks:
        1. Gap information is valid (gap_info section populated)
        2. Gap size meets min/max thresholds from playbook
        3. Gap type matches playbook filter (up/down/any)
        4. Confirmation period satisfied (if required)
        5. Stock price near entry target
        
        Args:
            play: Play dictionary with gap_info section
            
        Returns:
            Tuple of (should_enter, details_dict)
        """
        symbol = play.get('symbol', '')
        gap_info = play.get('gap_info', {})
        
        # Validate gap information
        if not self._validate_gap_info(play, gap_info):
            self.logger.debug(f"Gap info validation failed for: {symbol}")
            return False, {}
        
        # Check confirmation period (if required)
        if not self._check_confirmation_period(play, gap_info):
            self.logger.debug(f"Confirmation period not met for: {symbol}")
            return False, {}
        
        # Evaluate stock price entry conditions
        should_enter = self._evaluate_entry_conditions(play)
        
        if should_enter:
            details = {
                'gap_type': gap_info.get('gap_type', 'unknown'),
                'gap_pct': gap_info.get('gap_pct', 0),
                'trade_direction': gap_info.get('trade_direction', 'with_gap')
            }
            return True, details
        
        return False, {}
    
    # =========================================================================
    # Squeeze Momentum Type Evaluation (FUTURE)
    # =========================================================================
    
    def _evaluate_squeeze_entry(
        self, 
        play: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate entry conditions for TTM Squeeze momentum type.
        
        FUTURE IMPLEMENTATION:
        - Check if squeeze has fired (Bollinger inside Keltner)
        - Check momentum histogram direction/color
        - Confirm with volume or other indicators
        
        Args:
            play: Play dictionary
            
        Returns:
            Tuple of (should_enter, details_dict)
        """
        self.logger.warning("Squeeze momentum type not yet implemented, using manual entry")
        # Fall back to manual entry evaluation for now
        should_enter = self._evaluate_entry_conditions(play)
        return should_enter, {'squeeze_status': 'not_implemented'}
    
    # =========================================================================
    # EMA Cross Momentum Type Evaluation (FUTURE)
    # =========================================================================
    
    def _evaluate_ema_cross_entry(
        self, 
        play: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate entry conditions for EMA crossover momentum type.
        
        FUTURE IMPLEMENTATION:
        - Check for fast EMA crossing above/below slow EMA
        - Confirm trend direction
        - Check for pullback to EMA support/resistance
        
        Args:
            play: Play dictionary
            
        Returns:
            Tuple of (should_enter, details_dict)
        """
        self.logger.warning("EMA cross momentum type not yet implemented, using manual entry")
        # Fall back to manual entry evaluation for now
        should_enter = self._evaluate_entry_conditions(play)
        return should_enter, {'ema_cross_status': 'not_implemented'}
    
    # =========================================================================
    # Gap Validation Helpers
    # =========================================================================
    
    def _validate_gap_info(
        self, 
        play: Dict[str, Any], 
        gap_info: Dict[str, Any]
    ) -> bool:
        """
        Validate gap information meets strategy requirements.
        
        Args:
            play: Play dictionary
            gap_info: Gap information from play
            
        Returns:
            True if gap is valid for trading
        """
        if not gap_info:
            self.logger.debug("No gap_info in play")
            return False
        
        gap_pct = gap_info.get('gap_pct', 0)
        gap_type = gap_info.get('gap_type', '')
        
        # Get min/max gap from playbook or defaults
        min_gap = self.get_playbook_setting(
            play, 'momentum_config.min_gap_pct', 1.0
        )
        max_gap = self.get_playbook_setting(
            play, 'momentum_config.max_gap_pct', None
        )
        
        # Get allowed gap types from playbook
        allowed_gap_type = self.get_playbook_setting(
            play, 'momentum_config.gap_type', 'any'
        )
        
        # Check gap type
        if allowed_gap_type != 'any':
            if gap_type.lower() != allowed_gap_type.lower():
                self.logger.debug(
                    f"Gap type {gap_type} doesn't match required {allowed_gap_type}"
                )
                return False
        
        # Check gap size
        abs_gap = abs(gap_pct)
        if abs_gap < min_gap:
            self.logger.debug(
                f"Gap {abs_gap:.2f}% below minimum {min_gap:.2f}%"
            )
            return False
        
        if max_gap is not None and abs_gap > max_gap:
            self.logger.debug(
                f"Gap {abs_gap:.2f}% exceeds maximum {max_gap:.2f}%"
            )
            return False
        
        return True
    
    def _check_confirmation_period(
        self, 
        play: Dict[str, Any], 
        gap_info: Dict[str, Any]
    ) -> bool:
        """
        Check if confirmation period has passed (if required).
        
        Some playbooks wait for price confirmation before entry
        to avoid false breakouts.
        
        Args:
            play: Play dictionary
            gap_info: Gap information
            
        Returns:
            True if confirmation period satisfied or not required
        """
        wait_for_confirmation = self.get_playbook_setting(
            play, 'momentum_config.wait_for_confirmation', False
        )
        
        if not wait_for_confirmation:
            return True
        
        confirmation_minutes = self.get_playbook_setting(
            play, 'momentum_config.confirmation_period_minutes', 15
        )
        
        # Get market open time (9:30 AM ET)
        now = datetime.now()
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        
        # Check if we've passed the confirmation period
        confirmation_time = market_open + timedelta(minutes=confirmation_minutes)
        
        if now < confirmation_time:
            self.logger.debug(
                f"Waiting for confirmation: {confirmation_minutes} mins after open "
                f"(current: {now.strftime('%H:%M')}, target: {confirmation_time.strftime('%H:%M')})"
            )
            return False
        
        # Optionally check if confirmation_time is set in play
        play_confirmation = gap_info.get('confirmation_time')
        if play_confirmation:
            try:
                conf_dt = datetime.strptime(play_confirmation, "%Y-%m-%d %H:%M:%S")
                if now < conf_dt:
                    return False
            except ValueError:
                pass
        
        return True
    
    def _evaluate_entry_conditions(self, play: Dict[str, Any]) -> bool:
        """
        Evaluate if stock price entry conditions are met.
        
        Uses the shared evaluate_opening_strategy function for
        consistency with other long strategies.
        
        Args:
            play: Play dictionary
            
        Returns:
            True if entry conditions met
        """
        symbol = play.get('symbol', '')
        
        # Use shared evaluation logic (same as option_swings)
        return evaluate_opening_strategy(
            symbol=symbol,
            play=play,
            get_stock_price_fn=self._get_stock_price
        )
    
    # =========================================================================
    # Exit Evaluation
    # =========================================================================
    
    def evaluate_open_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Evaluate open positions for exit conditions.
        
        For momentum (long premium), exits on:
        - Take profit: Premium increased by target %
        - Stop loss: Premium decreased by target %
        - Time exit: Same-day close or max hold days
        - Trailing stop: If enabled and triggered
        
        Args:
            plays: List of play dictionaries from 'open' folder
        
        Returns:
            List of tuples: (play, close_conditions) for plays to close
        """
        plays_to_close = []
        
        for play in plays:
            play_file = play.get('_play_file', '')
            symbol = play.get('symbol', '')
            
            try:
                # Check time-based exits first
                time_exit = self._check_time_exit(play)
                if time_exit:
                    close_conditions = {
                        'should_close': True,
                        'is_profit': False,  # Will be determined by P&L
                        'is_primary_loss': False,
                        'is_contingency_loss': False,
                        'is_time_exit': True,
                        'exit_reason': time_exit,
                        'sl_type': 'LIMIT'
                    }
                    
                    self.log_trade_action('EXIT_SIGNAL_TIME', play, {
                        'action': 'STC',
                        'reason': time_exit
                    })
                    
                    plays_to_close.append((play, close_conditions))
                    continue
                
                # Evaluate standard TP/SL conditions using shared module
                close_conditions = evaluate_closing_strategy(
                    symbol=symbol,
                    play=play,
                    play_file=play_file,
                    get_stock_price_fn=self._get_stock_price,
                    get_option_data_fn=self._get_option_data,
                    save_play_fn=save_play_improved
                )
                
                if close_conditions.get('should_close', False):
                    close_type = 'TP' if close_conditions.get('is_profit') else 'SL'
                    if close_conditions.get('is_contingency_loss'):
                        close_type = 'SL(CONTINGENCY)'
                    
                    self.log_trade_action(f'EXIT_SIGNAL_{close_type}', play, {
                        'action': 'STC',
                        'is_profit': close_conditions.get('is_profit'),
                        'sl_type': close_conditions.get('sl_type')
                    })
                    
                    plays_to_close.append((play, close_conditions))
                    
            except Exception as e:
                self.logger.error(f"Error evaluating open play {symbol}: {e}")
                continue
        
        return plays_to_close
    
    def _check_time_exit(self, play: Dict[str, Any]) -> Optional[str]:
        """
        Check if position should be closed due to time-based rules.
        
        Checks:
        - Same-day exit requirement
        - Max hold days exceeded
        - Exit before close timing
        
        Args:
            play: Play dictionary
            
        Returns:
            Exit reason string if should exit, None otherwise
        """
        now = datetime.now()
        
        # Check same-day exit
        same_day_exit = self.get_playbook_setting(
            play, 'momentum_config.same_day_exit', False
        )
        
        if same_day_exit:
            time_mgmt = play.get('time_management', {})
            exit_before_close = time_mgmt.get('exit_before_close', True)
            exit_minutes = time_mgmt.get('exit_minutes_before_close', 15)
            
            # Market closes at 4:00 PM ET
            market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
            exit_time = market_close - timedelta(minutes=exit_minutes)
            
            if now >= exit_time:
                return f"Same-day exit: {exit_minutes} mins before close"
        
        # Check max hold days
        max_hold_days = self.get_playbook_setting(
            play, 'momentum_config.max_hold_days', None
        )
        
        if max_hold_days is not None:
            open_datetime = play.get('logging', {}).get('datetime_atOpen')
            if open_datetime:
                try:
                    if isinstance(open_datetime, str):
                        open_dt = datetime.strptime(open_datetime, "%Y-%m-%d %H:%M:%S")
                    else:
                        open_dt = open_datetime
                    
                    days_held = (now - open_dt).days
                    if days_held >= max_hold_days:
                        return f"Max hold days exceeded: {days_held} >= {max_hold_days}"
                        
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Could not parse open datetime: {e}")
        
        return None
    
    # =========================================================================
    # Validation
    # =========================================================================
    
    def validate_play(self, play: Dict[str, Any]) -> bool:
        """
        Validate play data structure for momentum strategy.
        """
        # Base validation
        if not super().validate_play(play):
            return False
        
        # Momentum-specific required fields
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
        
        # Validate trade_type is CALL or PUT
        trade_type = play.get('trade_type', '').upper()
        if trade_type not in ('CALL', 'PUT'):
            self.logger.warning(f"Invalid trade_type: {trade_type}")
            return False
        
        # Validate action is BTO (if specified)
        action = play.get('action', 'BTO').upper()
        if action not in ('BTO', 'BUY_TO_OPEN'):
            self.logger.warning(f"momentum requires action: BTO, got: {action}")
            return False
        
        # Validate entry_point structure
        entry_point = play.get('entry_point', {})
        if 'order_type' not in entry_point:
            self.logger.warning("Play entry_point missing order_type")
            return False
        
        return True
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _get_stock_price(self, symbol: str) -> Optional[float]:
        """Get current stock price."""
        try:
            price = self.market_data.get_stock_price(symbol)
            if price is not None:
                if hasattr(price, 'item'):
                    price = float(price.item())
                return float(price)
            return None
        except Exception as e:
            self.logger.error(f"Error getting stock price for {symbol}: {e}")
            return None
    
    def _get_option_data(self, option_symbol: str) -> Optional[Dict[str, float]]:
        """Get current option quote data."""
        try:
            return self.market_data.get_option_quote(option_symbol)
        except Exception as e:
            self.logger.error(f"Error getting option data for {option_symbol}: {e}")
            return None
    
    def _is_play_expired(self, play: Dict[str, Any]) -> bool:
        """Check if play has passed its expiration date."""
        play_expiration = play.get('play_expiration_date')
        if not play_expiration:
            return False
        
        try:
            exp_date = datetime.strptime(play_expiration, "%m/%d/%Y").date()
            return exp_date < datetime.now().date()
        except ValueError:
            self.logger.warning(f"Invalid play_expiration_date: {play_expiration}")
            return False
    
    def _is_dte_acceptable(self, play: Dict[str, Any]) -> bool:
        """
        Check if option DTE is within acceptable range.
        
        Uses playbook settings if available.
        """
        expiration_str = play.get('expiration_date')
        if not expiration_str:
            return True
        
        try:
            expiration = datetime.strptime(expiration_str, "%m/%d/%Y").date()
            today = datetime.now().date()
            dte = (expiration - today).days
            
            # Get DTE range from playbook or defaults
            dte_min = self.get_playbook_setting(play, 'entry.dte_min', 
                      self.get_playbook_setting(play, 'momentum_config.dte_min', 7))
            dte_max = self.get_playbook_setting(play, 'entry.dte_max',
                      self.get_playbook_setting(play, 'momentum_config.dte_max', 21))
            
            return dte_min <= dte <= dte_max
            
        except ValueError:
            return True
    
    def get_strategy_config(self) -> Dict[str, Any]:
        """Get cached strategy configuration."""
        if self._strategy_config is None:
            config_section = self.config.get(self.get_config_section())
            self._strategy_config = config_section if config_section is not None else {}
        return self._strategy_config if self._strategy_config is not None else {}
    
    # =========================================================================
    # Gap Analysis Helpers
    # =========================================================================
    
    def calculate_gap_info(
        self, 
        symbol: str, 
        previous_close: float, 
        current_open: float
    ) -> Dict[str, Any]:
        """
        Calculate gap information for a symbol.
        
        This is a utility method that can be used by play creation tools
        to populate the gap_info section.
        
        Args:
            symbol: Stock symbol
            previous_close: Previous day's closing price
            current_open: Current day's opening price
            
        Returns:
            Dict with gap_type, gap_pct, previous_close, gap_open
        """
        if previous_close <= 0:
            return {}
        
        gap_amount = current_open - previous_close
        gap_pct = (gap_amount / previous_close) * 100
        
        if gap_pct > 0:
            gap_type = "up"
        elif gap_pct < 0:
            gap_type = "down"
        else:
            gap_type = "flat"
        
        return {
            'gap_type': gap_type,
            'gap_pct': round(gap_pct, 2),
            'previous_close': previous_close,
            'gap_open': current_open,
            'trade_direction': None,  # Set by play creator based on playbook
            'confirmation_time': None
        }
    
    def get_trade_type_for_gap(
        self, 
        gap_type: str, 
        trade_direction: str
    ) -> str:
        """
        Determine option type (CALL/PUT) based on gap and direction.
        
        Args:
            gap_type: "up" or "down"
            trade_direction: "with_gap" or "fade_gap"
            
        Returns:
            "CALL" or "PUT"
        """
        if trade_direction == "with_gap":
            # Trade with the gap direction
            return "CALL" if gap_type == "up" else "PUT"
        else:  # fade_gap
            # Trade against the gap direction
            return "PUT" if gap_type == "up" else "CALL"
    
    # =========================================================================
    # Order Execution Methods
    # =========================================================================
    
    def open_position(self, play: Dict[str, Any], play_file: str) -> bool:
        """
        Open a long option position.
        
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
        Close an open long option position.
        
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


__all__ = ['MomentumStrategy']

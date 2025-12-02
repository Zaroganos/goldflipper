"""
Spreads Strategy Runner

This module implements options spread strategies including vertical spreads,
iron condors, and butterflies. This is "Kegan's Strategy" per the config.

Status: IMPLEMENTED - Multi-leg support with entry/exit evaluation
Priority: P3

Configuration section: spreads (in settings.yaml)
Default: enabled: false

Trade Direction: MULTI-LEG (varies by spread type and leg)

Spread strategies involve multiple options contracts (legs) with different
order actions per leg:

    Bull Call Spread: BTO lower strike call + STO higher strike call
    Bear Put Spread:  BTO higher strike put + STO lower strike put
    Iron Condor:      STO call spread (credit) + STO put spread (credit)
    Butterfly:        BTO 1x wing + STO 2x body + BTO 1x wing

Each leg has its own OrderAction, and the spread must be executed atomically.

Play JSON Structure for Spreads:
{
    "symbol": "SPY",
    "spread_type": "bull_call",
    "is_credit": false,
    "net_premium": 1.50,  # Net debit/credit at entry
    "legs": [
        {"symbol": "SPY241220C00590000", "action": "BTO", "contracts": 1, "ratio": 1},
        {"symbol": "SPY241220C00600000", "action": "STO", "contracts": 1, "ratio": 1}
    ],
    "entry_point": {
        "stock_price": 595.0,
        "stock_price_low": 590.0,
        "stock_price_high": 600.0,
        "order_type": "limit",
        "limit_price": 1.50  # Net limit for the spread
    },
    "take_profit": {
        "net_premium_target": 2.25,  # Target net value of spread
        "premium_pct": 50.0,  # Or percentage gain
        "max_profit_pct": 80.0  # Close at 80% of max profit
    },
    "stop_loss": {
        "net_premium_target": 0.75,  # Exit if net value falls to this
        "premium_pct": 50.0,  # Or percentage loss
        "max_loss_pct": 50.0  # Close at 50% of max loss
    },
    ...
}
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum

from goldflipper.strategy.base import BaseStrategy, PlayStatus, OrderAction, PositionSide
from goldflipper.strategy.registry import register_strategy
from goldflipper.strategy.shared import save_play_improved


class SpreadType(Enum):
    """Types of options spreads supported by this strategy."""
    # Vertical spreads (same expiration, different strikes)
    BULL_CALL_SPREAD = "bull_call"      # Debit spread: BTO lower, STO higher
    BEAR_CALL_SPREAD = "bear_call"      # Credit spread: STO lower, BTO higher
    BULL_PUT_SPREAD = "bull_put"        # Credit spread: STO higher, BTO lower
    BEAR_PUT_SPREAD = "bear_put"        # Debit spread: BTO higher, STO lower
    
    # Multi-leg complex spreads
    IRON_CONDOR = "iron_condor"         # 4 legs: sell call spread + sell put spread
    IRON_BUTTERFLY = "iron_butterfly"   # 4 legs at same strike
    BUTTERFLY = "butterfly"             # 3 strikes: buy 1, sell 2, buy 1
    CALENDAR_SPREAD = "calendar"        # Same strike, different expirations
    DIAGONAL_SPREAD = "diagonal"        # Different strike and expiration
    
    # Strangles/Straddles
    STRANGLE = "strangle"               # STO OTM call + STO OTM put
    STRADDLE = "straddle"               # STO ATM call + STO ATM put


class SpreadLeg:
    """
    Represents a single leg in a multi-leg spread.
    
    Attributes:
        symbol: Option contract symbol
        action: OrderAction for this leg (BTO, STO, etc.)
        contracts: Number of contracts for this leg
        ratio: Leg ratio (e.g., 2 for butterfly body)
    """
    def __init__(
        self,
        symbol: str,
        action: OrderAction,
        contracts: int = 1,
        ratio: int = 1
    ):
        self.symbol = symbol
        self.action = action
        self.contracts = contracts
        self.ratio = ratio
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert leg to dictionary for serialization."""
        return {
            'symbol': self.symbol,
            'action': self.action.value,
            'contracts': self.contracts,
            'ratio': self.ratio
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpreadLeg':
        """Create leg from dictionary."""
        return cls(
            symbol=data['symbol'],
            action=OrderAction.from_string(data['action']),
            contracts=data.get('contracts', 1),
            ratio=data.get('ratio', 1)
        )


@register_strategy('spreads')
class SpreadsStrategy(BaseStrategy):
    """
    Options Spreads Strategy (Kegan's Strategy).
    
    This is a STUB implementation. The strategy is registered but has
    minimal functionality. Full implementation is planned for a future phase.
    
    Trade Direction: MULTI-LEG
    
    Unlike single-leg strategies (option_swings, sell_puts), spreads involve
    multiple legs with DIFFERENT order actions. For example:
    
        Bull Call Spread:
        - Leg 1: BUY_TO_OPEN lower strike call
        - Leg 2: SELL_TO_OPEN higher strike call
        
    The spread's overall P&L depends on the net premium (debit or credit)
    and how the legs move relative to each other.
    
    Credit vs Debit Spreads:
    - Credit spread: Net premium collected at entry (STO dominant)
    - Debit spread: Net premium paid at entry (BTO dominant)
    
    Planned spread types:
    - Vertical spreads (bull call, bear put, etc.)
    - Iron condors
    - Butterflies
    - Calendar spreads
    
    Configuration section: spreads
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        market_data: Any,
        brokerage_client: Any
    ):
        """Initialize the Spreads strategy."""
        super().__init__(config, market_data, brokerage_client)
        self.logger.info(f"SpreadsStrategy initialized (enabled={self.is_enabled()})")
    
    def get_name(self) -> str:
        """Return unique strategy identifier."""
        return "spreads"
    
    def get_config_section(self) -> str:
        """Return the configuration section name."""
        return "spreads"
    
    def get_plays_base_dir(self) -> str:
        """Return base directory for play files."""
        return "plays"
    
    def get_priority(self) -> int:
        """Return execution priority (lower = higher priority)."""
        return 150  # Lower priority (runs later)
    
    # =========================================================================
    # Order Action Methods - Multi-leg handling
    # =========================================================================
    
    def get_default_entry_action(self) -> OrderAction:
        """
        Return default entry action.
        
        For spreads, this is less meaningful since each leg has its own action.
        Returns BTO as a fallback, but real logic should use get_legs_for_play().
        """
        return OrderAction.BUY_TO_OPEN
    
    def is_multi_leg_strategy(self) -> bool:
        """Return True - spreads are always multi-leg."""
        return True
    
    def get_legs_for_play(self, play: Dict[str, Any]) -> List[SpreadLeg]:
        """
        Extract the legs from a spread play.
        
        Spread plays should have a 'legs' array with each leg's details.
        
        Args:
            play: Play dictionary
        
        Returns:
            List of SpreadLeg objects
        """
        legs_data = play.get('legs', [])
        return [SpreadLeg.from_dict(leg) for leg in legs_data]
    
    def get_spread_type(self, play: Dict[str, Any]) -> Optional[SpreadType]:
        """
        Determine the spread type from play data.
        
        Args:
            play: Play dictionary
        
        Returns:
            SpreadType enum or None if not specified/recognized
        """
        spread_type_str = play.get('spread_type')
        if not spread_type_str:
            return None
        
        try:
            return SpreadType(spread_type_str)
        except ValueError:
            self.logger.warning(f"Unknown spread type: {spread_type_str}")
            return None
    
    def is_credit_spread(self, play: Dict[str, Any]) -> bool:
        """
        Determine if a spread is a credit spread (net premium collected).
        
        Args:
            play: Play dictionary
        
        Returns:
            True if credit spread, False if debit spread
        """
        # Can be explicitly set in play
        if 'is_credit' in play:
            return play['is_credit']
        
        # Or infer from spread type
        spread_type = self.get_spread_type(play)
        credit_spreads = {
            SpreadType.BEAR_CALL_SPREAD,
            SpreadType.BULL_PUT_SPREAD,
            SpreadType.IRON_CONDOR,
            SpreadType.STRANGLE,
            SpreadType.STRADDLE,
        }
        return spread_type in credit_spreads
    
    def get_closing_legs(self, play: Dict[str, Any]) -> List[SpreadLeg]:
        """
        Get the closing legs for an open spread position.
        
        Each leg's action is reversed (BTO → STC, STO → BTC).
        
        Args:
            play: Play dictionary with open position
        
        Returns:
            List of SpreadLeg objects with closing actions
        """
        entry_legs = self.get_legs_for_play(play)
        closing_legs = []
        
        for leg in entry_legs:
            closing_action = leg.action.get_closing_action()
            closing_legs.append(SpreadLeg(
                symbol=leg.symbol,
                action=closing_action,
                contracts=leg.contracts,
                ratio=leg.ratio
            ))
        
        return closing_legs
    
    # =========================================================================
    # Play Validation
    # =========================================================================
    
    def validate_play(self, play: Dict[str, Any]) -> bool:
        """
        Validate spread play data structure.
        
        Spread plays require 'legs' array with at least 2 legs.
        """
        if not super().validate_play(play):
            return False
        
        # Spread-specific required fields
        required_fields = ['legs', 'spread_type']
        for field in required_fields:
            if field not in play:
                self.logger.warning(f"Spread play missing required field: {field}")
                return False
        
        # Validate legs
        legs = play.get('legs', [])
        if len(legs) < 2:
            self.logger.warning("Spread play must have at least 2 legs")
            return False
        
        # Validate each leg has required fields
        for i, leg in enumerate(legs):
            if not isinstance(leg, dict):
                self.logger.warning(f"Leg {i} must be a dictionary")
                return False
            if 'symbol' not in leg or 'action' not in leg:
                self.logger.warning(f"Leg {i} missing 'symbol' or 'action'")
                return False
        
        return True
    
    # =========================================================================
    # Market Data Helpers
    # =========================================================================
    
    def _get_stock_price(self, symbol: str) -> Optional[float]:
        """Get current stock price using market data manager."""
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
        """Get current option quote data for a single leg."""
        try:
            return self.market_data.get_option_quote(option_symbol)
        except Exception as e:
            self.logger.error(f"Error getting option data for {option_symbol}: {e}")
            return None
    
    def _get_current_spread_value(self, play: Dict[str, Any]) -> Optional[float]:
        """
        Calculate the current net value of the spread.
        
        For each leg:
        - BTO legs: Add current bid (what we'd get if we sold)
        - STO legs: Subtract current ask (what we'd pay to buy back)
        
        Returns:
            Net value of spread (positive for profit in credit spreads,
            positive for value in debit spreads)
        """
        legs = self.get_legs_for_play(play)
        if not legs:
            return None
        
        net_value = 0.0
        
        for leg in legs:
            option_data = self._get_option_data(leg.symbol)
            if option_data is None:
                self.logger.warning(f"Could not get quote for {leg.symbol}")
                return None
            
            bid = option_data.get('bid', 0.0)
            ask = option_data.get('ask', 0.0)
            contracts = leg.contracts * leg.ratio
            
            if leg.action.is_long():
                # Long leg: value is what we could sell for (bid)
                net_value += bid * contracts * 100
            else:
                # Short leg: liability is what we'd pay to close (ask)
                net_value -= ask * contracts * 100
        
        return net_value
    
    def _is_play_expired(self, play: Dict[str, Any]) -> bool:
        """Check if play has passed its expiration date."""
        play_expiration = play.get('play_expiration_date')
        if not play_expiration:
            return False
        
        try:
            exp_date = datetime.strptime(play_expiration, "%m/%d/%Y").date()
            return exp_date < datetime.now().date()
        except ValueError:
            self.logger.warning(f"Invalid play_expiration_date format: {play_expiration}")
            return False
    
    # =========================================================================
    # Entry Evaluation
    # =========================================================================
    
    def evaluate_new_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate spread plays for entry conditions.
        
        Entry conditions for spreads:
        1. Stock price within entry range
        2. Net spread premium meets limit price requirement
        3. Play hasn't expired
        
        Args:
            plays: List of play dictionaries from 'new' folder
        
        Returns:
            List of plays that should be opened
        """
        plays_to_open = []
        
        for play in plays:
            play_file = play.get('_play_file', '')
            symbol = play.get('symbol', '')
            
            try:
                # Validate
                if not self.validate_play(play):
                    self.logger.warning(f"Spread play validation failed: {play_file}")
                    continue
                
                # Check expiration
                if self._is_play_expired(play):
                    self.logger.info(f"Spread play expired, skipping: {symbol}")
                    continue
                
                # Get current stock price
                stock_price = self._get_stock_price(symbol)
                if stock_price is None:
                    self.logger.warning(f"Could not get price for {symbol}")
                    continue
                
                # Check stock price entry range
                entry_point = play.get('entry_point', {})
                price_low = entry_point.get('stock_price_low', 0)
                price_high = entry_point.get('stock_price_high', float('inf'))
                
                if not (price_low <= stock_price <= price_high):
                    self.logger.debug(
                        f"Stock price {stock_price:.2f} outside entry range "
                        f"[{price_low:.2f}, {price_high:.2f}]"
                    )
                    continue
                
                # Calculate current spread net premium
                current_value = self._get_current_spread_value(play)
                if current_value is None:
                    self.logger.warning(f"Could not calculate spread value for {symbol}")
                    continue
                
                # For limit orders, check if we can get our desired fill
                order_type = entry_point.get('order_type', 'market')
                if order_type == 'limit':
                    limit_price = entry_point.get('limit_price')
                    if limit_price:
                        is_credit = self.is_credit_spread(play)
                        # Convert to per-share value
                        current_per_share = abs(current_value / 100)
                        
                        if is_credit:
                            # Credit spread: We want to collect at least limit_price
                            if current_per_share < limit_price:
                                self.logger.debug(
                                    f"Credit spread value ${current_per_share:.2f} "
                                    f"below limit ${limit_price:.2f}"
                                )
                                continue
                        else:
                            # Debit spread: We want to pay at most limit_price
                            if current_per_share > limit_price:
                                self.logger.debug(
                                    f"Debit spread cost ${current_per_share:.2f} "
                                    f"above limit ${limit_price:.2f}"
                                )
                                continue
                
                # All conditions met
                spread_type = play.get('spread_type', 'unknown')
                self.log_trade_action('ENTRY_SIGNAL', play, {
                    'spread_type': spread_type,
                    'stock_price': stock_price,
                    'legs': len(play.get('legs', []))
                })
                plays_to_open.append(play)
                
            except Exception as e:
                self.logger.error(f"Error evaluating spread play {symbol}: {e}")
                continue
        
        return plays_to_open
    
    # =========================================================================
    # Exit Evaluation
    # =========================================================================
    
    def evaluate_open_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Evaluate open spread positions for exit conditions.
        
        Exit conditions for spreads:
        1. Net spread value reaches take profit target
        2. Net spread value reaches stop loss target
        3. Max profit/loss percentage thresholds
        4. Play expiration approaching (DTE management)
        
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
                # Get current spread value
                current_value = self._get_current_spread_value(play)
                if current_value is None:
                    self.logger.warning(f"Could not calculate spread value for {symbol}")
                    continue
                
                # Get entry values
                entry_net = play.get('entry_point', {}).get('entry_net_premium', 0)
                is_credit = self.is_credit_spread(play)
                
                # Calculate P&L
                if is_credit:
                    # Credit spread: Profit when spread value decreases
                    # Entry: We collected premium (positive cash flow)
                    # Exit: We pay to close (current_value is negative liability)
                    pnl = entry_net * 100 + current_value  # Both in dollars
                else:
                    # Debit spread: Profit when spread value increases
                    # Entry: We paid premium (negative cash flow)
                    # Exit: We receive value (current_value is positive)
                    pnl = current_value - entry_net * 100
                
                # Initialize condition flags
                tp_hit = False
                sl_hit = False
                close_reason = None
                
                take_profit = play.get('take_profit', {})
                stop_loss = play.get('stop_loss', {})
                
                # Check premium percentage targets
                if entry_net and entry_net != 0:
                    pnl_pct = (pnl / abs(entry_net * 100)) * 100
                    
                    # Take profit by percentage
                    tp_pct = take_profit.get('premium_pct')
                    if tp_pct and pnl_pct >= tp_pct:
                        tp_hit = True
                        close_reason = f"TP hit: {pnl_pct:.1f}% >= {tp_pct}%"
                    
                    # Stop loss by percentage
                    sl_pct = stop_loss.get('premium_pct')
                    if sl_pct and pnl_pct <= -sl_pct:
                        sl_hit = True
                        close_reason = f"SL hit: {pnl_pct:.1f}% <= -{sl_pct}%"
                
                # Check absolute net premium targets
                current_per_share = current_value / 100
                
                tp_target = take_profit.get('net_premium_target')
                if tp_target:
                    if is_credit:
                        # For credit spreads, we profit when we can buy back cheaper
                        if abs(current_per_share) <= tp_target:
                            tp_hit = True
                            close_reason = f"TP hit: Net ${current_per_share:.2f} <= ${tp_target:.2f}"
                    else:
                        # For debit spreads, we profit when spread value increases
                        if current_per_share >= tp_target:
                            tp_hit = True
                            close_reason = f"TP hit: Net ${current_per_share:.2f} >= ${tp_target:.2f}"
                
                sl_target = stop_loss.get('net_premium_target')
                if sl_target:
                    if is_credit:
                        # For credit spreads, we lose when buyback cost exceeds threshold
                        if abs(current_per_share) >= sl_target:
                            sl_hit = True
                            close_reason = f"SL hit: Net ${current_per_share:.2f} >= ${sl_target:.2f}"
                    else:
                        # For debit spreads, we lose when spread value decreases
                        if current_per_share <= sl_target:
                            sl_hit = True
                            close_reason = f"SL hit: Net ${current_per_share:.2f} <= ${sl_target:.2f}"
                
                # Check max profit percentage (for credit spreads)
                max_profit_pct = take_profit.get('max_profit_pct')
                if max_profit_pct and is_credit:
                    max_profit = entry_net * 100  # Max profit is premium collected
                    if max_profit > 0:
                        profit_captured = (pnl / max_profit) * 100
                        if profit_captured >= max_profit_pct:
                            tp_hit = True
                            close_reason = f"Max profit {profit_captured:.1f}% >= {max_profit_pct}%"
                
                # Build close conditions
                if tp_hit or sl_hit:
                    close_conditions = {
                        'should_close': True,
                        'is_profit': tp_hit,
                        'is_primary_loss': sl_hit,
                        'is_contingency_loss': False,
                        'close_reason': close_reason,
                        'current_value': current_value,
                        'pnl': pnl,
                        'is_credit': is_credit,
                        'sl_type': stop_loss.get('SL_type', 'MARKET')
                    }
                    
                    close_type = 'TP' if tp_hit else 'SL'
                    self.log_trade_action(f'EXIT_SIGNAL_{close_type}', play, {
                        'reason': close_reason,
                        'pnl': f"${pnl:.2f}"
                    })
                    
                    plays_to_close.append((play, close_conditions))
                    
            except Exception as e:
                self.logger.error(f"Error evaluating open spread {symbol}: {e}")
                continue
        
        return plays_to_close
    
    # =========================================================================
    # Position Management
    # =========================================================================
    
    def open_position(self, play: Dict[str, Any], play_file: str) -> bool:
        """
        Open a spread position (multi-leg order).
        
        Note: Currently delegates to core.py. Future implementation will
        use Alpaca's multi-leg order API directly.
        """
        try:
            # For now, delegate to core.py
            from goldflipper.core import open_position as core_open_position
            return core_open_position(play, play_file)
        except Exception as e:
            self.logger.error(f"Error opening spread position: {e}")
            return False
    
    def close_position(
        self, 
        play: Dict[str, Any], 
        close_conditions: Dict[str, Any],
        play_file: str
    ) -> bool:
        """
        Close a spread position (multi-leg order).
        
        Note: Currently delegates to core.py. Future implementation will
        use Alpaca's multi-leg order API directly.
        """
        try:
            from goldflipper.core import close_position as core_close_position
            return core_close_position(play, close_conditions, play_file)
        except Exception as e:
            self.logger.error(f"Error closing spread position: {e}")
            return False


__all__ = ['SpreadsStrategy', 'SpreadType', 'SpreadLeg']

"""
Spreads Strategy Runner (Stub)

This module implements options spread strategies including vertical spreads,
iron condors, and butterflies. This is "Kegan's Strategy" per the config.

Status: STUB - Placeholder for future implementation
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
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum

from goldflipper.strategy.base import BaseStrategy, PlayStatus, OrderAction, PositionSide
from goldflipper.strategy.registry import register_strategy


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
    # Stub implementations
    # =========================================================================
    
    def evaluate_new_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate plays for entry conditions.
        
        STUB: Returns empty list (no plays to open).
        """
        self.logger.debug("spreads: evaluate_new_plays (stub - no implementation)")
        return []
    
    def evaluate_open_plays(
        self, 
        plays: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Evaluate open positions for exit conditions.
        
        STUB: Returns empty list (no plays to close).
        """
        self.logger.debug("spreads: evaluate_open_plays (stub - no implementation)")
        return []


__all__ = ['SpreadsStrategy', 'SpreadType', 'SpreadLeg']

"""
Dynamic GTD (Good-Til-Date) Base Module

Defines the abstract base class, data structures, and enums for the Dynamic GTD framework.
Dynamic GTD is an overlay on top of the static play_expiration_date, allowing methods to
shorten or extend the effective play lifespan based on real-world options trading strategies.

Key design principle: The static play_expiration_date remains as the hard backstop.
Dynamic methods can shorten the lifespan (most methods) or extend it (profit-conditional
only, capped at option expiration date).

Usage:
    from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDContext, GTDResult, GTDAction

    class MyGTDMethod(DynamicGTDMethod):
        def get_name(self) -> str:
            return "my_method"

        def evaluate(self, context: GTDContext) -> GTDResult:
            # ... evaluation logic
            return GTDResult(action=GTDAction.HOLD, reason="No action needed")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class GTDAction(Enum):
    """Actions that a GTD method can recommend.

    HOLD: No change to effective date (method has no opinion this cycle)
    SHORTEN: Move effective date earlier (reduce remaining hold time)
    EXTEND: Move effective date later (only profit-conditional, capped at option expiration)
    CLOSE_NOW: Immediately close the position (highest priority, overrides all other actions)
    """

    HOLD = "hold"
    SHORTEN = "shorten"
    EXTEND = "extend"
    CLOSE_NOW = "close_now"


@dataclass(frozen=True)
class GTDContext:
    """Immutable context provided to each GTD method during evaluation.

    Contains all information a method might need to make its decision.
    Market data fields are Optional because not all methods require them
    and they may not always be available.

    Attributes:
        play: The full play dictionary
        current_date: Today's date
        entry_date: Date the position was opened (None if not yet open)
        play_expiration_date: Static play expiration from play JSON
        option_expiration_date: Option contract expiration date
        current_effective_date: Current dynamic GTD effective date (None if not yet set)
        current_price: Current stock price (None if unavailable)
        entry_price: Stock price at entry (None if not recorded)
        current_premium: Current option premium (None if unavailable)
        entry_premium: Option premium at entry (None if not recorded)
        unrealized_pnl_pct: Unrealized P/L as percentage (None if not calculable)
        greeks: Dict of current greeks {delta, gamma, theta, vega, rho} (empty if unavailable)
        days_held: Number of trading days held (None if not calculable)
        days_to_expiry: Calendar days to option expiration (None if not calculable)
        is_market_open: Whether market is currently open
        upcoming_events: List of event dicts {type, date, symbol} (e.g., earnings, FOMC)
        method_state: Persisted state dict for this specific method instance
        method_params: Configuration parameters for this method from play JSON
    """

    play: dict[str, Any]
    current_date: date
    entry_date: date | None = None
    play_expiration_date: date | None = None
    option_expiration_date: date | None = None
    current_effective_date: date | None = None
    current_price: float | None = None
    entry_price: float | None = None
    current_premium: float | None = None
    entry_premium: float | None = None
    unrealized_pnl_pct: float | None = None
    greeks: dict[str, float] = field(default_factory=dict)
    days_held: int | None = None
    days_to_expiry: int | None = None
    is_market_open: bool = True
    upcoming_events: list[dict[str, Any]] = field(default_factory=list)
    method_state: dict[str, Any] = field(default_factory=dict)
    method_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class GTDResult:
    """Result returned by a GTD method's evaluate() call.

    Attributes:
        action: The recommended GTDAction
        recommended_date: The suggested new effective date (required for SHORTEN/EXTEND, ignored for HOLD/CLOSE_NOW)
        reason: Human-readable explanation for the decision
        priority: Numeric priority (lower = higher priority). Used for conflict resolution
                  among methods recommending the same action type. Default 100.
        metadata: Optional dict for method-specific data to log or persist
    """

    action: GTDAction
    recommended_date: date | None = None
    reason: str = ""
    priority: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)


class DynamicGTDMethod(ABC):
    """Abstract base class for all Dynamic GTD methods.

    Each method implements a specific strategy for adjusting the effective
    play expiration date. Methods are registered with the GTDRegistry via
    the @register_gtd_method decorator and instantiated by the GTDEvaluator.

    Lifecycle:
        1. Method is instantiated (once per play evaluation cycle)
        2. evaluate() is called with a GTDContext
        3. Result is collected and fed into conflict resolution
        4. If state changed, get_state() is called to persist

    Example:
        @register_gtd_method('max_hold_days')
        class MaxHoldDaysMethod(DynamicGTDMethod):
            def get_name(self) -> str:
                return "max_hold_days"

            def evaluate(self, context: GTDContext) -> GTDResult:
                max_days = context.method_params.get('max_days', 5)
                if context.days_held is not None and context.days_held >= max_days:
                    return GTDResult(
                        action=GTDAction.CLOSE_NOW,
                        reason=f"Held {context.days_held} days, max is {max_days}"
                    )
                return GTDResult(action=GTDAction.HOLD, reason="Within hold period")
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return unique method identifier (e.g., 'max_hold_days')."""

    @abstractmethod
    def evaluate(self, context: GTDContext) -> GTDResult:
        """Evaluate the play and return a GTD action recommendation.

        Args:
            context: Immutable GTDContext with all relevant play/market data

        Returns:
            GTDResult with the recommended action
        """

    def get_default_params(self) -> dict[str, Any]:
        """Return default parameters for this method.

        These are used when the method is enabled but no custom params are provided.
        Override in subclasses to define method-specific defaults.

        Returns:
            Dict of parameter name -> default value
        """
        return {}

    def get_param_schema(self) -> dict[str, Any]:
        """Return a JSON-schema-like description of this method's parameters.

        Used by the GUI to render parameter input fields and for validation.
        Override in subclasses to describe method-specific parameters.

        Returns:
            Dict describing each parameter: {param_name: {type, description, default, min, max, ...}}
        """
        return {}

    def validate_config(self, params: dict[str, Any]) -> list[str]:
        """Validate method configuration parameters.

        Args:
            params: Parameter dict to validate

        Returns:
            List of validation error strings (empty if valid)
        """
        return []

    def get_state(self) -> dict[str, Any]:
        """Return any state that should be persisted between evaluation cycles.

        State is stored in the play JSON under dynamic_gtd.method_states[method_name].
        Override if the method needs to track information across cycles (e.g., rolling averages).

        Returns:
            Dict of state to persist (must be JSON-serializable)
        """
        return {}

    def load_state(self, state: dict[str, Any]) -> None:  # noqa: B027
        """Load previously persisted state.

        Called before evaluate() with the state from the previous cycle.

        Args:
            state: Previously persisted state dict
        """

    def requires_market_data(self) -> bool:
        """Whether this method requires live market data to evaluate.

        If True, the evaluator will skip this method when market data is unavailable.
        Most methods that only use dates/days_held can return False.

        Returns:
            True if market data is required
        """
        return False

    def __repr__(self) -> str:
        return f"<GTDMethod:{self.get_name()}>"

"""
Rolling GTD Method

Auto-extends the effective GTD as long as the position is above breakeven.
Once the position drops below breakeven, the rolling extension stops and
the current effective date becomes the hard deadline.

This method uses persisted state to track whether rolling is active.

Params:
    extension_days (int): Days to extend per evaluation cycle while eligible. Default: 1
    breakeven_buffer_pct (float): Buffer above breakeven to keep rolling (e.g., 1.0 = 1% above BE). Default: 0.0
"""

from datetime import timedelta
from typing import Any

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("rolling_gtd")
class RollingGTDMethod(DynamicGTDMethod):
    def __init__(self):
        self._rolling_active = True

    def get_name(self) -> str:
        return "rolling_gtd"

    def evaluate(self, context: GTDContext) -> GTDResult:
        extension_days = context.method_params.get("extension_days", 1)
        buffer_pct = context.method_params.get("breakeven_buffer_pct", 0.0)

        # Check if rolling was deactivated in a prior cycle
        if not self._rolling_active:
            return GTDResult(
                action=GTDAction.HOLD,
                reason="Rolling GTD deactivated (position previously dropped below breakeven)",
            )

        if context.unrealized_pnl_pct is None:
            return GTDResult(action=GTDAction.HOLD, reason="P/L not available for rolling GTD")

        # Check breakeven condition
        if context.unrealized_pnl_pct < buffer_pct:
            self._rolling_active = False
            return GTDResult(
                action=GTDAction.HOLD,
                reason=f"P/L {context.unrealized_pnl_pct:.1f}% below breakeven buffer of {buffer_pct}%, stopping rolling extension",
            )

        # Position is above breakeven — extend
        base_date = context.current_effective_date or context.play_expiration_date
        if base_date is None:
            return GTDResult(action=GTDAction.HOLD, reason="No base date available for rolling extension")

        extended_date = base_date + timedelta(days=extension_days)

        # Cap at option expiration
        if context.option_expiration_date is not None and extended_date > context.option_expiration_date:
            extended_date = context.option_expiration_date

        return GTDResult(
            action=GTDAction.EXTEND,
            recommended_date=extended_date,
            reason=f"Rolling extension: above breakeven ({context.unrealized_pnl_pct:.1f}%), extending by {extension_days} day(s)",
            priority=95,
        )

    def get_state(self) -> dict[str, Any]:
        return {"rolling_active": self._rolling_active}

    def load_state(self, state: dict[str, Any]) -> None:
        self._rolling_active = state.get("rolling_active", True)

    def get_default_params(self):
        return {"extension_days": 1, "breakeven_buffer_pct": 0.0}

    def get_param_schema(self):
        return {
            "extension_days": {
                "type": "integer",
                "description": "Days to extend per cycle while above breakeven",
                "default": 1,
                "min": 1,
                "max": 7,
            },
            "breakeven_buffer_pct": {
                "type": "number",
                "description": "P/L percentage above breakeven required to keep rolling (0 = exactly breakeven)",
                "default": 0.0,
                "min": -5.0,
                "max": 20.0,
            },
        }

    def requires_market_data(self) -> bool:
        return True

    def validate_config(self, params):
        errors = []
        days = params.get("extension_days")
        if days is not None and (not isinstance(days, int) or days < 1):
            errors.append("extension_days must be a positive integer")
        return errors

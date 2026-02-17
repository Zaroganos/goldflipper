"""
Max Hold Days GTD Method

Closes the position after N trading days from entry, regardless of P/L.
This is a simple time-based risk management method that prevents positions
from becoming stale or tying up capital for too long.

Params:
    max_days (int): Maximum number of calendar days to hold. Default: 5
"""

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("max_hold_days")
class MaxHoldDaysMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "max_hold_days"

    def evaluate(self, context: GTDContext) -> GTDResult:
        max_days = context.method_params.get("max_days", 5)

        if context.days_held is None:
            return GTDResult(action=GTDAction.HOLD, reason="No entry date available, cannot calculate days held")

        if context.days_held >= max_days:
            return GTDResult(
                action=GTDAction.CLOSE_NOW,
                reason=f"Position held {context.days_held} days, exceeds max of {max_days}",
                priority=50,
            )

        # Calculate the date we'd need to close by
        if context.entry_date is not None:
            from datetime import timedelta

            close_by = context.entry_date + timedelta(days=max_days)
            remaining = max_days - context.days_held
            return GTDResult(
                action=GTDAction.SHORTEN,
                recommended_date=close_by,
                reason=f"{remaining} days remaining of {max_days} max hold",
                priority=80,
            )

        return GTDResult(action=GTDAction.HOLD, reason="Within max hold period")

    def get_default_params(self):
        return {"max_days": 5}

    def get_param_schema(self):
        return {
            "max_days": {
                "type": "integer",
                "description": "Maximum calendar days to hold the position",
                "default": 5,
                "min": 1,
                "max": 365,
            }
        }

    def validate_config(self, params):
        errors = []
        max_days = params.get("max_days")
        if max_days is not None:
            if not isinstance(max_days, int) or max_days < 1:
                errors.append("max_days must be a positive integer")
        return errors

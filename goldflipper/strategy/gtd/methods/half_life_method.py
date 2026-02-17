"""
Half-Life GTD Method

Closes the position at the midpoint between entry date and option expiration.
This is a simple, deterministic method based on the principle that the second
half of an option's life has accelerating theta decay and diminishing
probability of reaching the target.

Params:
    fraction (float): Fraction of total time to hold (0.5 = half-life). Default: 0.5
"""

from datetime import timedelta

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("half_life_method")
class HalfLifeMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "half_life_method"

    def evaluate(self, context: GTDContext) -> GTDResult:
        fraction = context.method_params.get("fraction", 0.5)

        if context.entry_date is None or context.option_expiration_date is None:
            return GTDResult(action=GTDAction.HOLD, reason="Entry date or expiration date not available")

        total_days = (context.option_expiration_date - context.entry_date).days
        if total_days <= 0:
            return GTDResult(action=GTDAction.CLOSE_NOW, reason="Option already at or past expiration", priority=20)

        hold_days = int(total_days * fraction)
        close_by = context.entry_date + timedelta(days=hold_days)

        if context.current_date >= close_by:
            return GTDResult(
                action=GTDAction.CLOSE_NOW,
                reason=f"Past half-life: day {context.days_held} of {hold_days} ({fraction * 100:.0f}% of {total_days} total)",
                priority=65,
            )

        return GTDResult(
            action=GTDAction.SHORTEN,
            recommended_date=close_by,
            reason=f"Half-life at {close_by.strftime('%m/%d/%Y')} (day {hold_days} of {total_days})",
            priority=85,
        )

    def get_default_params(self):
        return {"fraction": 0.5}

    def get_param_schema(self):
        return {
            "fraction": {
                "type": "number",
                "description": "Fraction of entry-to-expiry to hold (0.5 = half-life, 0.33 = one-third)",
                "default": 0.5,
                "min": 0.1,
                "max": 0.9,
            }
        }

    def validate_config(self, params):
        errors = []
        f = params.get("fraction")
        if f is not None and (not isinstance(f, (int, float)) or f <= 0 or f >= 1):
            errors.append("fraction must be between 0 and 1 (exclusive)")
        return errors

"""
P/L Time Stop GTD Method

Closes the position if the take-profit target has not been reached within N days
of entry. This prevents capital from being tied up in positions that aren't
progressing toward the profit target.

Params:
    max_days_to_tp (int): Days allowed to reach TP before forcing close. Default: 3
"""

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("pl_time_stop")
class PLTimeStopMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "pl_time_stop"

    def evaluate(self, context: GTDContext) -> GTDResult:
        max_days = context.method_params.get("max_days_to_tp", 3)

        if context.days_held is None:
            return GTDResult(action=GTDAction.HOLD, reason="No entry date available")

        if context.days_held < max_days:
            return GTDResult(
                action=GTDAction.HOLD,
                reason=f"Day {context.days_held} of {max_days} allowed before time stop",
            )

        # Time limit reached — check if we're in profit
        if context.unrealized_pnl_pct is not None and context.unrealized_pnl_pct > 0:
            return GTDResult(
                action=GTDAction.HOLD,
                reason=f"Time stop reached ({context.days_held} days) but position is in profit ({context.unrealized_pnl_pct:.1f}%), holding",
            )

        if context.unrealized_pnl_pct is not None:
            reason = f"Time stop: {context.days_held} days held, TP not reached, P/L: {context.unrealized_pnl_pct:.1f}%"
        else:
            reason = f"Time stop: {context.days_held} days held, TP not reached"
        return GTDResult(action=GTDAction.CLOSE_NOW, reason=reason, priority=60)

    def get_default_params(self):
        return {"max_days_to_tp": 3}

    def get_param_schema(self):
        return {
            "max_days_to_tp": {
                "type": "integer",
                "description": "Days allowed to reach take-profit before closing",
                "default": 3,
                "min": 1,
                "max": 90,
            }
        }

    def validate_config(self, params):
        errors = []
        d = params.get("max_days_to_tp")
        if d is not None:
            if not isinstance(d, int) or d < 1:
                errors.append("max_days_to_tp must be a positive integer")
        return errors

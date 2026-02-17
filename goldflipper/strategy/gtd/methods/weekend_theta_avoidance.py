"""
Weekend Theta Avoidance GTD Method

Closes the position on Friday to avoid paying weekend theta decay (2 days of
time decay for no potential price movement during market closure).

Most relevant for short-DTE options where weekend theta is a significant
percentage of remaining premium.

Params:
    close_on_friday (bool): Whether to close on Friday. Default: True
    min_dte_for_concern (int): Only apply when DTE is below this. Default: 14
"""

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("weekend_theta_avoidance")
class WeekendThetaAvoidanceMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "weekend_theta_avoidance"

    def evaluate(self, context: GTDContext) -> GTDResult:
        close_on_friday = context.method_params.get("close_on_friday", True)
        min_dte = context.method_params.get("min_dte_for_concern", 14)

        if not close_on_friday:
            return GTDResult(action=GTDAction.HOLD, reason="Weekend theta avoidance disabled")

        # Only relevant for short-DTE options
        if context.days_to_expiry is not None and context.days_to_expiry > min_dte:
            return GTDResult(
                action=GTDAction.HOLD,
                reason=f"DTE {context.days_to_expiry} above concern threshold of {min_dte}",
            )

        # Check if today is Friday (weekday 4)
        if context.current_date.weekday() == 4:
            return GTDResult(
                action=GTDAction.CLOSE_NOW,
                reason=f"Friday close: avoiding weekend theta decay (DTE: {context.days_to_expiry})",
                priority=55,
            )

        # If today is Thursday, shorten to today so it doesn't hold through Friday close
        if context.current_date.weekday() == 3:
            from datetime import timedelta

            friday = context.current_date + timedelta(days=1)
            return GTDResult(
                action=GTDAction.SHORTEN,
                recommended_date=friday,
                reason=f"Shortening GTD to Friday to avoid weekend theta (DTE: {context.days_to_expiry})",
                priority=75,
            )

        return GTDResult(action=GTDAction.HOLD, reason="Not approaching weekend")

    def get_default_params(self):
        return {"close_on_friday": True, "min_dte_for_concern": 14}

    def get_param_schema(self):
        return {
            "close_on_friday": {
                "type": "boolean",
                "description": "Whether to close positions on Friday",
                "default": True,
            },
            "min_dte_for_concern": {
                "type": "integer",
                "description": "Only apply weekend avoidance when DTE is at or below this value",
                "default": 14,
                "min": 1,
                "max": 90,
            },
        }

    def validate_config(self, params):
        errors = []
        dte = params.get("min_dte_for_concern")
        if dte is not None and (not isinstance(dte, int) or dte < 1):
            errors.append("min_dte_for_concern must be a positive integer")
        return errors

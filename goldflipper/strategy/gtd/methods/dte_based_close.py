"""
DTE-Based Close GTD Method

Closes the position when the option reaches X days-to-expiration (DTE).
This avoids the zone of accelerating theta decay that occurs in the final
days before expiration.

Params:
    close_at_dte (int): Close when DTE reaches this number. Default: 7
"""

from datetime import timedelta

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("dte_based_close")
class DTEBasedCloseMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "dte_based_close"

    def evaluate(self, context: GTDContext) -> GTDResult:
        close_at_dte = context.method_params.get("close_at_dte", 7)

        if context.days_to_expiry is None:
            return GTDResult(action=GTDAction.HOLD, reason="Cannot determine DTE")

        if context.days_to_expiry <= close_at_dte:
            return GTDResult(
                action=GTDAction.CLOSE_NOW,
                reason=f"DTE is {context.days_to_expiry}, at or below threshold of {close_at_dte}",
                priority=40,
            )

        # Set effective date to close_at_dte days before option expiration
        if context.option_expiration_date is not None:
            close_by = context.option_expiration_date - timedelta(days=close_at_dte)
            return GTDResult(
                action=GTDAction.SHORTEN,
                recommended_date=close_by,
                reason=f"Will close at {close_at_dte} DTE ({close_by.strftime('%m/%d/%Y')})",
                priority=70,
            )

        return GTDResult(action=GTDAction.HOLD, reason=f"DTE is {context.days_to_expiry}, above threshold of {close_at_dte}")

    def get_default_params(self):
        return {"close_at_dte": 7}

    def get_param_schema(self):
        return {
            "close_at_dte": {
                "type": "integer",
                "description": "Close position when DTE reaches this value",
                "default": 7,
                "min": 0,
                "max": 90,
            }
        }

    def validate_config(self, params):
        errors = []
        dte = params.get("close_at_dte")
        if dte is not None:
            if not isinstance(dte, int) or dte < 0:
                errors.append("close_at_dte must be a non-negative integer")
        return errors

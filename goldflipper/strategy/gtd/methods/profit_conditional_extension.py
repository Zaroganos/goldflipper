"""
Profit-Conditional Extension GTD Method

Extends the effective GTD date if the position is currently in profit.
This is the only method that can EXTEND the GTD beyond the original
play_expiration_date, but it is always capped at the option expiration date.

The rationale: if a trade is working, give it more time to reach TP.

Params:
    min_profit_pct (float): Minimum unrealized P/L % to trigger extension. Default: 10.0
    extension_days (int): Number of days to extend. Default: 3
"""

from datetime import timedelta

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("profit_conditional_extension")
class ProfitConditionalExtensionMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "profit_conditional_extension"

    def evaluate(self, context: GTDContext) -> GTDResult:
        min_profit_pct = context.method_params.get("min_profit_pct", 10.0)
        extension_days = context.method_params.get("extension_days", 3)

        if context.unrealized_pnl_pct is None:
            return GTDResult(action=GTDAction.HOLD, reason="P/L not available for profit-conditional extension")

        if context.unrealized_pnl_pct < min_profit_pct:
            return GTDResult(
                action=GTDAction.HOLD,
                reason=f"P/L {context.unrealized_pnl_pct:.1f}% below {min_profit_pct}% threshold for extension",
            )

        # Calculate extended date from current effective date or play expiration
        base_date = context.current_effective_date or context.play_expiration_date
        if base_date is None:
            return GTDResult(action=GTDAction.HOLD, reason="No base date available for extension")

        extended_date = base_date + timedelta(days=extension_days)

        # Cap at option expiration (enforced by evaluator too, but be explicit)
        if context.option_expiration_date is not None and extended_date > context.option_expiration_date:
            extended_date = context.option_expiration_date

        return GTDResult(
            action=GTDAction.EXTEND,
            recommended_date=extended_date,
            reason=(
                f"Position in profit ({context.unrealized_pnl_pct:.1f}%), "
                f"extending GTD by {extension_days} days to {extended_date.strftime('%m/%d/%Y')}"
            ),
            priority=90,
        )

    def get_default_params(self):
        return {"min_profit_pct": 10.0, "extension_days": 3}

    def get_param_schema(self):
        return {
            "min_profit_pct": {
                "type": "number",
                "description": "Minimum unrealized P/L percentage to trigger extension",
                "default": 10.0,
                "min": 0.0,
                "max": 100.0,
            },
            "extension_days": {
                "type": "integer",
                "description": "Number of calendar days to extend the GTD",
                "default": 3,
                "min": 1,
                "max": 30,
            },
        }

    def requires_market_data(self) -> bool:
        return True

    def validate_config(self, params):
        errors = []
        pct = params.get("min_profit_pct")
        if pct is not None and (not isinstance(pct, (int, float)) or pct < 0):
            errors.append("min_profit_pct must be non-negative")
        days = params.get("extension_days")
        if days is not None and (not isinstance(days, int) or days < 1):
            errors.append("extension_days must be a positive integer")
        return errors

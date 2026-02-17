"""
Loss-Conditional Shortening GTD Method

Shortens the effective GTD date when the position is losing money.
The worse the loss, the more urgently the GTD is shortened, preventing
extended exposure to a deteriorating position.

Params:
    loss_threshold_pct (float): P/L % below which to start shortening. Default: -10.0
    shorten_days (int): Days to shorten the GTD. Default: 2
"""

from datetime import timedelta

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("loss_conditional_shortening")
class LossConditionalShorteningMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "loss_conditional_shortening"

    def evaluate(self, context: GTDContext) -> GTDResult:
        loss_threshold_pct = context.method_params.get("loss_threshold_pct", -10.0)
        shorten_days = context.method_params.get("shorten_days", 2)

        if context.unrealized_pnl_pct is None:
            return GTDResult(action=GTDAction.HOLD, reason="P/L not available for loss-conditional shortening")

        if context.unrealized_pnl_pct > loss_threshold_pct:
            return GTDResult(
                action=GTDAction.HOLD,
                reason=f"P/L {context.unrealized_pnl_pct:.1f}% above loss threshold of {loss_threshold_pct}%",
            )

        # Position is losing beyond threshold — shorten
        base_date = context.current_effective_date or context.play_expiration_date
        if base_date is None:
            return GTDResult(action=GTDAction.HOLD, reason="No base date available for shortening")

        shortened_date = base_date - timedelta(days=shorten_days)

        # Don't shorten to before today
        if shortened_date <= context.current_date:
            return GTDResult(
                action=GTDAction.CLOSE_NOW,
                reason=f"Loss shortening would close before today: P/L {context.unrealized_pnl_pct:.1f}%",
                priority=55,
            )

        return GTDResult(
            action=GTDAction.SHORTEN,
            recommended_date=shortened_date,
            reason=(
                f"Position losing ({context.unrealized_pnl_pct:.1f}%), shortening GTD by {shorten_days} days to {shortened_date.strftime('%m/%d/%Y')}"
            ),
            priority=70,
        )

    def get_default_params(self):
        return {"loss_threshold_pct": -10.0, "shorten_days": 2}

    def get_param_schema(self):
        return {
            "loss_threshold_pct": {
                "type": "number",
                "description": "Unrealized P/L percentage threshold to trigger shortening (negative value)",
                "default": -10.0,
                "min": -100.0,
                "max": 0.0,
            },
            "shorten_days": {
                "type": "integer",
                "description": "Number of calendar days to shorten the GTD",
                "default": 2,
                "min": 1,
                "max": 30,
            },
        }

    def requires_market_data(self) -> bool:
        return True

    def validate_config(self, params):
        errors = []
        pct = params.get("loss_threshold_pct")
        if pct is not None and (not isinstance(pct, (int, float)) or pct > 0):
            errors.append("loss_threshold_pct must be zero or negative")
        days = params.get("shorten_days")
        if days is not None and (not isinstance(days, int) or days < 1):
            errors.append("shorten_days must be a positive integer")
        return errors

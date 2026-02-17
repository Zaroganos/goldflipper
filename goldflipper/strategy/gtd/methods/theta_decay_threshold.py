"""
Theta Decay Threshold GTD Method

Closes the position when daily theta exceeds a threshold percentage of the
position's current value. This prevents holding through periods of excessive
time decay that erode the position faster than potential price appreciation.

Params:
    max_theta_pct (float): Max daily theta as % of position value. Default: 2.0
"""

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("theta_decay_threshold")
class ThetaDecayThresholdMethod(DynamicGTDMethod):
    def get_name(self) -> str:
        return "theta_decay_threshold"

    def evaluate(self, context: GTDContext) -> GTDResult:
        max_theta_pct = context.method_params.get("max_theta_pct", 2.0)

        theta = context.greeks.get("theta")
        if theta is None:
            return GTDResult(action=GTDAction.HOLD, reason="Theta not available")

        if context.current_premium is None or context.current_premium <= 0:
            return GTDResult(action=GTDAction.HOLD, reason="Current premium not available")

        # Theta is typically negative for long positions; use absolute value
        abs_theta = abs(theta)
        theta_pct_of_value = (abs_theta / context.current_premium) * 100

        if theta_pct_of_value >= max_theta_pct:
            return GTDResult(
                action=GTDAction.CLOSE_NOW,
                reason=f"Daily theta is {theta_pct_of_value:.1f}% of premium, exceeds {max_theta_pct}% threshold",
                priority=45,
                metadata={"theta": theta, "theta_pct": theta_pct_of_value},
            )

        return GTDResult(
            action=GTDAction.HOLD,
            reason=f"Theta is {theta_pct_of_value:.1f}% of premium, below {max_theta_pct}% threshold",
        )

    def get_default_params(self):
        return {"max_theta_pct": 2.0}

    def get_param_schema(self):
        return {
            "max_theta_pct": {
                "type": "number",
                "description": "Max daily theta as percentage of position value before closing",
                "default": 2.0,
                "min": 0.1,
                "max": 50.0,
            }
        }

    def requires_market_data(self) -> bool:
        return True

    def validate_config(self, params):
        errors = []
        pct = params.get("max_theta_pct")
        if pct is not None:
            if not isinstance(pct, (int, float)) or pct <= 0:
                errors.append("max_theta_pct must be a positive number")
        return errors

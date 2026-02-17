"""
IV Crush Prevention GTD Method

Closes or shortens the position when implied volatility is expected to drop
significantly (IV crush). Common before/after earnings, major events, or
when IV rank is extremely elevated.

Params:
    max_iv_rank (float): Close when IV rank exceeds this (0-100 scale). Default: 80.0
    close_if_iv_dropping (bool): Close if current IV < previous cycle IV. Default: False

Note: This method requires greeks/IV data from the market data provider.
      Currently uses vega as a proxy for IV sensitivity. Full IV rank integration
      is a future enhancement.
"""

from typing import Any

from goldflipper.strategy.gtd.base import DynamicGTDMethod, GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import register_gtd_method


@register_gtd_method("iv_crush_prevention")
class IVCrushPreventionMethod(DynamicGTDMethod):
    def __init__(self):
        self._prev_vega: float | None = None

    def get_name(self) -> str:
        return "iv_crush_prevention"

    def evaluate(self, context: GTDContext) -> GTDResult:
        _max_iv_rank = context.method_params.get("max_iv_rank", 80.0)  # Reserved for future IV rank integration
        close_if_dropping = context.method_params.get("close_if_iv_dropping", False)

        vega = context.greeks.get("vega")
        if vega is None:
            return GTDResult(action=GTDAction.HOLD, reason="Vega/IV data not available")

        # Check if IV is dropping cycle-over-cycle (using vega as proxy)
        if close_if_dropping and self._prev_vega is not None:
            if vega < self._prev_vega * 0.9:  # 10% drop in vega suggests IV compression
                self._prev_vega = vega
                return GTDResult(
                    action=GTDAction.CLOSE_NOW,
                    reason=f"IV crush detected: vega dropped from {self._prev_vega:.4f} to {vega:.4f}",
                    priority=35,
                    metadata={"vega": vega, "prev_vega": self._prev_vega},
                )

        self._prev_vega = vega

        # Stub: IV rank check would go here with proper IV rank data source
        # For now, this is a placeholder that always holds
        return GTDResult(
            action=GTDAction.HOLD,
            reason=f"IV crush prevention: vega={vega:.4f}, monitoring",
        )

    def get_state(self) -> dict[str, Any]:
        return {"prev_vega": self._prev_vega}

    def load_state(self, state: dict[str, Any]) -> None:
        self._prev_vega = state.get("prev_vega")

    def get_default_params(self):
        return {"max_iv_rank": 80.0, "close_if_iv_dropping": False}

    def get_param_schema(self):
        return {
            "max_iv_rank": {
                "type": "number",
                "description": "Close when IV rank exceeds this value (0-100)",
                "default": 80.0,
                "min": 0.0,
                "max": 100.0,
            },
            "close_if_iv_dropping": {
                "type": "boolean",
                "description": "Close if IV is dropping significantly between cycles",
                "default": False,
            },
        }

    def requires_market_data(self) -> bool:
        return True

    def validate_config(self, params):
        errors = []
        rank = params.get("max_iv_rank")
        if rank is not None and (not isinstance(rank, (int, float)) or rank < 0 or rank > 100):
            errors.append("max_iv_rank must be between 0 and 100")
        return errors

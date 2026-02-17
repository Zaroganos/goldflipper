"""
Dynamic GTD (Good-Til-Date) Framework

Provides dynamic adjustment of play expiration dates based on configurable
methods. This is an overlay on top of the static play_expiration_date field.

Submodules:
    base: Core ABC, enums, and data structures
    registry: Method registration and discovery
    evaluator: Method execution and conflict resolution
    methods/: Individual GTD method implementations

Usage:
    from goldflipper.strategy.gtd import GTDEvaluator, GTDAction, GTDResult

    evaluator = GTDEvaluator(market_data=market_data_manager)
    result = evaluator.evaluate_play(play)

    if result['should_close']:
        # Trigger immediate close
    elif result['effective_date_changed']:
        play['dynamic_gtd']['effective_date'] = result['effective_date']
"""

from goldflipper.strategy.gtd.base import (
    DynamicGTDMethod,
    GTDAction,
    GTDContext,
    GTDResult,
)
from goldflipper.strategy.gtd.evaluator import GTDEvaluator
from goldflipper.strategy.gtd.registry import (
    GTDRegistry,
    register_gtd_method,
)

__all__ = [
    # Base classes and data structures
    "DynamicGTDMethod",
    "GTDAction",
    "GTDContext",
    "GTDResult",
    # Registry
    "GTDRegistry",
    "register_gtd_method",
    # Evaluator
    "GTDEvaluator",
]

"""
Strategy Runners for Goldflipper

This package contains individual strategy implementations. Each strategy
is a subclass of BaseStrategy and registers itself using the @register_strategy
decorator.

Available Strategies:
    option_swings: Manual option swing trading (current/default)
    option_swings_auto: Automated option swing trading
    momentum: Momentum-based trading
    sell_puts: Cash-secured put selling (Tasty Trade style)
    spreads: Options spreads strategies

Usage:
    Strategies are automatically discovered by the StrategyRegistry when
    the orchestrator initializes. To create a new strategy:

    1. Create a new module in this package (e.g., my_strategy.py)
    2. Implement a class extending BaseStrategy
    3. Decorate with @register_strategy('my_strategy')
    4. Add config section to settings.yaml with enabled: true/false

Example:
    # In my_strategy.py
    from goldflipper.strategy.base import BaseStrategy
    from goldflipper.strategy.registry import register_strategy

    @register_strategy('my_strategy')
    class MyStrategy(BaseStrategy):
        def get_name(self) -> str:
            return "my_strategy"

        def get_config_section(self) -> str:
            return "my_strategy"

        # ... implement other required methods
"""

# Runners are imported dynamically by StrategyRegistry.discover()
# Do not add static imports here to avoid circular dependencies

"""
Strategy Registry Module for Goldflipper Multi-Strategy System

This module provides strategy registration, discovery, and lookup functionality.
Strategies register themselves using the @register_strategy decorator, and the
orchestrator uses the registry to find and instantiate enabled strategies.

Usage:
    # Registering a strategy (in strategy module)
    from goldflipper.strategy.registry import register_strategy

    @register_strategy('my_strategy')
    class MyStrategy(BaseStrategy):
        ...

    # Looking up strategies (in orchestrator)
    from goldflipper.strategy.registry import StrategyRegistry

    registry = StrategyRegistry()
    registry.discover()  # Auto-discover strategy modules

    for strategy_class in registry.get_all_strategies():
        strategy = strategy_class(config, market_data, client)
        if strategy.is_enabled():
            # use strategy
"""

import importlib
import logging
from collections.abc import Callable
from typing import Any

# Forward reference - actual import happens at runtime
# to avoid circular imports
BaseStrategy = Any  # Will be goldflipper.strategy.base.BaseStrategy


class StrategyRegistry:
    """
    Registry for discovering and managing strategy implementations.

    The registry maintains a mapping of strategy names to their implementing
    classes. Strategies register themselves using the @register_strategy
    decorator when their module is imported.

    Attributes:
        _strategies (Dict[str, Type]): Class-level mapping of names to classes
        _discovered (bool): Whether auto-discovery has run

    Example:
        registry = StrategyRegistry()
        registry.discover()

        for name, cls in registry.get_all_strategies_with_names():
            print(f"Found strategy: {name}")
    """

    # Class-level storage - shared across all instances (singleton pattern)
    _strategies: dict[str, type] = {}
    _discovered: bool = False
    _logger: logging.Logger | None = None

    def __init__(self):
        """Initialize registry instance."""
        if StrategyRegistry._logger is None:
            StrategyRegistry._logger = logging.getLogger(__name__)

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        if StrategyRegistry._logger is None:
            StrategyRegistry._logger = logging.getLogger(__name__)
        return StrategyRegistry._logger

    # =========================================================================
    # Registration Methods
    # =========================================================================

    @classmethod
    def register(cls, name: str, strategy_class: type) -> None:
        """
        Register a strategy class with the given name.

        Args:
            name: Unique strategy identifier
            strategy_class: Class implementing BaseStrategy

        Raises:
            ValueError: If a strategy with this name is already registered
        """
        if name in cls._strategies:
            existing = cls._strategies[name]
            if existing is not strategy_class:
                # Allow re-registration of same class (module reload)
                raise ValueError(f"Strategy '{name}' is already registered (existing: {existing.__name__}, new: {strategy_class.__name__})")
            return

        cls._strategies[name] = strategy_class

        logger = logging.getLogger(__name__)
        logger.debug(f"Registered strategy: {name} -> {strategy_class.__name__}")

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister a strategy by name.

        Args:
            name: Strategy identifier to remove

        Returns:
            bool: True if strategy was removed, False if not found
        """
        if name in cls._strategies:
            del cls._strategies[name]
            logging.getLogger(__name__).debug(f"Unregistered strategy: {name}")
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered strategies.

        Primarily used for testing.
        """
        cls._strategies.clear()
        cls._discovered = False
        logging.getLogger(__name__).debug("Cleared all registered strategies")

    # =========================================================================
    # Lookup Methods
    # =========================================================================

    @classmethod
    def get(cls, name: str) -> type | None:
        """
        Get a strategy class by name.

        Args:
            name: Strategy identifier

        Returns:
            Strategy class or None if not found
        """
        return cls._strategies.get(name)

    @classmethod
    def get_all_strategies(cls) -> list[type]:
        """
        Get all registered strategy classes.

        Returns:
            List of strategy classes
        """
        return list(cls._strategies.values())

    @classmethod
    def get_all_strategy_names(cls) -> list[str]:
        """
        Get all registered strategy names.

        Returns:
            List of strategy names
        """
        return list(cls._strategies.keys())

    @classmethod
    def get_all_strategies_with_names(cls) -> list[tuple]:
        """
        Get all strategies with their names.

        Returns:
            List of (name, strategy_class) tuples
        """
        return list(cls._strategies.items())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a strategy is registered.

        Args:
            name: Strategy identifier

        Returns:
            bool: True if registered
        """
        return name in cls._strategies

    @classmethod
    def count(cls) -> int:
        """
        Get count of registered strategies.

        Returns:
            int: Number of registered strategies
        """
        return len(cls._strategies)

    # =========================================================================
    # Discovery Methods
    # =========================================================================

    @classmethod
    def discover(cls, force: bool = False) -> int:
        """
        Auto-discover strategies in the runners package.

        Imports all known runner modules, which triggers their @register_strategy
        decorators to execute and register the strategies.

        Args:
            force: If True, re-run discovery even if already done

        Returns:
            int: Number of strategies discovered
        """
        if cls._discovered and not force:
            return cls.count()

        logger = logging.getLogger(__name__)
        logger.info("Discovering strategy modules...")

        runners_package = "goldflipper.strategy.runners"

        # Known runner modules - add new strategies here
        runner_modules = [
            "option_swings",
            "option_swings_auto",
            "momentum",
            "sell_puts",
            "spreads",
        ]

        discovered_count = 0

        for module_name in runner_modules:
            full_module = f"{runners_package}.{module_name}"
            try:
                importlib.import_module(full_module)
                logger.debug(f"Loaded strategy module: {module_name}")
                discovered_count += 1
            except ImportError as e:
                # Module doesn't exist yet - this is fine during development
                logger.debug(f"Strategy module not found (expected during dev): {module_name} - {e}")
            except Exception as e:
                logger.error(f"Error loading strategy module {module_name}: {e}")

        cls._discovered = True
        logger.info(f"Strategy discovery complete: {cls.count()} strategies registered")

        return cls.count()

    @classmethod
    def discover_from_config(cls, config: dict[str, Any]) -> int:
        """
        Discover strategies based on configuration.

        Only loads modules for strategies that are enabled in config.

        Args:
            config: Application configuration dictionary

        Returns:
            int: Number of strategies discovered
        """
        logger = logging.getLogger(__name__)

        # Strategy name -> module mapping
        strategy_modules = {
            "option_swings": "option_swings",
            "option_swings_auto": "option_swings_auto",
            "momentum": "momentum",
            "sell_puts": "sell_puts",
            "spreads": "spreads",
        }

        # Config section -> strategy name mapping
        config_to_strategy = {
            "options_swings": "option_swings",
            "option_swings_auto": "option_swings_auto",
            "momentum": "momentum",
            "sell_puts": "sell_puts",
            "spreads": "spreads",
        }

        runners_package = "goldflipper.strategy.runners"

        for config_section, strategy_name in config_to_strategy.items():
            section = config.get(config_section, {})

            if section.get("enabled", False):
                module_name = strategy_modules.get(strategy_name)
                if module_name:
                    full_module = f"{runners_package}.{module_name}"
                    try:
                        importlib.import_module(full_module)
                        logger.debug(f"Loaded enabled strategy: {strategy_name}")
                    except ImportError as e:
                        logger.warning(f"Could not load strategy module {module_name}: {e}")
                    except Exception as e:
                        logger.error(f"Error loading strategy {strategy_name}: {e}")

        return cls.count()


def register_strategy(name: str) -> Callable[[type], type]:
    """
    Decorator to register a strategy class with the registry.

    Use this decorator on strategy classes to automatically register them
    when their module is imported.

    Args:
        name: Unique strategy identifier

    Returns:
        Decorator function

    Example:
        @register_strategy('my_strategy')
        class MyStrategy(BaseStrategy):
            def get_name(self) -> str:
                return "my_strategy"
            # ... implement other methods

    Note:
        The decorated class must implement BaseStrategy interface.
        The name should match what get_name() returns.
    """

    def decorator(cls: type) -> type:
        StrategyRegistry.register(name, cls)
        return cls

    return decorator


# Convenience function for manual registration
def register(name: str, strategy_class: type) -> None:
    """
    Manually register a strategy class.

    Alternative to using the @register_strategy decorator.

    Args:
        name: Unique strategy identifier
        strategy_class: Class implementing BaseStrategy
    """
    StrategyRegistry.register(name, strategy_class)

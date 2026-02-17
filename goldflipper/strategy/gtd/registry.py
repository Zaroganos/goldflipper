"""
GTD Method Registry

Provides registration, discovery, and instantiation of Dynamic GTD methods.
Follows the same pattern as the strategy registry (@register_strategy decorator).

Usage:
    from goldflipper.strategy.gtd.registry import GTDRegistry, register_gtd_method

    @register_gtd_method('my_method')
    class MyMethod(DynamicGTDMethod):
        ...

    # Lookup
    registry = GTDRegistry()
    registry.discover()
    method_cls = registry.get('my_method')
"""

import importlib
import logging
from collections.abc import Callable

from goldflipper.strategy.gtd.base import DynamicGTDMethod

logger = logging.getLogger(__name__)


class GTDRegistry:
    """Registry for Dynamic GTD method implementations.

    Class-level storage (singleton pattern) shared across all instances,
    mirroring StrategyRegistry's design.
    """

    _methods: dict[str, type[DynamicGTDMethod]] = {}
    _discovered: bool = False

    @classmethod
    def register(cls, name: str, method_class: type[DynamicGTDMethod]) -> None:
        """Register a GTD method class.

        Args:
            name: Unique method identifier
            method_class: Class implementing DynamicGTDMethod

        Raises:
            ValueError: If a different class is already registered with this name
        """
        if name in cls._methods:
            existing = cls._methods[name]
            if existing is not method_class:
                raise ValueError(f"GTD method '{name}' is already registered (existing: {existing.__name__}, new: {method_class.__name__})")
            return

        cls._methods[name] = method_class
        logger.debug(f"Registered GTD method: {name} -> {method_class.__name__}")

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a GTD method by name."""
        if name in cls._methods:
            del cls._methods[name]
            logger.debug(f"Unregistered GTD method: {name}")
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """Clear all registered methods. Primarily for testing."""
        cls._methods.clear()
        cls._discovered = False

    @classmethod
    def get(cls, name: str) -> type[DynamicGTDMethod] | None:
        """Get a GTD method class by name."""
        return cls._methods.get(name)

    @classmethod
    def get_all(cls) -> dict[str, type[DynamicGTDMethod]]:
        """Get all registered method classes."""
        return dict(cls._methods)

    @classmethod
    def get_all_names(cls) -> list[str]:
        """Get all registered method names."""
        return list(cls._methods.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a method is registered."""
        return name in cls._methods

    @classmethod
    def count(cls) -> int:
        """Get count of registered methods."""
        return len(cls._methods)

    @classmethod
    def create(cls, name: str) -> DynamicGTDMethod | None:
        """Instantiate a registered GTD method by name.

        Args:
            name: Method identifier

        Returns:
            Instance of the method, or None if not found
        """
        method_class = cls.get(name)
        if method_class is None:
            logger.warning(f"GTD method not found: {name}")
            return None
        try:
            return method_class()
        except Exception as e:
            logger.error(f"Error instantiating GTD method '{name}': {e}")
            return None

    @classmethod
    def discover(cls, force: bool = False) -> int:
        """Auto-discover GTD methods in the methods package.

        Imports all known method modules, triggering their @register_gtd_method
        decorators.

        Args:
            force: If True, re-run discovery even if already done

        Returns:
            Number of methods registered after discovery
        """
        if cls._discovered and not force:
            return cls.count()

        logger.info("Discovering GTD method modules...")

        methods_package = "goldflipper.strategy.gtd.methods"

        method_modules = [
            "max_hold_days",
            "dte_based_close",
            "theta_decay_threshold",
            "pl_time_stop",
            "profit_conditional_extension",
            "loss_conditional_shortening",
            "rolling_gtd",
            "earnings_event_based",
            "weekend_theta_avoidance",
            "iv_crush_prevention",
            "half_life_method",
        ]

        for module_name in method_modules:
            full_module = f"{methods_package}.{module_name}"
            try:
                importlib.import_module(full_module)
                logger.debug(f"Loaded GTD method module: {module_name}")
            except ImportError as e:
                logger.debug(f"GTD method module not found (expected during dev): {module_name} - {e}")
            except Exception as e:
                logger.error(f"Error loading GTD method module {module_name}: {e}")

        cls._discovered = True
        logger.info(f"GTD method discovery complete: {cls.count()} methods registered")
        return cls.count()


def register_gtd_method(name: str) -> Callable[[type[DynamicGTDMethod]], type[DynamicGTDMethod]]:
    """Decorator to register a GTD method class with the registry.

    Args:
        name: Unique method identifier

    Returns:
        Decorator function

    Example:
        @register_gtd_method('max_hold_days')
        class MaxHoldDaysMethod(DynamicGTDMethod):
            def get_name(self) -> str:
                return "max_hold_days"
    """

    def decorator(cls: type[DynamicGTDMethod]) -> type[DynamicGTDMethod]:
        GTDRegistry.register(name, cls)
        return cls

    return decorator

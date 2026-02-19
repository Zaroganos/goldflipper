"""
Shared Strategy Utilities for Goldflipper

This package contains utility modules shared across all trading strategies.
These modules are extracted from core.py to provide reusable components.

Modules:
    play_manager: Play file operations (move, save, load)
    order_executor: Order placement and execution
    evaluation: TP/SL evaluation helpers and calculations

Usage:
    # Import play management utilities
    from goldflipper.strategy.shared import (
        PlayManager,
        save_play,
        move_play_to_open,
        move_play_to_closed
    )

    # Import evaluation utilities
    from goldflipper.strategy.shared import (
        evaluate_opening_strategy,
        evaluate_closing_strategy,
        calculate_and_store_price_levels,
        calculate_and_store_premium_levels
    )

    # Import order execution utilities
    from goldflipper.strategy.shared import (
        OrderExecutor,
        get_option_contract
    )

Note:
    During migration, these modules provide both a class-based interface
    and standalone functions for backward compatibility with core.py.
    Once migration is complete, core.py functions will be thin wrappers
    that call these shared modules.
"""

# Play Manager exports
# Evaluation exports
from goldflipper.strategy.shared.evaluation import (
    # Dynamic GTD convenience function
    apply_dynamic_gtd,
    calculate_and_store_premium_levels,
    # Price level calculations
    calculate_and_store_price_levels,
    evaluate_closing_strategy,
    # Opening/closing strategy evaluation
    evaluate_opening_strategy,
)

# Order Executor exports
from goldflipper.strategy.shared.order_executor import (
    # Class
    OrderExecutor,
    # Price determination helpers
    determine_limit_price,
    get_entry_premium,
    # Standalone functions (backward compatible)
    get_option_contract,
    get_order_side_for_entry,
    get_order_side_for_exit,
    # Order action helpers (trade direction support)
    order_action_to_side,
)
from goldflipper.strategy.shared.play_manager import (
    # Class
    PlayManager,
    PlayStatus,
    UUIDEncoder,
    move_play_to_closed,
    move_play_to_expired,
    move_play_to_new,
    move_play_to_open,
    move_play_to_pending_closing,
    move_play_to_pending_opening,
    move_play_to_temp,
    # Standalone functions (backward compatible)
    save_play,
    save_play_improved,
)

__all__ = [
    # Play Manager
    "PlayManager",
    "PlayStatus",
    "UUIDEncoder",
    "save_play",
    "save_play_improved",
    "move_play_to_new",
    "move_play_to_pending_opening",
    "move_play_to_open",
    "move_play_to_pending_closing",
    "move_play_to_closed",
    "move_play_to_expired",
    "move_play_to_temp",
    # Evaluation
    "evaluate_opening_strategy",
    "evaluate_closing_strategy",
    "calculate_and_store_price_levels",
    "calculate_and_store_premium_levels",
    "apply_dynamic_gtd",
    # Order Executor
    "OrderExecutor",
    "order_action_to_side",
    "get_order_side_for_entry",
    "get_order_side_for_exit",
    "determine_limit_price",
    "get_entry_premium",
    "get_option_contract",
]

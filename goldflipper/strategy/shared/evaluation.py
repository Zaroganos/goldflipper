"""
Strategy Evaluation Module for Goldflipper Multi-Strategy System

This module provides centralized evaluation logic for trading strategies:
- Opening condition evaluation (entry triggers)
- Closing condition evaluation (TP/SL triggers)
- Price level calculations for percentage-based targets
- Dynamic TP/SL support (stub for future implementations)

The module extracts and consolidates evaluation functions from core.py,
maintaining backward compatibility while enabling strategy-specific handling.

Usage:
    from goldflipper.strategy.shared.evaluation import (
        evaluate_opening_strategy,
        evaluate_closing_strategy,
        calculate_and_store_price_levels,
        calculate_and_store_premium_levels,
        apply_dynamic_targets  # Stub for future dynamic TP/SL methods
    )

    # Check if entry conditions are met
    if evaluate_opening_strategy(symbol, play):
        open_position(play, play_file)

    # Check if exit conditions are met
    close_conditions = evaluate_closing_strategy(symbol, play, play_file)
    if close_conditions['should_close']:
        close_position(play, close_conditions, play_file)
"""

import logging
from collections.abc import Callable
from typing import Any

from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display

SavePlayFn = Callable[[dict[str, Any], str], bool | None]
GetStockPriceFn = Callable[[str], float | None]
GetOptionDataFn = Callable[[str], dict[str, Any] | None]


# ==================================================
# Dynamic TP/SL Calculations (Stub for Future Methods)
# ==================================================


def apply_dynamic_gtd(
    play: dict[str, Any],
    market_data: Any | None = None,
    play_file: str | None = None,
    save_play_fn: SavePlayFn | None = None,
) -> dict[str, Any]:
    """
    Convenience function to evaluate Dynamic GTD methods for a play.

    Wraps GTDEvaluator.evaluate_play() for use by any strategy or module.
    If the effective date changes, it updates the play dict in-place and
    optionally persists to disk.

    Args:
        play: Play data dictionary (may be modified in-place if effective date changes)
        market_data: MarketDataManager instance (optional, some methods don't need it)
        play_file: Path to play file for persistence (optional)
        save_play_fn: Function to save the play (optional, defaults to save_play_improved)

    Returns:
        Dict with evaluation results:
            - should_close (bool): Whether to close the position immediately
            - close_reason (str): Reason for closing
            - effective_date (str|None): New effective date in MM/DD/YYYY
            - effective_date_changed (bool): Whether effective date was modified
            - is_gtd_exit (bool): True if this is a GTD-triggered exit
            - method_results (list): Individual method results

    Example:
        result = apply_dynamic_gtd(play, market_data=md, play_file=filepath)
        if result['should_close']:
            close_position(play, {'is_gtd_exit': True}, play_file)
    """
    gtd_config = play.get("dynamic_gtd", {})
    if not gtd_config.get("enabled", False):
        return {
            "should_close": False,
            "close_reason": "",
            "effective_date": None,
            "effective_date_changed": False,
            "is_gtd_exit": False,
            "method_results": [],
        }

    try:
        from goldflipper.strategy.gtd import GTDEvaluator

        evaluator = GTDEvaluator(market_data=market_data)
        result = evaluator.evaluate_play(play)

        # Persist effective date change
        if result.get("effective_date_changed", False) and result.get("effective_date"):
            play["dynamic_gtd"]["effective_date"] = result["effective_date"]
            if play_file:
                if save_play_fn is None:
                    from goldflipper.strategy.shared.play_manager import save_play_improved

                    save_play_fn = save_play_improved
                if save_play_fn is not None:
                    try:
                        save_play_fn(play, play_file)
                    except Exception as e:
                        logging.warning(f"Failed to persist GTD effective date: {e}")

        return result

    except Exception as e:
        logging.error(f"Error in apply_dynamic_gtd: {e}")
        return {
            "should_close": False,
            "close_reason": "",
            "effective_date": None,
            "effective_date_changed": False,
            "is_gtd_exit": False,
            "method_results": [],
        }


def apply_dynamic_targets(play: dict[str, Any]) -> bool:
    """
    Apply dynamic TP/SL target adjustments to a play.

    This is a STUB for future dynamic pricing methods. Dynamic TP/SL allows
    targets to be recalculated based on various factors such as:
    - Time decay (theta)
    - Implied volatility changes
    - Market regime shifts
    - Entry timing relative to play creation
    - Custom model outputs

    The framework distinguishes between:
    - STATIC: Fixed TP/SL levels calculated once at play creation
    - DYNAMIC: TP/SL levels that can be recalculated based on configured methods

    Args:
        play: Play data dictionary (modified in place)

    Returns:
        True if adjustments were applied, False otherwise

    Note:
        Currently returns False as no dynamic methods are implemented.
        Future implementations will check play['take_profit']['TP_type'] == 'DYNAMIC'
        and play['stop_loss']['SL_type'] == 'DYNAMIC', then apply the configured
        dynamic_method (e.g., 'time_decay', 'iv_adjusted', 'model_v1', etc.).
    """
    take_profit = play.get("take_profit", {})
    stop_loss = play.get("stop_loss", {})

    # Check if dynamic TP/SL is enabled
    tp_is_dynamic = take_profit.get("TP_type") == "DYNAMIC"
    sl_is_dynamic = stop_loss.get("SL_type") == "DYNAMIC"

    if not tp_is_dynamic and not sl_is_dynamic:
        return False

    # Get dynamic method (stub - no methods implemented yet)
    dynamic_method = take_profit.get("dynamic_method") or stop_loss.get("dynamic_method")

    if dynamic_method:
        logging.info(f"Dynamic TP/SL requested with method '{dynamic_method}' - not yet implemented")
    else:
        logging.info("Dynamic TP/SL enabled but no method specified - using static targets")

    # Future: Implement dynamic methods here
    # Example structure:
    # if dynamic_method == 'time_decay':
    #     return _apply_time_decay_adjustment(play)
    # elif dynamic_method == 'iv_adjusted':
    #     return _apply_iv_adjustment(play)
    # elif dynamic_method == 'model_v1':
    #     return _apply_model_v1(play)

    # Currently no methods implemented - return False
    return False


# ==================================================
# Price Level Calculations
# ==================================================


def calculate_and_store_price_levels(play: dict[str, Any], entry_stock_price: float) -> None:
    """
    Calculate and store TP/SL stock price levels in the play data.

    This function calculates target prices for percentage-based TP/SL settings
    and stores them in the play dictionary for future evaluation.

    Args:
        play: Play data dictionary (modified in place)
        entry_stock_price: Stock price at entry time

    Side Effects:
        Updates play dictionary with:
        - entry_point.entry_stock_price
        - take_profit.TP_stock_price_target (if stock_price_pct set)
        - stop_loss.SL_stock_price_target (if stock_price_pct set)
        - stop_loss.contingency_SL_stock_price_target (if contingency_stock_price_pct set)
    """
    # Convert entry_stock_price to float if it's a Series
    entry_price_item = getattr(entry_stock_price, "item", None)
    if callable(entry_price_item):
        raw_entry_price = entry_price_item()
        if isinstance(raw_entry_price, (int, float, str)):
            entry_stock_price = float(raw_entry_price)
        else:
            entry_stock_price = float(entry_stock_price)
    else:
        entry_stock_price = float(entry_stock_price)

    # Store entry stock price
    if "entry_point" not in play:
        play["entry_point"] = {}
    play["entry_point"]["entry_stock_price"] = entry_stock_price

    trade_type = play.get("trade_type", "").upper()

    # Calculate take profit target if using stock price percentage
    if play["take_profit"].get("stock_price_pct"):
        tp_pct = play["take_profit"]["stock_price_pct"] / 100
        if trade_type == "CALL":
            play["take_profit"]["TP_stock_price_target"] = entry_stock_price * (1 + tp_pct)
        else:  # PUT
            play["take_profit"]["TP_stock_price_target"] = entry_stock_price * (1 - tp_pct)

    # Calculate stop loss targets if using stock price percentage
    if play["stop_loss"].get("stock_price_pct"):
        sl_pct = play["stop_loss"]["stock_price_pct"] / 100
        if trade_type == "CALL":
            play["stop_loss"]["SL_stock_price_target"] = entry_stock_price * (1 - sl_pct)
        else:  # PUT
            play["stop_loss"]["SL_stock_price_target"] = entry_stock_price * (1 + sl_pct)

    # Calculate contingency stop loss target if applicable
    if play["stop_loss"].get("contingency_stock_price_pct"):
        contingency_sl_pct = play["stop_loss"]["contingency_stock_price_pct"] / 100
        if trade_type == "CALL":
            play["stop_loss"]["contingency_SL_stock_price_target"] = entry_stock_price * (1 - contingency_sl_pct)
        else:  # PUT
            play["stop_loss"]["contingency_SL_stock_price_target"] = entry_stock_price * (1 + contingency_sl_pct)


def calculate_and_store_premium_levels(play: dict[str, Any], option_data: dict[str, Any]) -> None:
    """
    Calculate and store TP/SL premium levels in the play data using correct entry price.

    This function calculates target premiums for percentage-based TP/SL settings
    and stores them in the play dictionary for future evaluation.

    Args:
        play: Play data dictionary (modified in place)
        option_data: Option data dictionary with bid/ask/mid/last prices

    Side Effects:
        Updates play dictionary with:
        - take_profit.TP_option_prem (if premium_pct set)
        - stop_loss.SL_option_prem (if premium_pct set)
        - stop_loss.contingency_SL_option_prem (if contingency_premium_pct set)
    """
    # Get entry premium based on entry order type
    entry_order_type = play.get("entry_point", {}).get("order_type", "limit at bid")

    if entry_order_type == "limit at bid":
        entry_premium = option_data.get("bid", 0.0)
    elif entry_order_type == "limit at ask":
        entry_premium = option_data.get("ask", 0.0)
    elif entry_order_type == "limit at mid":
        entry_premium = option_data.get("mid", 0.0)
    else:  # 'limit at last' or 'market'
        entry_premium = option_data.get("last", 0.0)

    if play["take_profit"].get("premium_pct"):
        tp_pct = play["take_profit"]["premium_pct"] / 100
        play["take_profit"]["TP_option_prem"] = entry_premium * (1 + tp_pct)

    if play["stop_loss"].get("premium_pct"):
        sl_pct = play["stop_loss"]["premium_pct"] / 100
        play["stop_loss"]["SL_option_prem"] = entry_premium * (1 - sl_pct)

    # Add contingency SL premium calculation if it exists
    if play["stop_loss"].get("contingency_premium_pct"):
        contingency_sl_pct = play["stop_loss"]["contingency_premium_pct"] / 100
        play["stop_loss"]["contingency_SL_option_prem"] = entry_premium * (1 - contingency_sl_pct)


# ==================================================
# Opening Strategy Evaluation
# ==================================================


def evaluate_opening_strategy(symbol: str, play: dict[str, Any], get_stock_price_fn: GetStockPriceFn | None = None) -> bool:
    """
    Evaluate if opening conditions are met based on stock price and entry point.

    Checks if the current stock price is within the entry buffer of the
    target entry price for the play.

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        play: Play data dictionary
        get_stock_price_fn: Optional function to get stock price (for testing/injection)
                           If None, imports from core module

    Returns:
        bool: True if entry conditions are met, False otherwise

    Entry Logic:
        - For CALL/PUT trades: price must be within ±buffer of entry_point.stock_price
        - Buffer is configured in settings.yaml under entry_strategy.buffer
    """
    logging.debug(f"Evaluating opening strategy for {symbol} using play data...")

    entry_point = play.get("entry_point", {}).get("stock_price", 0)

    # Get stock price (allow injection for testing)
    stock_price_getter = get_stock_price_fn
    if stock_price_getter is None:
        from goldflipper.core import get_stock_price

        stock_price_getter = get_stock_price

    if stock_price_getter is None:
        logging.error("Stock price getter is unavailable")
        return False

    last_price = stock_price_getter(symbol)
    if last_price is None:
        logging.error(f"Could not get current price for {symbol}")
        display.error(f"Could not get current price for {symbol}")
        return False

    trade_type = play.get("trade_type", "").upper()

    # Get buffer from config instead of hardcoding (ensure float conversion)
    buffer = float(config.get("entry_strategy", "buffer", default=0.05))
    lower_bound = entry_point - buffer
    upper_bound = entry_point + buffer

    if trade_type == "CALL" or trade_type == "PUT":
        # Check if the last price is within ±buffer of the entry point
        condition_met = lower_bound <= last_price <= upper_bound
        comparison = (
            f"between {lower_bound:.2f} and {upper_bound:.2f}" if condition_met else f"not within ±{buffer:.2f} of entry point {entry_point:.2f}"
        )
    else:
        logging.error(f"Invalid trade type: {trade_type}. Must be CALL or PUT.")
        display.error(f"Invalid trade type: {trade_type}. Must be CALL or PUT.")
        return False

    if condition_met:
        logging.info(f"Opening condition met: Current price {last_price:.2f} is {comparison} for {trade_type}")
        display.success(f"OPENING: {symbol} condition met! Price {last_price:.2f} is {comparison}")
    else:
        logging.debug(f"Opening condition not met: Current price {last_price:.2f} is {comparison} for {trade_type}")

    # Always show a concise evaluation line with the key data and result
    status_tag = "[HIT]" if condition_met else "[MISS]"
    message = f"ENTRY ${symbol} {status_tag}: price ${last_price:.2f} target ${lower_bound:.2f}-${upper_bound:.2f}"
    if condition_met:
        display.success(message)
    else:
        display.status(message)

    return condition_met


# ==================================================
# Closing Strategy Evaluation
# ==================================================


def evaluate_closing_strategy(
    symbol: str,
    play: dict[str, Any],
    play_file: str | None = None,
    get_stock_price_fn: GetStockPriceFn | None = None,
    get_option_data_fn: GetOptionDataFn | None = None,
    save_play_fn: SavePlayFn | None = None,
) -> dict[str, Any]:
    """
    Evaluate if closing conditions are met. Supports:
    - Mixed conditions (e.g., TP by stock price, SL by premium %)
    - Multiple conditions (both stock price AND premium % for either TP or SL)
    - Contingency stop loss with primary and backup conditions
    - Stock price absolute value
    - Stock price percentage movement
    - Option premium percentage

    Args:
        symbol: The underlying symbol
        play: The play data dictionary
        play_file: Optional path to play file - if provided, will save play
                   after calculating missing targets
        get_stock_price_fn: Optional function to get stock price (for testing)
        get_option_data_fn: Optional function to get option data (for testing)
        save_play_fn: Optional function to save play (for testing)

    Returns:
        Dict with condition flags:
        - 'should_close': bool - Whether to close the position
        - 'is_profit': bool - True if closing for take profit
        - 'is_primary_loss': bool - True if closing for stop loss
        - 'is_contingency_loss': bool - True if closing for contingency SL
        - 'sl_type': str - Stop loss type ('STOP', 'LIMIT', 'CONTINGENCY')
    """
    logging.debug(f"Evaluating closing strategy for {symbol} using play data...")

    # Get functions for data access (allow injection for testing)
    stock_price_getter = get_stock_price_fn
    if stock_price_getter is None:
        from goldflipper.core import get_stock_price

        stock_price_getter = get_stock_price

    option_data_getter = get_option_data_fn
    if option_data_getter is None:
        from goldflipper.core import get_option_data

        option_data_getter = get_option_data

    save_play = save_play_fn
    if save_play is None:
        from goldflipper.strategy.shared.play_manager import save_play_improved

        save_play = save_play_improved

    # Get current stock price
    if stock_price_getter is None:
        logging.error("Stock price getter is unavailable")
        return {
            "should_close": False,
            "is_profit": False,
            "is_primary_loss": False,
            "is_contingency_loss": False,
            "sl_type": play.get("stop_loss", {}).get("SL_type", "STOP"),
        }

    last_price = stock_price_getter(symbol)
    if last_price is None:
        logging.error(f"Could not get current price for {symbol}")
        display.error(f"Could not get current price for {symbol}")
        return {
            "should_close": False,
            "is_profit": False,
            "is_primary_loss": False,
            "is_contingency_loss": False,
            "sl_type": play.get("stop_loss", {}).get("SL_type", "STOP"),
        }

    trade_type = play.get("trade_type", "").upper()

    # Initialize condition flags
    profit_condition = False
    loss_condition = False
    contingency_loss_condition = False

    # Track if we calculated any missing targets
    calculated_values = False

    # Get entry stock price for percentage calculations
    entry_stock_price = play.get("entry_point", {}).get("entry_stock_price")
    entry_premium = play.get("entry_point", {}).get("entry_premium")

    # =================================================================
    # TAKE PROFIT EVALUATION
    # =================================================================

    # Check stock price-based take profit (absolute)
    if play["take_profit"].get("stock_price") is not None:
        if trade_type == "CALL":
            profit_condition = profit_condition or (last_price >= play["take_profit"]["stock_price"])
        elif trade_type == "PUT":
            profit_condition = profit_condition or (last_price <= play["take_profit"]["stock_price"])

    # Check percentage-based take profit
    if play["take_profit"].get("stock_price_pct") is not None:
        tp_target = play["take_profit"].get("TP_stock_price_target")
        if tp_target is None and entry_stock_price is not None:
            # Calculate on-the-fly
            tp_pct = play["take_profit"]["stock_price_pct"] / 100
            if trade_type == "CALL":
                tp_target = entry_stock_price * (1 + tp_pct)
            else:  # PUT
                tp_target = entry_stock_price * (1 - tp_pct)
            play["take_profit"]["TP_stock_price_target"] = tp_target
            calculated_values = True
            logging.info(f"Calculated TP_stock_price_target on-the-fly: ${tp_target:.2f}")

        if tp_target is not None:
            if trade_type == "CALL":
                profit_condition = profit_condition or (last_price >= tp_target)
            elif trade_type == "PUT":
                profit_condition = profit_condition or (last_price <= tp_target)

    # =================================================================
    # STOP LOSS EVALUATION
    # =================================================================

    sl_type = play["stop_loss"].get("SL_type", "STOP")

    # Check stock price-based stop loss (absolute)
    if play["stop_loss"].get("stock_price") is not None:
        if trade_type == "CALL":
            loss_condition = loss_condition or (last_price <= play["stop_loss"]["stock_price"])
        elif trade_type == "PUT":
            loss_condition = loss_condition or (last_price >= play["stop_loss"]["stock_price"])

    # Check percentage-based stop loss
    if play["stop_loss"].get("stock_price_pct") is not None:
        sl_target = play["stop_loss"].get("SL_stock_price_target")
        if sl_target is None and entry_stock_price is not None:
            # Calculate on-the-fly
            sl_pct = play["stop_loss"]["stock_price_pct"] / 100
            if trade_type == "CALL":
                sl_target = entry_stock_price * (1 - sl_pct)
            else:  # PUT
                sl_target = entry_stock_price * (1 + sl_pct)
            play["stop_loss"]["SL_stock_price_target"] = sl_target
            calculated_values = True
            logging.info(f"Calculated SL_stock_price_target on-the-fly: ${sl_target:.2f}")

        if sl_target is not None:
            if trade_type == "CALL":
                loss_condition = loss_condition or (last_price <= sl_target)
            elif trade_type == "PUT":
                loss_condition = loss_condition or (last_price >= sl_target)

    # =================================================================
    # CONTINGENCY STOP LOSS EVALUATION
    # =================================================================

    if sl_type == "CONTINGENCY":
        # Check absolute contingency price
        if play["stop_loss"].get("contingency_stock_price") is not None:
            if trade_type == "CALL":
                contingency_loss_condition = contingency_loss_condition or (last_price <= play["stop_loss"]["contingency_stock_price"])
            elif trade_type == "PUT":
                contingency_loss_condition = contingency_loss_condition or (last_price >= play["stop_loss"]["contingency_stock_price"])

        # Check percentage-based contingency
        if play["stop_loss"].get("contingency_stock_price_pct") is not None:
            contingency_sl_target = play["stop_loss"].get("contingency_SL_stock_price_target")
            if contingency_sl_target is None and entry_stock_price is not None:
                # Calculate on-the-fly
                contingency_sl_pct = play["stop_loss"]["contingency_stock_price_pct"] / 100
                if trade_type == "CALL":
                    contingency_sl_target = entry_stock_price * (1 - contingency_sl_pct)
                else:  # PUT
                    contingency_sl_target = entry_stock_price * (1 + contingency_sl_pct)
                play["stop_loss"]["contingency_SL_stock_price_target"] = contingency_sl_target
                calculated_values = True
                logging.info(f"Calculated contingency_SL_stock_price_target on-the-fly: ${contingency_sl_target:.2f}")

            if contingency_sl_target is not None:
                if trade_type == "CALL":
                    contingency_loss_condition = contingency_loss_condition or (last_price <= contingency_sl_target)
                elif trade_type == "PUT":
                    contingency_loss_condition = contingency_loss_condition or (last_price >= contingency_sl_target)

    # =================================================================
    # PREMIUM-BASED CONDITIONS
    # =================================================================

    if option_data_getter is None:
        logging.error("Option data getter is unavailable")
        option_data = None
    else:
        option_data = option_data_getter(play["option_contract_symbol"])
    current_premium = None

    if option_data:
        current_premium = option_data.get("premium")

        # Check premium-based take profit
        if play["take_profit"].get("premium_pct") is not None:
            tp_target = play["take_profit"].get("TP_option_prem")
            if tp_target is None and entry_premium is not None:
                tp_pct = play["take_profit"]["premium_pct"] / 100
                tp_target = entry_premium * (1 + tp_pct)
                play["take_profit"]["TP_option_prem"] = tp_target
                calculated_values = True
                logging.info(f"Calculated TP_option_prem on-the-fly: ${tp_target:.4f}")

            if tp_target is not None and current_premium is not None:
                profit_condition = profit_condition or (current_premium >= tp_target)

        # Check premium-based stop loss
        if play["stop_loss"].get("premium_pct") is not None:
            sl_target = play["stop_loss"].get("SL_option_prem")
            if sl_target is None and entry_premium is not None:
                sl_pct = play["stop_loss"]["premium_pct"] / 100
                sl_target = entry_premium * (1 - sl_pct)
                play["stop_loss"]["SL_option_prem"] = sl_target
                calculated_values = True
                logging.info(f"Calculated SL_option_prem on-the-fly: ${sl_target:.4f}")

            if sl_target is not None and current_premium is not None:
                loss_condition = loss_condition or (current_premium <= sl_target)

        # Check contingency premium condition
        if sl_type == "CONTINGENCY" and play["stop_loss"].get("contingency_premium_pct") is not None:
            contingency_sl_target = play["stop_loss"].get("contingency_SL_option_prem")
            if contingency_sl_target is None and entry_premium is not None:
                contingency_sl_pct = play["stop_loss"]["contingency_premium_pct"] / 100
                contingency_sl_target = entry_premium * (1 - contingency_sl_pct)
                play["stop_loss"]["contingency_SL_option_prem"] = contingency_sl_target
                calculated_values = True
                logging.info(f"Calculated contingency_SL_option_prem on-the-fly: ${contingency_sl_target:.4f}")

            if contingency_sl_target is not None and current_premium is not None:
                contingency_loss_condition = contingency_loss_condition or (current_premium <= contingency_sl_target)

    # =================================================================
    # TRAILING STOP CONDITIONS
    # =================================================================

    try:
        from goldflipper.strategy.trailing import get_trailing_tp_levels, trailing_tp_enabled

        if trailing_tp_enabled(play):
            tp_levels = get_trailing_tp_levels(play)
            tp1 = tp_levels.get("tp1_premium")
            tp2 = tp_levels.get("tp2_premium")

            if option_data and current_premium is not None:
                if tp1 is not None and current_premium <= tp1:
                    profit_condition = True
                    logging.info("Trailing TP1 (floor) condition met by premium")
                if tp2 is not None and current_premium >= tp2:
                    profit_condition = True
                    logging.info("Trailing TP2 (ceiling) condition met by premium")
    except Exception as e:
        logging.warning(f"Error evaluating trailing conditions: {e}")

    # =================================================================
    # LOGGING AND DISPLAY
    # =================================================================

    if profit_condition:
        logging.info("Take profit condition met")
        display.success(f"CLOSING: {symbol} Take Profit condition met!")
    if loss_condition:
        logging.info(f"{'Primary' if sl_type == 'CONTINGENCY' else ''} Stop loss condition met")
        display.warning(f"CLOSING: {symbol} {'Primary' if sl_type == 'CONTINGENCY' else ''} Stop loss condition met")
    if contingency_loss_condition:
        logging.info("Contingency (backup) stop loss condition met")
        display.error(f"CLOSING: {symbol} Contingency (backup) stop loss condition met")

    # Show concise evaluation summary
    tag = "[HOLD]"
    reason = "no TP/SL/contingency hit"
    if profit_condition:
        tag = "[TP]"
        reason = "take profit target hit"
    elif contingency_loss_condition:
        tag = "[CONT]"
        reason = "contingency stop loss hit"
    elif loss_condition:
        tag = "[SL]"
        reason = "stop loss target hit"

    eval_parts = [f"EXIT ${symbol} {tag}: price ${last_price:.2f}"]
    if current_premium is not None:
        eval_parts.append(f"prem ${current_premium:.4f}")
    eval_parts.append(reason)
    exit_message = " | ".join(eval_parts)

    # Color-code exit summary by status tag
    if tag == "[TP]":
        display.success(exit_message)
    elif tag == "[SL]":
        display.warning(exit_message)
    elif tag == "[CONT]":
        display.error(exit_message)
    else:
        display.status(exit_message)

    # Save play if we calculated missing targets
    if calculated_values and play_file:
        if save_play is not None:
            try:
                save_play(play, play_file)
                logging.info(f"Saved play after calculating missing targets: {play_file}")
            except Exception as e:
                logging.warning(f"Failed to save play after calculating targets: {e}")

    return {
        "should_close": profit_condition or loss_condition or contingency_loss_condition,
        "is_profit": profit_condition,
        "is_primary_loss": loss_condition,
        "is_contingency_loss": contingency_loss_condition,
        "sl_type": sl_type,
    }

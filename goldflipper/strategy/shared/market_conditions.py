"""
Market Conditions Screening Module

Higher-level screening evaluators that wrap MarketDataManager calls with
condition logic. Intended to be called by strategy runners during
evaluate_new_plays() to filter or confirm candidate setups.

All evaluators:
  • Return a dict with at minimum {'passed': bool, 'reason': str}.
  • Are permissive on data errors (passed=True when data is unavailable)
    so that missing data does not silently block all trades.
  • Respect an 'enabled' flag in the config — disabled conditions always
    return passed=True without fetching any data.

Evaluators
----------
evaluate_vwap_condition
    Check whether price is on the correct side of VWAP (above for CALLs,
    below for PUTs) and optionally within a proximity band.

evaluate_volume_profile_condition
    Check price position relative to the Volume Profile POC, VAH, VAL.
    Can require price to be inside the value area, above/below POC, or
    within a certain percentage of the POC.

evaluate_greek_conditions
    Evaluate delta range, gamma squeeze / fade, delta fade, and parabolic
    extension at an option contract level. Chain-wide GEX conditions require
    an expiration date in the play dict.

Usage example (inside a strategy runner)::

    from goldflipper.strategy.shared.market_conditions import (
        evaluate_vwap_condition,
        evaluate_volume_profile_condition,
        evaluate_greek_conditions,
    )

    vwap_cfg = playbook.option_swings_config.vwap.to_dict()
    vwap_result = evaluate_vwap_condition(self.market_data, symbol, play, vwap_cfg)
    if not vwap_result['passed']:
        logging.info(f"VWAP screen failed: {vwap_result['reason']}")
        continue  # skip play
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# VWAP Condition
# =============================================================================


def evaluate_vwap_condition(
    market_data: Any,
    symbol: str,
    play: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate a VWAP-based entry screen.

    Checks whether the current price is on the correct side of VWAP and
    optionally whether it is within a proximity band.

    Args:
        market_data: MarketDataManager instance.
        symbol: Underlying stock ticker.
        play: Play data dict (reads trade_type).
        config: Dict with keys (all optional):
            enabled (bool)           – Skip entirely if False (default True).
            interval (str)           – Bar interval for VWAP, e.g. '4h'.
            lookback_days (int)      – Bars window.
            require_price_above_vwap (bool) – CALL entry must be above VWAP.
            require_price_below_vwap (bool) – PUT entry must be below VWAP.
            proximity_pct (float)    – Price must be within N % of VWAP.

    Returns:
        Dict: passed, vwap, price, price_vs_vwap_pct, reason.
    """
    result: dict[str, Any] = {
        "passed": True,
        "vwap": None,
        "price": None,
        "price_vs_vwap_pct": None,
        "reason": "",
    }

    if not config.get("enabled", False):
        result["reason"] = "vwap_disabled"
        return result

    try:
        interval = config.get("interval", "4h")
        lookback = config.get("lookback_days", 5)

        vwap_data = market_data.get_vwap(symbol, interval=interval, lookback_days=lookback)
        if not vwap_data or vwap_data.get("vwap") is None:
            result["reason"] = "vwap_data_unavailable"
            return result  # permissive

        vwap_val = float(vwap_data["vwap"])
        price = market_data.get_stock_price(symbol)
        if price is None:
            result["reason"] = "price_unavailable"
            return result

        pct = (price - vwap_val) / vwap_val * 100.0
        result.update({"vwap": round(vwap_val, 4), "price": round(price, 4), "price_vs_vwap_pct": round(pct, 3)})

        trade_type = play.get("trade_type", "").upper()

        if trade_type == "CALL" and config.get("require_price_above_vwap", False):
            if price <= vwap_val:
                result["passed"] = False
                result["reason"] = f"call_below_vwap (price={price:.2f}, vwap={vwap_val:.2f})"
                return result

        if trade_type == "PUT" and config.get("require_price_below_vwap", False):
            if price >= vwap_val:
                result["passed"] = False
                result["reason"] = f"put_above_vwap (price={price:.2f}, vwap={vwap_val:.2f})"
                return result

        prox = config.get("proximity_pct")
        if prox is not None and abs(pct) > float(prox):
            result["passed"] = False
            result["reason"] = f"price_too_far_from_vwap ({pct:+.1f}% > ±{prox}%)"
            return result

        result["reason"] = f"passed ({pct:+.1f}% from VWAP)"
        return result

    except Exception as exc:
        logger.error(f"evaluate_vwap_condition error for {symbol}: {exc}")
        result["reason"] = f"error: {exc}"
        return result  # permissive


# =============================================================================
# Volume Profile Condition
# =============================================================================


def evaluate_volume_profile_condition(
    market_data: Any,
    symbol: str,
    play: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate a Volume Profile based entry screen.

    Checks price position relative to VP POC, VAH, VAL.

    Args:
        market_data: MarketDataManager instance.
        symbol: Underlying stock ticker.
        play: Play data dict.
        config: Dict with keys (all optional):
            enabled (bool)
            interval (str)              – Bar interval, e.g. '4h'.
            lookback_days (int)
            n_bins (int)                – Price bins (default 24).
            value_area_pct (float)      – Value area fraction (default 0.70).
            require_in_value_area (bool)– Price must be between VAL and VAH.
            call_requires_above_poc (bool) – CALL entry must be above POC.
            put_requires_below_poc (bool)  – PUT entry must be below POC.
            poc_proximity_pct (float)   – Must be within N % of POC.

    Returns:
        Dict: passed, poc, vah, val, price, in_value_area, above_poc, reason.
    """
    result: dict[str, Any] = {
        "passed": True,
        "poc": None,
        "vah": None,
        "val": None,
        "price": None,
        "in_value_area": None,
        "above_poc": None,
        "reason": "",
    }

    if not config.get("enabled", False):
        result["reason"] = "volume_profile_disabled"
        return result

    try:
        interval = config.get("interval", "4h")
        lookback = config.get("lookback_days", 10)
        n_bins = config.get("n_bins", 24)
        va_pct = config.get("value_area_pct", 0.70)

        vp = market_data.get_volume_profile(symbol, interval=interval, lookback_days=lookback, n_bins=n_bins, value_area_pct=va_pct)
        if vp is None:
            result["reason"] = "vp_data_unavailable"
            return result  # permissive

        price = market_data.get_stock_price(symbol)
        if price is None:
            result["reason"] = "price_unavailable"
            return result

        in_va = vp.price_in_value_area(price)
        above_poc = vp.price_above_poc(price)
        pct_from_poc = vp.pct_from_poc(price)

        result.update(
            {
                "poc": round(vp.poc, 4),
                "vah": round(vp.vah, 4),
                "val": round(vp.val, 4),
                "price": round(price, 4),
                "in_value_area": in_va,
                "above_poc": above_poc,
                "pct_from_poc": round(pct_from_poc, 2),
            }
        )

        trade_type = play.get("trade_type", "").upper()

        if config.get("require_in_value_area", False) and not in_va:
            result["passed"] = False
            result["reason"] = f"outside_value_area (price={price:.2f}, VAL={vp.val:.2f}, VAH={vp.vah:.2f})"
            return result

        if trade_type == "CALL" and config.get("call_requires_above_poc", False) and not above_poc:
            result["passed"] = False
            result["reason"] = f"call_below_poc (price={price:.2f}, poc={vp.poc:.2f})"
            return result

        if trade_type == "PUT" and config.get("put_requires_below_poc", False) and above_poc:
            result["passed"] = False
            result["reason"] = f"put_above_poc (price={price:.2f}, poc={vp.poc:.2f})"
            return result

        poc_prox = config.get("poc_proximity_pct")
        if poc_prox is not None and abs(pct_from_poc) > float(poc_prox):
            result["passed"] = False
            result["reason"] = f"too_far_from_poc ({pct_from_poc:+.1f}% > ±{poc_prox}%)"
            return result

        result["reason"] = f"passed (poc={vp.poc:.2f}, in_va={in_va}, {pct_from_poc:+.1f}% from POC)"
        return result

    except Exception as exc:
        logger.error(f"evaluate_volume_profile_condition error for {symbol}: {exc}")
        result["reason"] = f"error: {exc}"
        return result  # permissive


# =============================================================================
# Greek Conditions
# =============================================================================


def evaluate_greek_conditions(
    market_data: Any,
    symbol: str,
    play: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate Greeks-based entry and exit screening conditions.

    Checks option Greeks at the target contract and optionally across the
    full chain (for GEX-based conditions).

    Args:
        market_data: MarketDataManager instance.
        symbol: Underlying stock ticker.
        play: Play data dict. Reads:
            option_contract_symbol – for per-contract delta/gamma checks.
            expiration_date        – for chain-wide GEX conditions.
            trade_type             – CALL / PUT.
            logging.delta_atOpen   – Entry delta for delta-fade detection.
        config: Dict with keys (all optional):
            enabled (bool)
            min_delta / max_delta (float)     – Delta range filter.
            check_gamma_squeeze (bool)        – Run GEX squeeze detection.
            gamma_squeeze_blocks_entry (bool) – Fail if squeeze detected.
            check_gamma_fade (bool)           – Run gamma fade detection.
            gamma_fade_blocks_entry (bool)    – Fail if fade detected.
            check_delta_fade (bool)           – Run delta fade detection.
            delta_fade_threshold (float)      – Delta point drop to flag (0.15).
            delta_fade_is_exit_signal (bool)  – Note fade as EXIT signal.
            check_parabolic (bool)            – Run parabolic move detection.
            parabolic_interval (str)          – Bar interval for VWAP (default '1h').
            parabolic_vwap_std (float)        – Std-dev distance threshold (2.0).
            parabolic_min_consecutive (int)   – Consecutive bars required (3).
            parabolic_blocks_entry (bool)     – Fail if parabolic detected.

    Returns:
        Dict with keys: passed, delta, gamma, theta, vega, rho,
        gamma_squeeze_detected, gamma_fade_detected, delta_fade_detected,
        parabolic_detected, parabolic_direction, flags, reason.
    """
    result: dict[str, Any] = {
        "passed": True,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "rho": None,
        "implied_volatility": None,
        "gamma_squeeze_detected": False,
        "gamma_fade_detected": False,
        "delta_fade_detected": False,
        "parabolic_detected": False,
        "parabolic_direction": None,
        "flags": [],
        "reason": "",
    }

    if not config.get("enabled", False):
        result["reason"] = "greek_conditions_disabled"
        return result

    try:
        contract = play.get("option_contract_symbol")
        if not contract:
            result["reason"] = "no_contract_symbol"
            return result

        # ── Per-contract Greeks ──────────────────────────────────────────
        option_data = market_data.get_option_quote(contract)
        if option_data:
            for greek in ("delta", "gamma", "theta", "vega", "rho", "implied_volatility"):
                result[greek] = option_data.get(greek)

            # Delta range check
            delta = option_data.get("delta")
            if delta is not None:
                abs_delta = abs(float(delta))
                min_d = config.get("min_delta")
                max_d = config.get("max_delta")
                if min_d is not None and abs_delta < float(min_d):
                    result["passed"] = False
                    result["flags"].append(f"delta_too_low ({abs_delta:.3f} < {min_d})")
                if max_d is not None and abs_delta > float(max_d):
                    result["passed"] = False
                    result["flags"].append(f"delta_too_high ({abs_delta:.3f} > {max_d})")

            # Delta fade check (uses entry delta stored in play logging block)
            if config.get("check_delta_fade", False) and result["delta"] is not None:
                entry_delta = play.get("logging", {}).get("delta_atOpen")
                if entry_delta and float(entry_delta) != 0:
                    from goldflipper.data.greeks.gamma_exposure import detect_delta_fade

                    threshold = float(config.get("delta_fade_threshold", 0.15))
                    fade = detect_delta_fade(float(result["delta"]), float(entry_delta), threshold)
                    result["delta_fade_detected"] = fade
                    if fade:
                        entry_str = f"{entry_delta:.3f}"
                        now_str = f"{result['delta']:.3f}"
                        flag = f"delta_fade (entry={entry_str} → now={now_str})"
                        result["flags"].append(flag)
                        if config.get("delta_fade_is_exit_signal", False):
                            result["flags"].append("EXIT_SIGNAL:delta_fade")

        # ── Parabolic detection (VWAP-based, uses OHLCV bars) ───────────
        if config.get("check_parabolic", False):
            try:
                para_interval = config.get("parabolic_interval", "1h")
                bars = market_data.get_bars(symbol, interval=para_interval, lookback_days=3)
                if bars is not None and not bars.empty:
                    bars.columns = [str(c).lower() for c in bars.columns]
                    if {"high", "low", "close", "volume"}.issubset(bars.columns):
                        from goldflipper.data.greeks.gamma_exposure import detect_parabolic_move
                        from goldflipper.data.indicators.base import MarketData
                        from goldflipper.data.indicators.vwap import VWAPCalculator

                        md = MarketData(high=bars["high"], low=bars["low"], close=bars["close"], volume=bars["volume"])
                        calc = VWAPCalculator(md)
                        vwap_val = calc.current_vwap()
                        std_val = calc.current_std_dev()

                        if vwap_val and std_val:
                            closes = bars["close"].tolist()
                            vwap_std = float(config.get("parabolic_vwap_std", 2.0))
                            min_bars = int(config.get("parabolic_min_consecutive", 3))
                            para = detect_parabolic_move(closes, vwap_val, std_val, vwap_std, min_bars)
                            if para.get("is_parabolic"):
                                result["parabolic_detected"] = True
                                result["parabolic_direction"] = para.get("direction")
                                result["flags"].append(
                                    f"parabolic_{para['direction']} "
                                    f"({para['vwap_std_distance']:.1f}σ from VWAP, "
                                    f"{para.get('consecutive_up', para.get('consecutive_down', 0))} consec bars)"
                                )
                                if config.get("parabolic_blocks_entry", False):
                                    result["passed"] = False
            except Exception as para_exc:
                logger.warning(f"Parabolic check failed for {symbol}: {para_exc}")

        # ── Chain-wide GEX conditions (gamma squeeze / fade) ────────────
        squeeze_requested = config.get("check_gamma_squeeze", False)
        fade_requested = config.get("check_gamma_fade", False)
        if squeeze_requested or fade_requested:
            try:
                expiration = play.get("expiration_date")
                if expiration:
                    chain = market_data._try_providers("get_option_chain", symbol, expiration)
                    if chain:
                        import pandas as pd

                        from goldflipper.data.greeks.gamma_exposure import GammaExposureAnalyzer

                        calls = chain.get("calls", pd.DataFrame())
                        puts = chain.get("puts", pd.DataFrame())
                        if not calls.empty:
                            calls = calls.copy()
                            calls["type"] = "call"
                        if not puts.empty:
                            puts = puts.copy()
                            puts["type"] = "put"
                        chain_df = pd.concat([c for c in [calls, puts] if not c.empty], ignore_index=True)

                        if not chain_df.empty:
                            spot = market_data.get_stock_price(symbol)
                            if spot:
                                analyzer = GammaExposureAnalyzer(chain_df, spot)

                                if squeeze_requested:
                                    squeeze = analyzer.is_gamma_squeeze()
                                    result["gamma_squeeze_detected"] = squeeze
                                    if squeeze:
                                        result["flags"].append(f"gamma_squeeze (near_gex={analyzer.near_spot_gex():.0f})")
                                        if config.get("gamma_squeeze_blocks_entry", False):
                                            result["passed"] = False

                                if fade_requested:
                                    fade = analyzer.is_gamma_fade()
                                    result["gamma_fade_detected"] = fade
                                    if fade:
                                        result["flags"].append(f"gamma_fade (atm_γ={analyzer.atm_gamma():.5f}, avg_γ={analyzer.avg_gamma():.5f})")
                                        if config.get("gamma_fade_blocks_entry", False):
                                            result["passed"] = False
            except Exception as chain_exc:
                logger.warning(f"Chain GEX conditions failed for {symbol}: {chain_exc}")

        # ── Final reason string ──────────────────────────────────────────
        if result["flags"]:
            result["reason"] = ", ".join(result["flags"])
        else:
            result["reason"] = "all_greek_conditions_passed"

        return result

    except Exception as exc:
        logger.error(f"evaluate_greek_conditions error for {symbol}: {exc}")
        result["reason"] = f"error: {exc}"
        return result  # permissive

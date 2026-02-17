"""
GTD Evaluator

Builds GTDContext from play data, runs all configured GTD methods, and resolves
conflicts between method recommendations to produce a final effective date decision.

Conflict Resolution Rules:
    1. CLOSE_NOW wins over everything (any method can trigger immediate close)
    2. Among SHORTEN recommendations: take the earliest date (most conservative)
    3. Among EXTEND recommendations: take the latest date, capped at option expiration
    4. SHORTEN beats EXTEND (safety first)
    5. If no method has an opinion, effective date stays unchanged

Usage:
    from goldflipper.strategy.gtd.evaluator import GTDEvaluator

    evaluator = GTDEvaluator(market_data=market_data_manager)
    result = evaluator.evaluate_play(play)

    if result['should_close']:
        # Trigger immediate exit
    elif result['effective_date_changed']:
        # Persist new effective date to play JSON
"""

import logging
from datetime import date, datetime
from typing import Any

from goldflipper.strategy.gtd.base import GTDAction, GTDContext, GTDResult
from goldflipper.strategy.gtd.registry import GTDRegistry

logger = logging.getLogger(__name__)


class GTDEvaluator:
    """Evaluates all configured Dynamic GTD methods for a play and resolves conflicts.

    Attributes:
        market_data: MarketDataManager instance for fetching prices/greeks (optional)
    """

    def __init__(self, market_data: Any | None = None):
        """Initialize the evaluator.

        Args:
            market_data: MarketDataManager for fetching live data (optional, some methods
                         don't require it)
        """
        self.market_data = market_data
        # Ensure methods are discovered
        GTDRegistry.discover()

    def evaluate_play(self, play: dict[str, Any]) -> dict[str, Any]:
        """Evaluate all configured GTD methods for a play.

        Args:
            play: Play dictionary with dynamic_gtd section

        Returns:
            Dict with evaluation results:
                - should_close (bool): Whether to close the position immediately
                - close_reason (str): Reason for closing (empty if not closing)
                - effective_date (Optional[str]): New effective date in MM/DD/YYYY (None if unchanged)
                - effective_date_changed (bool): Whether the effective date was modified
                - method_results (List[Dict]): Individual method results for logging
                - is_gtd_exit (bool): True if this is a GTD-triggered exit
        """
        gtd_config = play.get("dynamic_gtd", {})

        # Quick exit if GTD is not enabled
        if not gtd_config.get("enabled", False):
            return {
                "should_close": False,
                "close_reason": "",
                "effective_date": None,
                "effective_date_changed": False,
                "method_results": [],
                "is_gtd_exit": False,
            }

        methods_config = gtd_config.get("methods", [])
        if not methods_config:
            return {
                "should_close": False,
                "close_reason": "",
                "effective_date": None,
                "effective_date_changed": False,
                "method_results": [],
                "is_gtd_exit": False,
            }

        # Build context
        context_base = self._build_context_base(play)

        # Run each configured method
        results: list[tuple[str, GTDResult]] = []
        method_log: list[dict[str, Any]] = []

        for method_cfg in methods_config:
            if not method_cfg.get("enabled", True):
                continue

            method_name = method_cfg.get("method", "")
            method_params = method_cfg.get("params", {})
            method_state = gtd_config.get("method_states", {}).get(method_name, {})

            # Instantiate method
            method = GTDRegistry.create(method_name)
            if method is None:
                logger.warning(f"GTD method not found in registry: {method_name}")
                method_log.append({"method": method_name, "status": "not_found", "action": None, "reason": "Method not registered"})
                continue

            # Skip methods requiring market data if unavailable
            if method.requires_market_data() and self.market_data is None:
                logger.debug(f"Skipping GTD method {method_name}: requires market data but none available")
                method_log.append({"method": method_name, "status": "skipped", "action": None, "reason": "No market data"})
                continue

            # Build method-specific context
            context = GTDContext(
                play=context_base["play"],
                current_date=context_base["current_date"],
                entry_date=context_base["entry_date"],
                play_expiration_date=context_base["play_expiration_date"],
                option_expiration_date=context_base["option_expiration_date"],
                current_effective_date=context_base["current_effective_date"],
                current_price=context_base["current_price"],
                entry_price=context_base["entry_price"],
                current_premium=context_base["current_premium"],
                entry_premium=context_base["entry_premium"],
                unrealized_pnl_pct=context_base["unrealized_pnl_pct"],
                greeks=context_base["greeks"],
                days_held=context_base["days_held"],
                days_to_expiry=context_base["days_to_expiry"],
                is_market_open=context_base["is_market_open"],
                upcoming_events=context_base["upcoming_events"],
                method_state=method_state,
                method_params=method_params,
            )

            try:
                # Load state and evaluate
                method.load_state(method_state)
                result = method.evaluate(context)

                results.append((method_name, result))
                method_log.append(
                    {
                        "method": method_name,
                        "status": "evaluated",
                        "action": result.action.value,
                        "reason": result.reason,
                        "recommended_date": result.recommended_date.strftime("%m/%d/%Y") if result.recommended_date else None,
                        "priority": result.priority,
                    }
                )

                # Persist method state
                new_state = method.get_state()
                if new_state:
                    if "method_states" not in gtd_config:
                        gtd_config["method_states"] = {}
                    gtd_config["method_states"][method_name] = new_state

            except Exception as e:
                logger.error(f"Error evaluating GTD method {method_name}: {e}")
                method_log.append({"method": method_name, "status": "error", "action": None, "reason": str(e)})

        # Resolve conflicts
        resolution = self._resolve_conflicts(results, context_base)

        # Update last_evaluated timestamp
        gtd_config["last_evaluated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "should_close": resolution["should_close"],
            "close_reason": resolution["close_reason"],
            "effective_date": resolution["effective_date"],
            "effective_date_changed": resolution["effective_date_changed"],
            "method_results": method_log,
            "is_gtd_exit": resolution["should_close"],
        }

    def _build_context_base(self, play: dict[str, Any]) -> dict[str, Any]:
        """Build the shared context data from play + market data.

        Returns a dict (not GTDContext) so method-specific params can be injected per method.
        """
        current_date = date.today()

        # Parse dates from play
        entry_date = self._parse_date(play.get("logging", {}).get("datetime_atOpen"))
        play_expiration_date = self._parse_date(play.get("play_expiration_date"))
        option_expiration_date = self._parse_date(play.get("expiration_date"))

        # Parse current effective date
        gtd_config = play.get("dynamic_gtd", {})
        current_effective_date = self._parse_date(gtd_config.get("effective_date"))

        # Market data
        current_price = None
        current_premium = None
        greeks: dict[str, float] = {}

        symbol = play.get("symbol")
        option_symbol = play.get("option_contract_symbol")

        if self.market_data is not None and symbol:
            try:
                current_price = self.market_data.get_stock_price(symbol)
                if current_price is not None and hasattr(current_price, "item"):
                    current_price = float(current_price.item())
                elif current_price is not None:
                    current_price = float(current_price)
            except Exception as e:
                logger.debug(f"Could not get stock price for GTD context: {e}")

            if option_symbol:
                try:
                    option_data = self.market_data.get_option_quote(option_symbol)
                    if option_data:
                        current_premium = option_data.get("premium") or option_data.get("last")
                        for greek in ("delta", "gamma", "theta", "vega", "rho"):
                            if greek in option_data:
                                greeks[greek] = float(option_data[greek])
                except Exception as e:
                    logger.debug(f"Could not get option data for GTD context: {e}")

        # Entry data from play
        entry_price = play.get("entry_point", {}).get("entry_stock_price")
        entry_premium = play.get("entry_point", {}).get("entry_premium")
        if entry_price is not None:
            entry_price = float(entry_price)
        if entry_premium is not None:
            entry_premium = float(entry_premium)

        # Calculate derived fields
        days_held = None
        if entry_date is not None:
            days_held = (current_date - entry_date).days

        days_to_expiry = None
        if option_expiration_date is not None:
            days_to_expiry = (option_expiration_date - current_date).days

        unrealized_pnl_pct = None
        if entry_premium is not None and entry_premium > 0 and current_premium is not None:
            unrealized_pnl_pct = ((current_premium - entry_premium) / entry_premium) * 100

        return {
            "play": play,
            "current_date": current_date,
            "entry_date": entry_date,
            "play_expiration_date": play_expiration_date,
            "option_expiration_date": option_expiration_date,
            "current_effective_date": current_effective_date,
            "current_price": current_price,
            "entry_price": entry_price,
            "current_premium": current_premium,
            "entry_premium": entry_premium,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "greeks": greeks,
            "days_held": days_held,
            "days_to_expiry": days_to_expiry,
            "is_market_open": True,  # Caller can override if needed
            "upcoming_events": [],  # Future: integrate event calendar
        }

    def _resolve_conflicts(
        self,
        results: list[tuple[str, GTDResult]],
        context_base: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve conflicts between multiple method recommendations.

        Rules:
            1. CLOSE_NOW wins over everything
            2. SHORTEN: take earliest recommended date
            3. EXTEND: take latest recommended date, capped at option expiration
            4. SHORTEN beats EXTEND
            5. No opinions = no change
        """
        if not results:
            return {"should_close": False, "close_reason": "", "effective_date": None, "effective_date_changed": False}

        close_now_results = [(name, r) for name, r in results if r.action == GTDAction.CLOSE_NOW]
        shorten_results = [(name, r) for name, r in results if r.action == GTDAction.SHORTEN and r.recommended_date]
        extend_results = [(name, r) for name, r in results if r.action == GTDAction.EXTEND and r.recommended_date]

        # Rule 1: CLOSE_NOW wins
        if close_now_results:
            # Pick highest priority (lowest number)
            close_now_results.sort(key=lambda x: x[1].priority)
            winner_name, winner_result = close_now_results[0]
            return {
                "should_close": True,
                "close_reason": f"GTD CLOSE_NOW triggered by {winner_name}: {winner_result.reason}",
                "effective_date": None,
                "effective_date_changed": False,
            }

        current_effective = context_base["current_effective_date"]
        option_expiration = context_base["option_expiration_date"]
        new_effective: date | None = None

        # Rule 2: SHORTEN - take earliest date
        if shorten_results:
            shorten_results.sort(key=lambda x: x[1].recommended_date)
            _, earliest = shorten_results[0]
            new_effective = earliest.recommended_date

        # Rule 3: EXTEND - take latest date, capped at option expiration
        if extend_results and new_effective is None:
            extend_results.sort(key=lambda x: x[1].recommended_date, reverse=True)
            _, latest = extend_results[0]
            extended_date = latest.recommended_date
            # Cap at option expiration
            if option_expiration is not None and extended_date > option_expiration:
                extended_date = option_expiration
            new_effective = extended_date

        # Rule 4: SHORTEN beats EXTEND (already handled by checking shorten first)

        # Check if date actually changed
        if new_effective is not None:
            changed = new_effective != current_effective
            return {
                "should_close": False,
                "close_reason": "",
                "effective_date": new_effective.strftime("%m/%d/%Y") if changed else None,
                "effective_date_changed": changed,
            }

        return {"should_close": False, "close_reason": "", "effective_date": None, "effective_date_changed": False}

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse a date string in various formats.

        Supports: MM/DD/YYYY, YYYY-MM-DD, YYYY-MM-DD HH:MM:SS
        """
        if not date_str:
            return None

        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except (ValueError, TypeError):
                continue

        logger.debug(f"Could not parse date: {date_str}")
        return None

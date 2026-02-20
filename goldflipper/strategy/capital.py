"""
Capital Manager for Goldflipper Multi-Strategy System

Gates every new position through account-level and playbook-level risk limits.
Called once per cycle in run_cycle() (via refresh()) and checked before each
open_position() call in _execute_strategy().

Checks (in order — first failure wins):
  1. Global max total open positions (settings.yaml capital_management)
  2. Per-symbol max open positions (risk_config overrides global default)
  3. Per-playbook max open plays (risk_config.max_open_plays)
  4. Per-trade max contracts (risk_config.max_contracts_per_play)
  5. Per-trade fixed dollar limit (risk_config.max_capital_per_trade_fixed)
  6. Per-trade % of equity limit (risk_config.max_capital_per_trade_pct)
  7. Global max capital deployed % (total_active_cost / equity)
  8. Buying power: estimated cost vs available buying power (with reserve)
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class CapitalManager:
    """
    Enforces capital allocation and position sizing limits before new positions are opened.

    Instantiated by StrategyOrchestrator in _initialize_resources() and injected into
    each strategy via strategy.capital_manager.  refresh() is called once per run_cycle()
    to snapshot account state; check_trade() is called per-play before open_position().

    Args:
        client: Alpaca TradingClient (may be None in tests / paper mode without auth).
        config: Full application configuration dict (settings.yaml parsed).
    """

    def __init__(self, client: Any, config: dict[str, Any]):
        self._client = client
        self._config = config
        self._cm_config: dict[str, Any] = config.get("capital_management", {})

        # Account state — refreshed each cycle
        self._buying_power: float = 0.0
        self._equity: float = 0.0
        self._portfolio_value: float = 0.0
        self._account_loaded: bool = False

        # Play / cost cache — invalidated on refresh()
        self._active_plays_cache: list[dict[str, Any]] | None = None
        self._total_deployed_cache: float | None = None

    # =========================================================================
    # Account data
    # =========================================================================

    def refresh(self) -> None:
        """
        Fetch live account data from Alpaca.

        On success, updates buying_power / equity / portfolio_value and marks
        _account_loaded = True.  On failure, logs a warning and keeps stale values
        (buying_power checks are then skipped in check_trade).

        Also invalidates the per-cycle play / cost caches so count_active_plays()
        re-reads the filesystem on the next call.
        """
        # Invalidate filesystem caches each cycle
        self._active_plays_cache = None
        self._total_deployed_cache = None

        if self._client is None:
            return

        try:
            account = self._client.get_account()

            # Prefer options_buying_power when available
            bp = getattr(account, "options_buying_power", None)
            if bp is None:
                bp = getattr(account, "buying_power", "0")
            self._buying_power = float(bp)

            eq = getattr(account, "equity", "0")
            self._equity = float(eq)

            pv = getattr(account, "portfolio_value", "0")
            self._portfolio_value = float(pv)

            self._account_loaded = True
            logger.debug(
                "CapitalManager refreshed: bp=%.2f equity=%.2f portfolio=%.2f",
                self._buying_power,
                self._equity,
                self._portfolio_value,
            )

        except Exception as e:
            logger.warning("CapitalManager: failed to refresh account data: %s", e)
            self._account_loaded = False

    @property
    def buying_power(self) -> float:
        """Current options buying power (or regular buying power if not available)."""
        return self._buying_power

    @property
    def equity(self) -> float:
        """Current account equity."""
        return self._equity

    @property
    def portfolio_value(self) -> float:
        """Current portfolio value."""
        return self._portfolio_value

    # =========================================================================
    # Play counting (filesystem-based, cached per cycle)
    # =========================================================================

    def _load_active_plays(self) -> list[dict[str, Any]]:
        """
        Read all JSON play files from open/ and pending-opening/ folders.

        Result is cached until the next refresh() call so check_trade() for
        multiple plays in the same cycle shares one filesystem scan.
        """
        if self._active_plays_cache is not None:
            return self._active_plays_cache

        plays: list[dict[str, Any]] = []

        try:
            from goldflipper.utils.exe_utils import get_play_subdir

            for folder in ("open", "pending-opening"):
                try:
                    folder_path = get_play_subdir(folder)
                    for filename in os.listdir(folder_path):
                        if not filename.endswith(".json"):
                            continue
                        filepath = os.path.join(folder_path, filename)
                        try:
                            with open(filepath, encoding="utf-8") as fh:
                                play = json.load(fh)
                            plays.append(play)
                        except Exception as e:
                            logger.debug("CapitalManager: could not read play %s: %s", filepath, e)
                except OSError as e:
                    logger.warning("CapitalManager: OS error reading '%s' dir: %s", folder, e)

        except Exception as e:
            logger.warning("CapitalManager: error loading active plays: %s", e)

        self._active_plays_cache = plays
        return plays

    def count_active_plays(self, symbol: str | None = None) -> int:
        """
        Count plays currently in open/ or pending-opening/ folders.

        Args:
            symbol: If provided, count only plays for this ticker (case-insensitive).
                    If None, count all active plays across all symbols.

        Returns:
            Integer count.  Returns 0 on filesystem errors (permissive).
        """
        plays = self._load_active_plays()

        if symbol is None:
            return len(plays)

        symbol_upper = symbol.upper()
        return sum(1 for p in plays if p.get("symbol", "").upper() == symbol_upper)

    # =========================================================================
    # Trade cost estimation
    # =========================================================================

    def estimate_trade_cost(self, play: dict[str, Any]) -> float:
        """
        Estimate the capital required to open this trade.

        BTO (buy calls/puts): entry_premium * contracts * 100
        STO (sell puts/calls): strike_price * contracts * 100  (collateral proxy)

        Falls back to 0.0 if the required fields are missing — the broker will
        perform the definitive buying-power check.
        """
        try:
            contracts = float(play.get("contracts", 1) or 1)
            action = str(play.get("action", play.get("entry_action", "BTO"))).upper()

            if action in ("STO", "SELL_TO_OPEN"):
                strike = play.get("strike_price")
                if strike is None:
                    return 0.0
                return float(strike) * contracts * 100.0

            # BTO path — look for entry premium in multiple locations
            premium: float | None = None

            entry_point = play.get("entry_point", {})
            if isinstance(entry_point, dict):
                premium = entry_point.get("target_price")

            if premium is None:
                premium = play.get("entry_premium") or play.get("premium")

            if premium is None:
                return 0.0

            return float(premium) * contracts * 100.0

        except Exception:
            return 0.0

    def _get_total_deployed(self) -> float:
        """
        Sum of estimated_trade_cost across all active plays.  Cached per cycle.
        """
        if self._total_deployed_cache is not None:
            return self._total_deployed_cache

        plays = self._load_active_plays()
        total = sum(self.estimate_trade_cost(p) for p in plays)
        self._total_deployed_cache = total
        return total

    # =========================================================================
    # Core gate
    # =========================================================================

    def check_trade(self, play: dict[str, Any], risk_config: Any = None) -> tuple[bool, str]:
        """
        Gate a candidate new trade against all capital and position limits.

        Args:
            play:        Play dictionary (as loaded from JSON).
            risk_config: RiskConfig dataclass from the play's playbook, or None.

        Returns:
            (allowed, reason) where allowed is True if the trade is permitted and
            reason is a human-readable explanation (always "ok" on success).

        Checks in order — first failure wins:
            1. Global max_total_open_positions
            2. Per-symbol max (risk_config.max_open_plays_per_symbol > global default)
            3. Per-playbook max_open_plays
            4. Per-trade max_contracts_per_play
            5. Per-trade max_capital_per_trade_fixed (dollars)
            6. Per-trade max_capital_per_trade_pct (% of equity)
            7. Global max_capital_deployed_pct
            8. Buying-power headroom check
        """
        cm = self._cm_config
        if not cm.get("enabled", True):
            return True, "disabled"

        symbol = play.get("symbol", "").upper()
        contracts = int(play.get("contracts", 1) or 1)

        # ------------------------------------------------------------------ #
        # 1. Global total open positions                                       #
        # ------------------------------------------------------------------ #
        max_total = cm.get("max_total_open_positions")
        if max_total is not None:
            total = self.count_active_plays()
            if total >= max_total:
                return False, (f"global max_total_open_positions={max_total} reached (current={total})")

        # ------------------------------------------------------------------ #
        # 2. Per-symbol limit                                                  #
        #    risk_config.max_open_plays_per_symbol takes precedence            #
        # ------------------------------------------------------------------ #
        per_symbol_max: int = cm.get("per_symbol_max_open_positions", 2)
        if risk_config is not None:
            rc_per_symbol = getattr(risk_config, "max_open_plays_per_symbol", None)
            if rc_per_symbol is not None:
                per_symbol_max = int(rc_per_symbol)

        if symbol:
            symbol_count = self.count_active_plays(symbol)
            if symbol_count >= per_symbol_max:
                return False, (f"per-symbol limit={per_symbol_max} reached for {symbol} (current={symbol_count})")

        # ------------------------------------------------------------------ #
        # 3. Per-playbook total open plays                                     #
        # ------------------------------------------------------------------ #
        if risk_config is not None:
            max_open_plays = getattr(risk_config, "max_open_plays", None)
            if max_open_plays is not None:
                total = self.count_active_plays()
                if total >= max_open_plays:
                    return False, (f"playbook max_open_plays={max_open_plays} reached (current={total})")

        # ------------------------------------------------------------------ #
        # 4. Per-trade max contracts                                           #
        # ------------------------------------------------------------------ #
        if risk_config is not None:
            max_contracts = getattr(risk_config, "max_contracts_per_play", None)
            if max_contracts is not None and contracts > max_contracts:
                return False, (f"contracts={contracts} exceeds max_contracts_per_play={max_contracts}")

        # Compute estimated trade cost (used for checks 5–8)
        estimated_cost = self.estimate_trade_cost(play)

        # ------------------------------------------------------------------ #
        # 5. Per-trade fixed dollar limit                                      #
        # ------------------------------------------------------------------ #
        if risk_config is not None:
            fixed_limit = getattr(risk_config, "max_capital_per_trade_fixed", None)
            if fixed_limit is not None and estimated_cost > 0 and estimated_cost > fixed_limit:
                return False, (f"estimated_cost=${estimated_cost:.2f} exceeds max_capital_per_trade_fixed=${fixed_limit:.2f}")

        # ------------------------------------------------------------------ #
        # 6. Per-trade % of equity                                             #
        # ------------------------------------------------------------------ #
        if risk_config is not None and self._account_loaded and self._equity > 0:
            pct_limit = getattr(risk_config, "max_capital_per_trade_pct", None)
            if pct_limit is not None and estimated_cost > 0:
                trade_pct = (estimated_cost / self._equity) * 100.0
                if trade_pct > pct_limit:
                    return False, (f"trade is {trade_pct:.1f}% of equity, exceeds max_capital_per_trade_pct={pct_limit}%")

        # ------------------------------------------------------------------ #
        # 7. Global max capital deployed %                                     #
        # ------------------------------------------------------------------ #
        max_deployed_pct = cm.get("max_capital_deployed_pct")
        if max_deployed_pct is not None and self._account_loaded and self._equity > 0:
            total_deployed = self._get_total_deployed()
            deployed_pct = (total_deployed / self._equity) * 100.0
            if deployed_pct >= max_deployed_pct:
                return False, (f"capital deployed {deployed_pct:.1f}% >= max_capital_deployed_pct={max_deployed_pct}%")

        # ------------------------------------------------------------------ #
        # 8. Buying-power headroom                                             #
        # ------------------------------------------------------------------ #
        if self._account_loaded and self._buying_power > 0 and estimated_cost > 0:
            reserve_pct = cm.get("buying_power_reserve_pct", 5.0) / 100.0
            available_bp = self._buying_power * (1.0 - reserve_pct)
            if estimated_cost > available_bp:
                return False, (
                    f"estimated_cost=${estimated_cost:.2f} > available buying power ${available_bp:.2f} (reserve={reserve_pct * 100:.0f}%)"
                )

        return True, "ok"

    # =========================================================================
    # Status / diagnostics
    # =========================================================================

    def get_summary(self) -> dict[str, Any]:
        """Return a snapshot dict suitable for logging or TUI display."""
        active = self.count_active_plays() if self._active_plays_cache is not None else "not_cached"
        return {
            "buying_power": self._buying_power,
            "equity": self._equity,
            "portfolio_value": self._portfolio_value,
            "account_loaded": self._account_loaded,
            "active_plays": active,
            "capital_management_enabled": self._cm_config.get("enabled", True),
        }

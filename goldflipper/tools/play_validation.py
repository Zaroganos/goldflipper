"""Utilities for validating option plays parsed by the CSV ingestor."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

from goldflipper.data.market.errors import MarketDataError
from goldflipper.data.market.manager import MarketDataManager
from goldflipper.tools.play_creation_tool import clean_ticker_symbol

LOGGER = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Container for play validation feedback."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


class PlayValidator:
    """Performs structural and market-data backed validation for option plays."""

    def __init__(
        self,
        market_manager: Optional[MarketDataManager] = None,
        enable_market_checks: bool = True,
        min_days_warning: Optional[int] = None,
        earnings_validation_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._symbol_cache: Dict[str, Dict[str, Optional[str]]] = {}
        self._contract_cache: Dict[str, Dict[str, Optional[str]]] = {}
        self._initialization_error: Optional[str] = None
        self._market_manager: Optional[MarketDataManager] = None
        self._enable_market_checks = enable_market_checks
        self._min_days_warning = min_days_warning
        self._earnings_config: Dict[str, Any] = {}
        self._earnings_enabled: bool = False

        if enable_market_checks:
            try:
                self._market_manager = market_manager or MarketDataManager()
            except Exception as exc:  # pragma: no cover - initialization failures are rare but handled
                self._initialization_error = str(exc)
                self._market_manager = None
                self._enable_market_checks = False
                LOGGER.warning(
                    "Market data validation disabled: unable to initialize MarketDataManager (%s)",
                    exc,
                )

        if earnings_validation_config is not None:
            self.configure_earnings_validation(earnings_validation_config)

    def configure_earnings_validation(self, earnings_validation_config: Optional[Dict[str, Any]]) -> None:
        """Configure earnings-based validation behavior.

        This is separated from __init__ to keep constructor arguments simple; callers
        can pass a config dict and enable/disable earnings checks here.
        """
        config = earnings_validation_config or {}
        self._earnings_config = config
        self._earnings_enabled = bool(config.get("enabled", False))

    def validate_play(self, play: Dict, context: str) -> ValidationResult:
        """Validate a play dictionary, returning collected errors and warnings."""

        result = ValidationResult()

        raw_symbol = play.get("symbol")
        symbol = clean_ticker_symbol(str(raw_symbol)) if raw_symbol else ""
        trade_type = str(play.get("trade_type", "")).upper()
        option_symbol = str(play.get("option_contract_symbol", ""))
        strike_value_raw = play.get("strike_price")
        expiration_value = play.get("expiration_date")

        if not symbol:
            result.errors.append(f"{context}: Missing ticker symbol.")
        if trade_type not in {"CALL", "PUT"}:
            result.errors.append(f"{context}: trade_type must be CALL or PUT (found '{trade_type}').")
        if not option_symbol:
            result.errors.append(f"{context}: Missing option_contract_symbol.")

        strike_numeric: Optional[float] = None
        if strike_value_raw is None:
            result.errors.append(f"{context}: Missing strike_price.")
        else:
            try:
                strike_numeric = float(strike_value_raw)
            except (TypeError, ValueError):
                result.errors.append(
                    f"{context}: strike_price '{strike_value_raw}' is not a valid number."
                )

        contract_expiry_dt: Optional[datetime] = None
        if expiration_value:
            try:
                contract_expiry_dt = datetime.strptime(str(expiration_value), "%m/%d/%Y")
            except ValueError:
                result.errors.append(
                    f"{context}: Expiration date '{expiration_value}' is not MM/DD/YYYY."
                )
        else:
            result.errors.append(f"{context}: Missing expiration_date.")

        # Validate expiration_date (GTE) - error if today or past, warning if too soon
        today = datetime.utcnow().date()
        if contract_expiry_dt is not None:
            contract_expiry_date_only = contract_expiry_dt.date()
            if contract_expiry_date_only <= today:
                result.errors.append(
                    f"{context}: Expiration date (GTE) '{expiration_value}' is today or in the past."
                )
            elif self._min_days_warning is not None:
                days_until_expiry = (contract_expiry_date_only - today).days
                if days_until_expiry < self._min_days_warning:
                    result.warnings.append(
                        f"{context}: Expiration date (GTE) '{expiration_value}' is less than {self._min_days_warning} days away ({days_until_expiry} days)."
                    )

        # Validate play_expiration_date (GTD) - required field, error if missing, today or past, warning if too soon
        play_expiration_value = play.get("play_expiration_date")
        play_expiry_dt: Optional[datetime] = None
        if not play_expiration_value:
            result.errors.append(f"{context}: Missing play_expiration_date (GTD). GTD date is required.")
        else:
            try:
                play_expiry_dt = datetime.strptime(str(play_expiration_value), "%m/%d/%Y")
                play_expiry_date_only = play_expiry_dt.date()
                if play_expiry_date_only <= today:
                    result.errors.append(
                        f"{context}: Play expiration date (GTD) '{play_expiration_value}' is today or in the past."
                    )
                elif self._min_days_warning is not None:
                    days_until_play_expiry = (play_expiry_date_only - today).days
                    if days_until_play_expiry < self._min_days_warning:
                        result.warnings.append(
                            f"{context}: Play expiration date (GTD) '{play_expiration_value}' is less than {self._min_days_warning} days away ({days_until_play_expiry} days)."
                        )
            except ValueError:
                result.errors.append(
                    f"{context}: Play expiration date (GTD) '{play_expiration_value}' is not MM/DD/YYYY."
                )

        contracts_value = play.get("contracts")
        if contracts_value is None:
            result.errors.append(f"{context}: Missing contracts value.")
        else:
            try:
                if int(contracts_value) <= 0:
                    result.errors.append(
                        f"{context}: contracts must be a positive integer (found '{contracts_value}')."
                    )
            except (TypeError, ValueError):
                result.errors.append(
                    f"{context}: contracts '{contracts_value}' is not a valid integer."
                )

        if option_symbol:
            result.errors.extend(
                self._validate_contract_structure(
                    option_symbol,
                    symbol,
                    trade_type,
                    strike_numeric,
                    contract_expiry_dt,
                    context,
                )
            )

        if not self._enable_market_checks:
            warning_msg = (
                f"{context}: Market data validation skipped"
                + (f" ({self._initialization_error})." if self._initialization_error else ".")
            )
            result.warnings.append(warning_msg)
            return result

        if self._market_manager is None:
            result.warnings.append(f"{context}: Market data validation unavailable.")
            return result

        if symbol:
            sym_errors, sym_warnings = self._validate_symbol_with_market_data(symbol, context)
            result.errors.extend(sym_errors)
            result.warnings.extend(sym_warnings)

            if self._earnings_enabled:
                earnings_errors, earnings_warnings = self._validate_earnings_window(
                    symbol, contract_expiry_dt, play_expiry_dt, context
                )
                result.errors.extend(earnings_errors)
                result.warnings.extend(earnings_warnings)

        if option_symbol:
            opt_errors, opt_warnings = self._validate_option_with_market_data(option_symbol, context)
            result.errors.extend(opt_errors)
            result.warnings.extend(opt_warnings)

        return result

    def _validate_earnings_window(
        self,
        symbol: str,
        contract_expiry_dt: Optional[datetime],
        play_expiry_dt: Optional[datetime],
        context: str,
    ) -> Tuple[List[str], List[str]]:
        """Validate risk from upcoming earnings within the play's active window.

        Uses MarketDataManager.get_next_earnings_date (via MarketDataApp) to find the
        next earnings date and compares it against:
        - A configured max_days_before_earnings threshold; and
        - The play's active window: today through min(GTE, GTD), when both are known.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not self._market_manager:
            return errors, warnings

        days_threshold = self._earnings_config.get("max_days_before_earnings")
        if not isinstance(days_threshold, int) or days_threshold <= 0:
            # Misconfigured or effectively disabled
            return errors, warnings

        severity = str(self._earnings_config.get("severity", "warning")).lower()
        if severity not in {"warning", "error"}:
            severity = "warning"

        try:
            next_earnings = self._market_manager.get_next_earnings_date(symbol)
        except Exception as exc:  # pragma: no cover - defensive catch
            warnings.append(
                f"{context}: Unable to check upcoming earnings for {symbol}: {exc}"
            )
            return errors, warnings

        if not next_earnings:
            return errors, warnings

        today = datetime.utcnow().date()
        if contract_expiry_dt is None or play_expiry_dt is None:
            # Date fields are already validated elsewhere; if they are missing or invalid,
            # the corresponding errors have been recorded and we skip earnings window logic.
            return errors, warnings

        window_end = min(contract_expiry_dt.date(), play_expiry_dt.date())
        if next_earnings > window_end:
            # Earnings occurs after this play's exposure window
            return errors, warnings

        days_until_earnings = (next_earnings - today).days
        if days_until_earnings <= days_threshold:
            msg = (
                f"{context}: Upcoming earnings for {symbol} on {next_earnings.isoformat()} "
                f"is {days_until_earnings} days away and falls within the play window "
                f"ending {window_end.isoformat()} (threshold: {days_threshold} days)."
            )
            if severity == "error":
                errors.append(msg)
            else:
                warnings.append(msg)

        return errors, warnings

    def _validate_contract_structure(
        self,
        option_symbol: str,
        symbol: str,
        trade_type: str,
        strike_numeric: Optional[float],
        contract_expiry_dt: Optional[datetime],
        context: str,
    ) -> List[str]:
        errors: List[str] = []

        if len(option_symbol) < 15:
            errors.append(
                f"{context}: Option contract '{option_symbol}' is too short to follow OCC format."
            )
            return errors

        root = option_symbol[:-15]
        date_part = option_symbol[-15:-9]
        option_type = option_symbol[-9:-8]
        strike_fragment = option_symbol[-8:]

        if symbol and root != symbol:
            errors.append(
                f"{context}: Contract root '{root}' does not match symbol '{symbol}'."
            )

        if trade_type in {"CALL", "PUT"}:
            expected_cp = "C" if trade_type == "CALL" else "P"
            if option_type != expected_cp:
                errors.append(
                    f"{context}: Contract type '{option_type}' does not match trade_type '{trade_type}'."
                )

        if contract_expiry_dt is not None:
            expected_date = contract_expiry_dt.strftime("%y%m%d")
            if date_part != expected_date:
                errors.append(
                    f"{context}: Contract expiration '{date_part}' does not match play expiration '{contract_expiry_dt.strftime('%m/%d/%Y')}'."
                )

        if strike_numeric is not None:
            try:
                strike_from_contract = int(strike_fragment) / 1000.0
            except ValueError:
                errors.append(
                    f"{context}: Contract strike fragment '{strike_fragment}' is not numeric."
                )
            else:
                if not math.isclose(
                    strike_numeric,
                    strike_from_contract,
                    rel_tol=1e-4,
                    abs_tol=1e-3,
                ):
                    errors.append(
                        f"{context}: Contract strike {strike_from_contract:.3f} does not match play strike {strike_numeric:.3f}."
                    )

        return errors

    def _validate_symbol_with_market_data(self, symbol: str, context: str) -> Tuple[List[str], List[str]]:
        cached = self._symbol_cache.get(symbol)
        if cached:
            status = cached.get("status")
            message = cached.get("message")
            if status == "valid":
                return [], []
            if status == "invalid" and message:
                return [f"{context}: {message}"], []
            if status == "warning" and message:
                return [], [f"{context}: {message}"]

        try:
            price = self._market_manager.get_stock_price(symbol)
        except MarketDataError as exc:
            message = f"Unable to verify ticker {symbol}: {exc}"
            self._symbol_cache[symbol] = {"status": "warning", "message": message}
            return [], [f"{context}: {message}"]
        except Exception as exc:  # pragma: no cover - defensive catch
            message = f"Unexpected error while verifying ticker {symbol}: {exc}"
            self._symbol_cache[symbol] = {"status": "warning", "message": message}
            return [], [f"{context}: {message}"]

        if price is None:
            message = f"Market data returned no price for ticker {symbol}."
            self._symbol_cache[symbol] = {"status": "invalid", "message": message}
            return [f"{context}: {message}"], []

        if price <= 0:
            message = f"Market data returned non-positive price ({price}) for ticker {symbol}."
            self._symbol_cache[symbol] = {"status": "invalid", "message": message}
            return [f"{context}: {message}"], []

        self._symbol_cache[symbol] = {"status": "valid", "message": None}
        return [], []

    def _validate_option_with_market_data(
        self, option_symbol: str, context: str
    ) -> Tuple[List[str], List[str]]:
        cached = self._contract_cache.get(option_symbol)
        if cached:
            status = cached.get("status")
            message = cached.get("message")
            if status == "valid":
                return [], []
            if status == "invalid" and message:
                return [f"{context}: {message}"], []
            if status == "warning" and message:
                return [], [f"{context}: {message}"]

        try:
            quote = self._market_manager.get_option_quote(option_symbol)
        except MarketDataError as exc:
            message = f"Unable to verify option {option_symbol}: {exc}"
            self._contract_cache[option_symbol] = {"status": "warning", "message": message}
            return [], [f"{context}: {message}"]
        except Exception as exc:  # pragma: no cover - defensive catch
            message = f"Unexpected error while verifying option {option_symbol}: {exc}"
            self._contract_cache[option_symbol] = {"status": "warning", "message": message}
            return [], [f"{context}: {message}"]

        if not quote:
            message = (
                f"Market data returned no quote for option {option_symbol}. Verify contract details."
            )
            self._contract_cache[option_symbol] = {"status": "invalid", "message": message}
            return [f"{context}: {message}"], []

        errors: List[str] = []
        warnings: List[str] = []

        volume = quote.get('volume')
        open_interest = quote.get('open_interest')
        if volume is not None and volume == 0:
            warnings.append(
                f"{context}: Option {option_symbol} has zero reported volume; check liquidity."
            )
        if open_interest is not None and open_interest == 0:
            warnings.append(
                f"{context}: Option {option_symbol} has zero open interest; confirm availability."
            )

        self._contract_cache[option_symbol] = {"status": "valid", "message": None}
        return errors, warnings

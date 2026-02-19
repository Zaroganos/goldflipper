"""
Startup Self-Tests Module

Provides provider-aware self-tests that run at system startup to verify connectivity
and configuration. Tests are run based on which market data providers are enabled,
with different failure handling for primary vs fallback providers.

Configuration: startup_self_tests section in settings.yaml
"""

import logging
import os
import sys
from datetime import datetime
from enum import Enum
from typing import Any

import requests
import yfinance as yf

from goldflipper.utils.logging_setup import configure_logging

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from goldflipper.alpaca_client import get_alpaca_client
from goldflipper.config.config import config


class TestSeverity(Enum):
    """Severity level for test failures."""

    ERROR = "error"  # Critical - blocks trading
    WARNING = "warn"  # Non-critical - trading can continue
    INFO = "info"  # Informational only


class StartupTestRunner:
    """
    Provider-aware startup test runner that checks which market data providers
    are enabled and runs appropriate tests with configurable failure handling.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._test_config = self._load_test_config()
        self._provider_config = self._load_provider_config()

    def _load_test_config(self) -> dict[str, Any]:
        """Load startup self-test configuration."""
        default_config = {
            "enabled": True,
            "on_primary_failure": "error",
            "on_fallback_failure": "warn",
            "on_brokerage_failure": "error",
            "pause_on_error": True,
            "tests": {
                "alpaca_sdk": {"enabled": True},
                "alpaca_api": {"enabled": True},
                "marketdataapp": {"enabled": "auto"},
                "yfinance": {"enabled": "auto"},
                "alpaca_market_data": {"enabled": "auto"},
            },
        }

        try:
            user_config = config.get("startup_self_tests", default={})
            if isinstance(user_config, dict):
                # Merge user config with defaults
                for key, value in user_config.items():
                    if key == "tests" and isinstance(value, dict):
                        for test_name, test_cfg in value.items():
                            if test_name in default_config["tests"]:
                                default_config["tests"][test_name].update(test_cfg)
                            else:
                                default_config["tests"][test_name] = test_cfg
                    else:
                        default_config[key] = value
            return default_config
        except Exception as e:
            self.logger.warning(f"Failed to load startup_self_tests config: {e}, using defaults")
            return default_config

    def _load_provider_config(self) -> dict[str, Any]:
        """Load market data provider configuration."""
        try:
            mdp_config = config.get("market_data_providers", default={})
            return {
                "primary_provider": mdp_config.get("primary_provider", "marketdataapp"),
                "providers": mdp_config.get("providers", {}),
                "fallback_order": mdp_config.get("fallback", {}).get("order", []),
            }
        except Exception as e:
            self.logger.warning(f"Failed to load market_data_providers config: {e}")
            return {
                "primary_provider": "marketdataapp",
                "providers": {},
                "fallback_order": [],
            }

    def _is_provider_enabled(self, provider_name: str) -> bool:
        """Check if a market data provider is enabled in config."""
        providers = self._provider_config.get("providers", {})
        provider_cfg = providers.get(provider_name, {})
        return provider_cfg.get("enabled", False)

    def _is_primary_provider(self, provider_name: str) -> bool:
        """Check if a provider is the primary market data provider."""
        return self._provider_config.get("primary_provider", "") == provider_name

    def _should_run_test(self, test_name: str) -> bool:
        """Determine if a test should run based on config."""
        if not self._test_config.get("enabled", True):
            return False

        test_cfg = self._test_config.get("tests", {}).get(test_name, {})
        enabled = test_cfg.get("enabled", True)

        if enabled == "auto":
            # Auto-determine based on provider config
            provider_map = {
                "marketdataapp": "marketdataapp",
                "yfinance": "yfinance",
                "alpaca_market_data": "alpaca",
            }
            provider_name = provider_map.get(test_name)
            if provider_name:
                return self._is_provider_enabled(provider_name)
            return True

        return bool(enabled)

    def _get_test_severity(self, test_name: str) -> TestSeverity:
        """Get the severity level for a test failure."""
        # Brokerage tests (Alpaca)
        if test_name in ("alpaca_sdk", "alpaca_api"):
            behavior = self._test_config.get("on_brokerage_failure", "error")
            return TestSeverity.ERROR if behavior == "error" else TestSeverity.WARNING

        # Market data provider tests
        provider_map = {
            "marketdataapp": "marketdataapp",
            "yfinance": "yfinance",
            "alpaca_market_data": "alpaca",
        }

        provider_name = provider_map.get(test_name)
        if provider_name:
            if self._is_primary_provider(provider_name):
                behavior = self._test_config.get("on_primary_failure", "error")
            else:
                behavior = self._test_config.get("on_fallback_failure", "warn")
            return TestSeverity.ERROR if behavior == "error" else TestSeverity.WARNING

        # Default to error for unknown tests
        return TestSeverity.ERROR

    def get_pause_on_error(self) -> bool:
        """Check if we should pause on critical errors."""
        return self._test_config.get("pause_on_error", True)


# =============================================================================
# Individual Test Functions
# =============================================================================


def test_alpaca_connection() -> tuple[bool, Any]:
    """Test Alpaca API connectivity and account status via SDK."""
    try:
        client = get_alpaca_client()
        account = client.get_account()

        # Basic account validation
        if not account:
            return False, "Could not retrieve account information"

        # Check if account is active
        if account.status != "ACTIVE":
            return False, f"Account status is {account.status}, not ACTIVE"

        # Check trading capabilities
        if not account.trading_blocked and account.account_blocked:
            return False, "Account is blocked from trading"

        return True, {
            "account_id": account.id,
            "cash": account.cash,
            "options_level": account.options_trading_level,
            "pattern_day_trader": account.pattern_day_trader,
        }

    except Exception as e:
        return False, f"Alpaca SDK test failed: {str(e)}"


def test_alpaca_api_direct() -> tuple[bool, Any]:
    """Test Alpaca API connectivity directly using HTTP request."""
    try:
        # Get the active account details
        active_account = config.get("alpaca", "active_account")
        accounts = config.get("alpaca", "accounts")
        if active_account not in accounts:
            return False, f"Active account '{active_account}' not found in configuration"

        account = accounts[active_account]

        # Get credentials for the active account
        api_key = account["api_key"]
        secret_key = account["secret_key"]
        base_url = account["base_url"]

        # Set up headers
        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}

        response = requests.get(f"{base_url}/account", headers=headers, timeout=10)

        if response.status_code == 200:
            account_data = response.json()
            nickname = account.get("nickname", active_account.replace("_", " ").title())
            return True, {
                "account": nickname,
                "status_code": response.status_code,
                "account_status": account_data.get("status"),
                "currency": account_data.get("currency"),
                "cash": account_data.get("cash"),
                "portfolio_value": account_data.get("portfolio_value"),
            }
        else:
            return False, f"API request failed with status code: {response.status_code}, Response: {response.text}"

    except Exception as e:
        return False, f"Direct API test failed: {str(e)}"


def test_marketdata_api() -> tuple[bool, Any]:
    """Test MarketData.app API connectivity and service status."""
    try:
        response = requests.get("https://api.marketdata.app/status/", timeout=10)

        if response.status_code != 200:
            return False, f"MarketData.app API returned status code: {response.status_code}"

        data = response.json()

        # First check if we got a valid response
        if data.get("s") != "ok":
            return False, "MarketData.app API returned non-ok status"

        # Look for the two specific API services we care about
        services = data.get("service", [])
        online_statuses = data.get("online", [])

        # Success if we got a valid response with services
        if not services or not online_statuses:
            return False, "Could not retrieve service information"

        return True, {"services": list(zip(services, online_statuses, strict=False))}

    except Exception as e:
        return False, f"MarketData.app API test failed: {str(e)}"


def test_yfinance() -> tuple[bool, Any]:
    """Test yfinance connectivity by fetching SPY data."""
    try:
        # Test with SPY as it's highly reliable
        ticker = yf.Ticker("SPY")

        # Get basic info (this is the quickest test)
        hist = ticker.history(period="1d")

        if hist.empty:
            return False, "Could not retrieve historical data from yfinance"

        return True, {"rows_retrieved": len(hist), "latest_close": float(hist["Close"].iloc[-1]) if not hist.empty else None, "status": "connected"}

    except Exception as e:
        return False, f"yfinance test failed: {str(e)}"


def test_alpaca_market_data() -> tuple[bool, Any]:
    """Test Alpaca market data API connectivity."""
    try:
        # Use the Alpaca data API to get a simple quote
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest

        # Get credentials
        active_account = config.get("alpaca", "active_account")
        accounts = config.get("alpaca", "accounts")
        if active_account not in accounts:
            return False, f"Active account '{active_account}' not found"

        account = accounts[active_account]
        api_key = account["api_key"]
        secret_key = account["secret_key"]

        # Create data client and fetch quote
        data_client = StockHistoricalDataClient(api_key, secret_key)
        request = StockLatestQuoteRequest(symbol_or_symbols="SPY")
        quote = data_client.get_stock_latest_quote(request)

        if quote and "SPY" in quote:
            spy_quote = quote["SPY"]
            return True, {
                "symbol": "SPY",
                "bid_price": float(spy_quote.bid_price) if spy_quote.bid_price else None,
                "ask_price": float(spy_quote.ask_price) if spy_quote.ask_price else None,
                "status": "connected",
            }
        else:
            return False, "Could not retrieve quote data from Alpaca"

    except ImportError as e:
        return False, f"Alpaca data library not available: {str(e)}"
    except Exception as e:
        return False, f"Alpaca market data test failed: {str(e)}"


# =============================================================================
# Main Test Runner Function
# =============================================================================


def run_startup_tests() -> dict[str, Any]:
    """
    Run provider-aware startup tests and return comprehensive results.

    Tests are run based on which market data providers are enabled in config.
    Primary provider failures are treated as errors, fallback provider failures
    as warnings (configurable).

    Returns:
        Dictionary containing:
        - timestamp: When tests were run
        - tests: Dict of test results with success, result, severity, is_primary
        - all_passed: True if all tests passed
        - critical_failures: List of tests that failed with ERROR severity
        - warnings: List of tests that failed with WARNING severity
        - should_block_trading: True if any ERROR severity tests failed
    """
    runner = StartupTestRunner()
    logging.info("Running provider-aware startup self-tests...")

    test_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {},
        "critical_failures": [],
        "warnings": [],
        "should_block_trading": False,
        "pause_on_error": runner.get_pause_on_error(),
    }

    # Define test functions and their names
    test_functions = {
        "alpaca_sdk": test_alpaca_connection,
        "alpaca_api": test_alpaca_api_direct,
        "marketdataapp": test_marketdata_api,
        "yfinance": test_yfinance,
        "alpaca_market_data": test_alpaca_market_data,
    }

    # Run tests based on configuration
    for test_name, test_func in test_functions.items():
        if not runner._should_run_test(test_name):
            logging.debug(f"Skipping disabled test: {test_name}")
            continue

        logging.info(f"Running test: {test_name}")

        try:
            success, result = test_func()
        except Exception as e:
            success = False
            result = f"Test raised unexpected exception: {str(e)}"

        severity = runner._get_test_severity(test_name)
        is_primary = runner._is_primary_provider(
            {"marketdataapp": "marketdataapp", "yfinance": "yfinance", "alpaca_market_data": "alpaca"}.get(test_name, "")
        )

        test_results["tests"][test_name] = {
            "success": success,
            "result": result,
            "severity": severity.value,
            "is_primary_provider": is_primary,
        }

        if not success:
            if severity == TestSeverity.ERROR:
                test_results["critical_failures"].append(test_name)
                test_results["should_block_trading"] = True
                logging.error(f"CRITICAL: {test_name} test FAILED - {result}")
            else:
                test_results["warnings"].append(test_name)
                logging.warning(f"WARNING: {test_name} test failed - {result}")
        else:
            logging.info(f"{test_name} test PASSED")

    # Overall status
    test_results["all_passed"] = all(test["success"] for test in test_results["tests"].values())

    return test_results


def format_test_results(results: dict[str, Any], use_colors: bool = True) -> str:
    """
    Format test results for display.

    Args:
        results: Test results dictionary from run_startup_tests()
        use_colors: Whether to use ANSI color codes

    Returns:
        Formatted string for display
    """
    lines = []

    # Color codes
    if use_colors:
        GREEN = "\033[92m"
        RED = "\033[91m"
        YELLOW = "\033[93m"
        RESET = "\033[0m"
        BOLD = "\033[1m"
    else:
        GREEN = RED = YELLOW = RESET = BOLD = ""

    lines.append(f"\n{BOLD}Startup Self-Test Results:{RESET}")
    lines.append("=" * 60)

    for test_name, test_data in results["tests"].items():
        success = test_data["success"]
        severity = test_data.get("severity", "error")
        is_primary = test_data.get("is_primary_provider", False)

        if success:
            status = f"{GREEN}PASSED{RESET}"
        elif severity == "error":
            status = f"{RED}FAILED (CRITICAL){RESET}"
        else:
            status = f"{YELLOW}FAILED (WARNING){RESET}"

        provider_tag = " [PRIMARY]" if is_primary else ""
        lines.append(f"\n{BOLD}{test_name.upper()}{RESET}{provider_tag}")
        lines.append(f"  Status: {status}")
        lines.append(f"  Details: {test_data['result']}")

    lines.append("\n" + "=" * 60)

    if results["all_passed"]:
        lines.append(f"{GREEN}{BOLD}All Tests Passed!{RESET}")
    else:
        if results["critical_failures"]:
            lines.append(f"{RED}{BOLD}CRITICAL FAILURES:{RESET} {', '.join(results['critical_failures'])}")
            lines.append(f"{RED}Trading will NOT start due to critical test failures.{RESET}")
        if results["warnings"]:
            lines.append(f"{YELLOW}{BOLD}WARNINGS:{RESET} {', '.join(results['warnings'])}")
            lines.append(f"{YELLOW}Trading can continue but some features may be degraded.{RESET}")

    return "\n".join(lines)


if __name__ == "__main__":
    configure_logging(console_mode=True)
    results = run_startup_tests()

    print(format_test_results(results, use_colors=True))

    if results["should_block_trading"]:
        print("\n" + "=" * 60)
        print("Press Enter to exit...")
        input()

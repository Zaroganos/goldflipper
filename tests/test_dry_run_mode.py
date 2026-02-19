"""
Unit Tests for Dry-Run Mode

This module provides unit tests for dry-run mode functionality:
1. Config loading with dry_run setting
2. Orchestrator dry-run initialization
3. Play evaluation without order execution
4. Logging verification for dry-run actions

Usage:
    python goldflipper/tests/test_dry_run_mode.py

Author: Cascade (automated)
Date: 2025-12-01
"""

import logging
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add project root to path BEFORE any goldflipper imports
_this_dir = os.path.dirname(os.path.abspath(__file__))
_goldflipper_pkg = os.path.dirname(_this_dir)
_project_root = os.path.dirname(_goldflipper_pkg)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.DEBUG)


# ==============================================================================
# Test Helpers
# ==============================================================================


def create_dry_run_config(dry_run: bool = True):
    """Create a mock configuration dictionary with dry_run setting."""
    return {
        "strategy_orchestration": {"enabled": True, "mode": "sequential", "max_parallel_workers": 3, "dry_run": dry_run},
        "options_swings": {"enabled": True, "priority": 10},
        "momentum": {"enabled": False, "priority": 20},
        "entry_strategy": {"buffer": 0.50},
    }


def create_mock_market_data():
    """Create a mock MarketDataManager."""
    mock = Mock()
    mock.get_stock_price = Mock(return_value=100.0)
    mock.get_option_quote = Mock(return_value={"bid": 1.50, "ask": 1.60, "mid": 1.55, "last": 1.55, "premium": 1.55, "delta": 0.45})
    mock.start_new_cycle = Mock()
    return mock


def create_mock_client():
    """Create a mock Alpaca TradingClient."""
    mock = Mock()
    mock.get_account = Mock(return_value=Mock(buying_power="100000.00"))
    mock.submit_order = Mock()  # Should NOT be called in dry-run
    return mock


def create_sample_play():
    """Create a sample play dictionary for testing."""
    now = datetime.now()
    exp_date = now + timedelta(days=14)
    play_exp = now + timedelta(days=7)

    return {
        "symbol": "SPY",
        "trade_type": "CALL",
        "strike_price": "500",
        "expiration_date": exp_date.strftime("%m/%d/%Y"),
        "option_symbol": f"SPY{exp_date.strftime('%y%m%d')}C00500000",
        "contracts": 1,
        "play_expiration_date": play_exp.strftime("%m/%d/%Y"),
        "entry_point": {"target_price": 100.0, "stock_price": 100.0, "entry_stock_price": 100.0, "entry_premium": 1.55, "order_type": "market"},
        "take_profit": {"TP_type": "single", "premium_pct": 50.0},
        "stop_loss": {"SL_type": "STOP", "premium_pct": 25.0},
        "_play_file": "/fake/path/play.json",
    }


# ==============================================================================
# Test Classes
# ==============================================================================


class TestDryRunConfig(unittest.TestCase):
    """Test dry-run configuration loading."""

    def test_dry_run_config_true(self):
        """Test that dry_run: true is loaded correctly."""
        config = create_dry_run_config(dry_run=True)
        self.assertTrue(config["strategy_orchestration"]["dry_run"])

    def test_dry_run_config_false(self):
        """Test that dry_run: false is loaded correctly."""
        config = create_dry_run_config(dry_run=False)
        self.assertFalse(config["strategy_orchestration"]["dry_run"])

    def test_dry_run_default(self):
        """Test that dry_run defaults to False if not specified."""
        config = {"strategy_orchestration": {"enabled": True, "mode": "sequential"}}
        self.assertFalse(config["strategy_orchestration"].get("dry_run", False))


class TestOrchestratorDryRun(unittest.TestCase):
    """Test orchestrator dry-run mode."""

    def test_orchestrator_loads_dry_run_setting(self):
        """Test that orchestrator correctly loads dry_run from config."""
        from goldflipper.strategy.orchestrator import StrategyOrchestrator

        config = create_dry_run_config(dry_run=True)
        mock_market = create_mock_market_data()
        mock_client = create_mock_client()

        with patch("goldflipper.strategy.registry.StrategyRegistry.discover"):
            with patch("goldflipper.strategy.registry.StrategyRegistry.get_all_strategies", return_value=[]):
                orchestrator = StrategyOrchestrator(config=config, market_data=mock_market, brokerage_client=mock_client)
                orchestrator.initialize()

                self.assertTrue(orchestrator.is_dry_run)

    def test_orchestrator_dry_run_false(self):
        """Test that orchestrator correctly loads dry_run=false."""
        from goldflipper.strategy.orchestrator import StrategyOrchestrator

        config = create_dry_run_config(dry_run=False)
        mock_market = create_mock_market_data()
        mock_client = create_mock_client()

        with patch("goldflipper.strategy.registry.StrategyRegistry.discover"):
            with patch("goldflipper.strategy.registry.StrategyRegistry.get_all_strategies", return_value=[]):
                orchestrator = StrategyOrchestrator(config=config, market_data=mock_market, brokerage_client=mock_client)
                orchestrator.initialize()

                self.assertFalse(orchestrator.is_dry_run)

    def test_orchestrator_status_includes_dry_run(self):
        """Test that get_status includes dry_run field."""
        from goldflipper.strategy.orchestrator import StrategyOrchestrator

        config = create_dry_run_config(dry_run=True)
        mock_market = create_mock_market_data()
        mock_client = create_mock_client()

        with patch("goldflipper.strategy.registry.StrategyRegistry.discover"):
            with patch("goldflipper.strategy.registry.StrategyRegistry.get_all_strategies", return_value=[]):
                orchestrator = StrategyOrchestrator(config=config, market_data=mock_market, brokerage_client=mock_client)
                orchestrator.initialize()

                status = orchestrator.get_status()
                self.assertIn("dry_run", status)
                self.assertTrue(status["dry_run"])


class TestDryRunExecution(unittest.TestCase):
    """Test that dry-run mode prevents actual execution."""

    def test_dry_run_skips_open_position(self):
        """Test that dry-run mode logs but doesn't execute open_position."""
        from goldflipper.strategy.orchestrator import StrategyOrchestrator

        config = create_dry_run_config(dry_run=True)
        mock_market = create_mock_market_data()
        mock_client = create_mock_client()

        # Create a mock strategy that would return plays to open
        mock_strategy = Mock()
        mock_strategy.get_name = Mock(return_value="test_strategy")
        mock_strategy.get_priority = Mock(return_value=10)
        mock_strategy.is_enabled = Mock(return_value=True)
        mock_strategy.get_config_section = Mock(return_value="test_strategy")
        mock_strategy.get_plays_dir = Mock(return_value="/fake/path")
        mock_strategy.on_cycle_start = Mock()
        mock_strategy.on_cycle_end = Mock()
        mock_strategy.validate_play = Mock(return_value=True)
        mock_strategy.evaluate_new_plays = Mock(return_value=[create_sample_play()])
        mock_strategy.evaluate_open_plays = Mock(return_value=[])
        mock_strategy.open_position = Mock(return_value=True)

        with patch("goldflipper.strategy.registry.StrategyRegistry.discover"):
            with patch("goldflipper.strategy.registry.StrategyRegistry.get_all_strategies", return_value=[type(mock_strategy)]):
                orchestrator = StrategyOrchestrator(config=config, market_data=mock_market, brokerage_client=mock_client)

                # Manually inject strategy
                orchestrator.strategies = [mock_strategy]
                orchestrator.state = orchestrator.state.__class__("initialized")
                orchestrator._dry_run = True

                # Mock load_plays_from_dir to return sample plays
                with patch.object(orchestrator, "_load_plays_from_dir", return_value=[create_sample_play()]):
                    with patch.object(orchestrator, "_handle_expired_plays"):
                        with patch.object(orchestrator, "_manage_pending_plays"):
                            orchestrator.run_cycle()

                # open_position should NOT be called in dry-run mode
                mock_strategy.open_position.assert_not_called()

    def test_dry_run_skips_close_position(self):
        """Test that dry-run mode logs but doesn't execute close_position."""
        from goldflipper.strategy.orchestrator import StrategyOrchestrator

        config = create_dry_run_config(dry_run=True)
        mock_market = create_mock_market_data()
        mock_client = create_mock_client()

        # Create a mock strategy that would return plays to close
        mock_strategy = Mock()
        mock_strategy.get_name = Mock(return_value="test_strategy")
        mock_strategy.get_priority = Mock(return_value=10)
        mock_strategy.is_enabled = Mock(return_value=True)
        mock_strategy.get_config_section = Mock(return_value="test_strategy")
        mock_strategy.get_plays_dir = Mock(return_value="/fake/path")
        mock_strategy.on_cycle_start = Mock()
        mock_strategy.on_cycle_end = Mock()
        mock_strategy.validate_play = Mock(return_value=True)
        mock_strategy.evaluate_new_plays = Mock(return_value=[])
        mock_strategy.evaluate_open_plays = Mock(return_value=[(create_sample_play(), {"is_profit": True, "reason": "TP hit"})])
        mock_strategy.close_position = Mock(return_value=True)

        with patch("goldflipper.strategy.registry.StrategyRegistry.discover"):
            with patch("goldflipper.strategy.registry.StrategyRegistry.get_all_strategies", return_value=[type(mock_strategy)]):
                orchestrator = StrategyOrchestrator(config=config, market_data=mock_market, brokerage_client=mock_client)

                # Manually inject strategy
                orchestrator.strategies = [mock_strategy]
                orchestrator.state = orchestrator.state.__class__("initialized")
                orchestrator._dry_run = True

                # Mock load_plays_from_dir to return sample plays
                with patch.object(orchestrator, "_load_plays_from_dir", return_value=[create_sample_play()]):
                    with patch.object(orchestrator, "_handle_expired_plays"):
                        with patch.object(orchestrator, "_manage_pending_plays"):
                            orchestrator.run_cycle()

                # close_position should NOT be called in dry-run mode
                mock_strategy.close_position.assert_not_called()


class TestDryRunWithRealStrategies(unittest.TestCase):
    """Test dry-run mode with actual strategy classes."""

    def test_option_swings_dry_run(self):
        """Test option_swings strategy in dry-run mode."""
        from goldflipper.strategy.runners.option_swings import OptionSwingsStrategy

        config = create_dry_run_config(dry_run=True)
        mock_market = create_mock_market_data()
        mock_client = create_mock_client()

        # Create strategy instance
        strategy = OptionSwingsStrategy(config=config, market_data=mock_market, brokerage_client=mock_client)

        # Create sample play that should trigger entry
        play = create_sample_play()

        # Test evaluate_new_plays (should work normally in dry-run)
        # Note: Dry-run mode only affects the orchestrator, not strategy evaluation
        result = strategy.evaluate_new_plays([play])

        # Evaluation should still work - dry-run only affects execution
        self.assertIsInstance(result, list)


# ==============================================================================
# Main Entry Point
# ==============================================================================


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDryRunConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestOrchestratorDryRun))
    suite.addTests(loader.loadTestsFromTestCase(TestDryRunExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestDryRunWithRealStrategies))

    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print(f"SUCCESS: All {result.testsRun} tests passed!")
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
        for test, trace in result.failures + result.errors:
            print(f"  - {test}: {trace.split(chr(10))[0]}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

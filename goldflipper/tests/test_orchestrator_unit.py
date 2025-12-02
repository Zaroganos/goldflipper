"""
Unit Tests for Strategy Orchestrator and Strategy Logic

This module provides unit tests for:
1. OrderAction, PlayStatus, PositionSide enums
2. StrategyOrchestrator initialization and execution
3. OptionSwingsStrategy entry/exit evaluation

Usage:
    python goldflipper/tests/test_orchestrator_unit_simple.py

Author: Cascade (automated)
Date: 2025-12-01
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, MagicMock, patch

# Add project root to path BEFORE any goldflipper imports
_this_dir = os.path.dirname(os.path.abspath(__file__))
_goldflipper_pkg = os.path.dirname(_this_dir)
_project_root = os.path.dirname(_goldflipper_pkg)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.WARNING)


# ==============================================================================
# Test Helpers
# ==============================================================================

def create_mock_config():
    """Create a mock configuration dictionary."""
    return {
        'strategy_orchestration': {
            'enabled': True,
            'mode': 'sequential',
            'max_parallel_workers': 3,
            'fallback_to_legacy': True
        },
        'options_swings': {
            'enabled': True,
            'priority': 10
        },
        'momentum': {
            'enabled': False,
            'priority': 20
        },
        'entry_strategy': {
            'buffer': 0.50
        }
    }


def create_mock_market_data():
    """Create a mock MarketDataManager."""
    mock = Mock()
    mock.get_stock_price = Mock(return_value=100.0)
    mock.get_option_quote = Mock(return_value={
        'bid': 1.50, 'ask': 1.60, 'mid': 1.55,
        'last': 1.55, 'premium': 1.55, 'delta': 0.45
    })
    mock.start_new_cycle = Mock()
    return mock


def create_mock_client():
    """Create a mock Alpaca TradingClient."""
    mock = Mock()
    mock.get_account = Mock(return_value=Mock(buying_power='100000.00'))
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
        "option_contract_symbol": f"SPY{exp_date.strftime('%y%m%d')}C00500000",
        "contracts": 1,
        "play_expiration_date": play_exp.strftime("%m/%d/%Y"),
        "entry_point": {
            "stock_price": 100.0,
            "entry_stock_price": 100.0,
            "entry_premium": 1.55,
            "order_type": "market"
        },
        "take_profit": {
            "TP_type": "single",
            "stock_price": 105.0,
            "stock_price_pct": 5.0,
            "premium_pct": 50.0,
            "TP_stock_price_target": 105.0,
            "TP_option_prem": 2.325,
            "order_type": "limit at bid",
            "trailing_config": {"enabled": False}
        },
        "stop_loss": {
            "SL_type": "STOP",
            "stock_price": 95.0,
            "stock_price_pct": 5.0,
            "premium_pct": 25.0,
            "SL_stock_price_target": 95.0,
            "SL_option_prem": 1.1625,
            "order_type": "market",
            "trailing_config": {"enabled": False}
        },
        "status": {"play_status": "NEW"}
    }


# ==============================================================================
# Test: OrderAction Enum
# ==============================================================================

class TestOrderAction:
    """Test OrderAction enum functionality."""
    
    def test_order_action_values(self):
        from goldflipper.strategy.base import OrderAction
        assert OrderAction.BUY_TO_OPEN.value == "BTO"
        assert OrderAction.SELL_TO_CLOSE.value == "STC"
        assert OrderAction.SELL_TO_OPEN.value == "STO"
        assert OrderAction.BUY_TO_CLOSE.value == "BTC"
    
    def test_from_string(self):
        from goldflipper.strategy.base import OrderAction
        assert OrderAction.from_string("BTO") == OrderAction.BUY_TO_OPEN
        assert OrderAction.from_string("STC") == OrderAction.SELL_TO_CLOSE
        assert OrderAction.from_string("bto") == OrderAction.BUY_TO_OPEN
        
        # Invalid value should raise
        try:
            OrderAction.from_string("INVALID")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
    
    def test_is_opening_closing(self):
        from goldflipper.strategy.base import OrderAction
        assert OrderAction.BUY_TO_OPEN.is_opening() == True
        assert OrderAction.SELL_TO_OPEN.is_opening() == True
        assert OrderAction.SELL_TO_CLOSE.is_closing() == True
        assert OrderAction.BUY_TO_CLOSE.is_closing() == True
    
    def test_is_long_short(self):
        from goldflipper.strategy.base import OrderAction
        assert OrderAction.BUY_TO_OPEN.is_long() == True
        assert OrderAction.SELL_TO_CLOSE.is_long() == True
        assert OrderAction.SELL_TO_OPEN.is_short() == True
        assert OrderAction.BUY_TO_CLOSE.is_short() == True
    
    def test_get_closing_action(self):
        from goldflipper.strategy.base import OrderAction
        assert OrderAction.BUY_TO_OPEN.get_closing_action() == OrderAction.SELL_TO_CLOSE
        assert OrderAction.SELL_TO_OPEN.get_closing_action() == OrderAction.BUY_TO_CLOSE


# ==============================================================================
# Test: PlayStatus Enum
# ==============================================================================

class TestPlayStatus:
    """Test PlayStatus enum."""
    
    def test_play_status_values(self):
        from goldflipper.strategy.base import PlayStatus
        assert PlayStatus.NEW.value == "NEW"
        assert PlayStatus.OPEN.value == "OPEN"
        assert PlayStatus.CLOSED.value == "CLOSED"
        assert PlayStatus.EXPIRED.value == "EXPIRED"


# ==============================================================================
# Test: PositionSide Enum
# ==============================================================================

class TestPositionSide:
    """Test PositionSide enum."""
    
    def test_from_order_action(self):
        from goldflipper.strategy.base import PositionSide, OrderAction
        assert PositionSide.from_order_action(OrderAction.BUY_TO_OPEN) == PositionSide.LONG
        assert PositionSide.from_order_action(OrderAction.SELL_TO_OPEN) == PositionSide.SHORT


# ==============================================================================
# Test: Orchestrator Initialization
# ==============================================================================

class TestOrchestratorInitialization:
    """Test StrategyOrchestrator initialization."""
    
    def test_init_default_state(self):
        from goldflipper.strategy.orchestrator import StrategyOrchestrator, OrchestratorState
        orchestrator = StrategyOrchestrator(config={'strategy_orchestration': {'enabled': False}})
        assert orchestrator.state == OrchestratorState.UNINITIALIZED
        assert orchestrator.strategies == []
    
    def test_init_with_resources(self):
        from goldflipper.strategy.orchestrator import StrategyOrchestrator
        config = create_mock_config()
        market = create_mock_market_data()
        client = create_mock_client()
        
        orchestrator = StrategyOrchestrator(
            config=config, market_data=market, brokerage_client=client
        )
        assert orchestrator.market_data is market
        assert orchestrator.client is client
    
    def test_init_disabled(self):
        from goldflipper.strategy.orchestrator import StrategyOrchestrator, OrchestratorState
        config = {'strategy_orchestration': {'enabled': False, 'mode': 'sequential'}}
        market = create_mock_market_data()
        client = create_mock_client()
        
        orchestrator = StrategyOrchestrator(
            config=config, market_data=market, brokerage_client=client
        )
        result = orchestrator.initialize()
        
        assert result == False
        assert orchestrator.state == OrchestratorState.STOPPED


# ==============================================================================
# Test: OptionSwingsStrategy
# ==============================================================================

class TestOptionSwingsStrategy:
    """Test OptionSwingsStrategy implementation."""
    
    def test_strategy_name(self):
        from goldflipper.strategy.runners.option_swings import OptionSwingsStrategy
        config = create_mock_config()
        strategy = OptionSwingsStrategy(
            config=config,
            market_data=create_mock_market_data(),
            brokerage_client=create_mock_client()
        )
        assert strategy.get_name() == "option_swings"
    
    def test_config_section(self):
        from goldflipper.strategy.runners.option_swings import OptionSwingsStrategy
        config = create_mock_config()
        strategy = OptionSwingsStrategy(
            config=config,
            market_data=create_mock_market_data(),
            brokerage_client=create_mock_client()
        )
        assert strategy.get_config_section() == "options_swings"
    
    def test_priority(self):
        from goldflipper.strategy.runners.option_swings import OptionSwingsStrategy
        config = create_mock_config()
        strategy = OptionSwingsStrategy(
            config=config,
            market_data=create_mock_market_data(),
            brokerage_client=create_mock_client()
        )
        assert strategy.get_priority() == 10
    
    def test_is_long_strategy(self):
        from goldflipper.strategy.runners.option_swings import OptionSwingsStrategy
        from goldflipper.strategy.base import OrderAction
        config = create_mock_config()
        strategy = OptionSwingsStrategy(
            config=config,
            market_data=create_mock_market_data(),
            brokerage_client=create_mock_client()
        )
        assert strategy.get_default_entry_action() == OrderAction.BUY_TO_OPEN
        assert strategy.is_long_strategy() == True
    
    def test_validate_play_valid(self):
        from goldflipper.strategy.runners.option_swings import OptionSwingsStrategy
        config = create_mock_config()
        strategy = OptionSwingsStrategy(
            config=config,
            market_data=create_mock_market_data(),
            brokerage_client=create_mock_client()
        )
        play = create_sample_play()
        assert strategy.validate_play(play) == True
    
    def test_validate_play_missing_field(self):
        from goldflipper.strategy.runners.option_swings import OptionSwingsStrategy
        config = create_mock_config()
        strategy = OptionSwingsStrategy(
            config=config,
            market_data=create_mock_market_data(),
            brokerage_client=create_mock_client()
        )
        play = create_sample_play()
        del play['strike_price']
        assert strategy.validate_play(play) == False


# ==============================================================================
# Main Runner
# ==============================================================================

def run_tests():
    """Run all tests without pytest."""
    print("=" * 60)
    print("Orchestrator Unit Tests")
    print("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    test_classes = [
        TestOrderAction,
        TestPlayStatus,
        TestPositionSide,
        TestOrchestratorInitialization,
        TestOptionSwingsStrategy
    ]
    
    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    getattr(instance, method_name)()
                    print(f"  OK {method_name}")
                    tests_passed += 1
                except Exception as e:
                    print(f"  FAIL {method_name}: {e}")
                    tests_failed += 1
    
    print(f"\n{'=' * 60}")
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

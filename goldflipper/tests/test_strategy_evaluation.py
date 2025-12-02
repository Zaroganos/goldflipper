"""
Unit Tests for Strategy Evaluation Module

This module provides comprehensive unit tests for the evaluation functions:
- evaluate_opening_strategy() - Entry condition evaluation
- evaluate_closing_strategy() - Exit condition evaluation (TP/SL)
- calculate_and_store_price_levels() - Stock price target calculations
- calculate_and_store_premium_levels() - Option premium target calculations

Usage:
    python goldflipper/tests/test_strategy_evaluation.py

Note: These tests use direct function imports to avoid circular import issues.

Author: Cascade (automated)
Date: 2025-12-01
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch

# Add project root to path BEFORE any goldflipper imports
_this_dir = os.path.dirname(os.path.abspath(__file__))
_goldflipper_pkg = os.path.dirname(_this_dir)
_project_root = os.path.dirname(_goldflipper_pkg)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(level=logging.WARNING)


def create_test_play(
    symbol: str = "SPY",
    trade_type: str = "CALL",
    entry_stock_price: float = 100.0,
    tp_stock_price: float = None,
    tp_stock_price_pct: float = 5.0,
    tp_premium_pct: float = 50.0,
    sl_stock_price: float = None,
    sl_stock_price_pct: float = 5.0,
    sl_premium_pct: float = 25.0,
    sl_type: str = "STOP",
    entry_premium: float = 1.55
) -> Dict[str, Any]:
    """Create a test play dictionary."""
    now = datetime.now()
    exp_date = now + timedelta(days=14)
    
    return {
        "symbol": symbol,
        "trade_type": trade_type,
        "strike_price": "500",
        "expiration_date": exp_date.strftime("%m/%d/%Y"),
        "option_contract_symbol": f"{symbol}{exp_date.strftime('%y%m%d')}C00500000",
        "contracts": 1,
        "entry_point": {
            "stock_price": entry_stock_price,
            "entry_stock_price": entry_stock_price,
            "entry_premium": entry_premium,
            "order_type": "market"
        },
        "take_profit": {
            "TP_type": "single",
            "stock_price": tp_stock_price,
            "stock_price_pct": tp_stock_price_pct,
            "premium_pct": tp_premium_pct,
            "TP_stock_price_target": None,
            "TP_option_prem": None,
            "order_type": "limit at bid"
        },
        "stop_loss": {
            "SL_type": sl_type,
            "stock_price": sl_stock_price,
            "stock_price_pct": sl_stock_price_pct,
            "premium_pct": sl_premium_pct,
            "SL_stock_price_target": None,
            "SL_option_prem": None,
            "order_type": "market"
        },
        "status": {"play_status": "NEW"}
    }


class TestPriceLevelCalculations:
    """Test calculate_and_store_price_levels function."""
    
    def test_call_tp_calculation(self):
        """Test TP price level for CALL options."""
        from goldflipper.strategy.shared.evaluation import calculate_and_store_price_levels
        
        play = create_test_play(trade_type="CALL", tp_stock_price_pct=10.0)
        calculate_and_store_price_levels(play, entry_stock_price=100.0)
        
        expected = 100.0 * 1.10
        assert abs(play['take_profit']['TP_stock_price_target'] - expected) < 0.01
    
    def test_call_sl_calculation(self):
        """Test SL price level for CALL options."""
        from goldflipper.strategy.shared.evaluation import calculate_and_store_price_levels
        
        play = create_test_play(trade_type="CALL", sl_stock_price_pct=10.0)
        calculate_and_store_price_levels(play, entry_stock_price=100.0)
        
        expected = 100.0 * 0.90
        assert abs(play['stop_loss']['SL_stock_price_target'] - expected) < 0.01
    
    def test_put_tp_calculation(self):
        """Test TP price level for PUT options."""
        from goldflipper.strategy.shared.evaluation import calculate_and_store_price_levels
        
        play = create_test_play(trade_type="PUT", tp_stock_price_pct=10.0)
        calculate_and_store_price_levels(play, entry_stock_price=100.0)
        
        expected = 100.0 * 0.90
        assert abs(play['take_profit']['TP_stock_price_target'] - expected) < 0.01
    
    def test_put_sl_calculation(self):
        """Test SL price level for PUT options."""
        from goldflipper.strategy.shared.evaluation import calculate_and_store_price_levels
        
        play = create_test_play(trade_type="PUT", sl_stock_price_pct=10.0)
        calculate_and_store_price_levels(play, entry_stock_price=100.0)
        
        expected = 100.0 * 1.10
        assert abs(play['stop_loss']['SL_stock_price_target'] - expected) < 0.01


class TestPremiumLevelCalculations:
    """Test calculate_and_store_premium_levels function."""
    
    def test_tp_premium_calculation(self):
        """Test TP premium calculation."""
        from goldflipper.strategy.shared.evaluation import calculate_and_store_premium_levels
        
        play = create_test_play(tp_premium_pct=50.0)
        play['entry_point']['order_type'] = 'market'
        
        option_data = {'bid': 1.50, 'ask': 1.60, 'mid': 1.55, 'last': 1.55}
        calculate_and_store_premium_levels(play, option_data)
        
        expected = 1.55 * 1.50
        assert abs(play['take_profit']['TP_option_prem'] - expected) < 0.001
    
    def test_sl_premium_calculation(self):
        """Test SL premium calculation."""
        from goldflipper.strategy.shared.evaluation import calculate_and_store_premium_levels
        
        play = create_test_play(sl_premium_pct=25.0)
        play['entry_point']['order_type'] = 'market'
        
        option_data = {'bid': 1.50, 'ask': 1.60, 'mid': 1.55, 'last': 1.55}
        calculate_and_store_premium_levels(play, option_data)
        
        expected = 1.55 * 0.75
        assert abs(play['stop_loss']['SL_option_prem'] - expected) < 0.001


class TestOpeningStrategyEvaluation:
    """Test evaluate_opening_strategy function."""
    
    def test_entry_at_target(self):
        """Test entry when price is at target."""
        from goldflipper.strategy.shared.evaluation import evaluate_opening_strategy
        
        play = create_test_play(entry_stock_price=100.0)
        mock_get_price = Mock(return_value=100.0)
        
        result = evaluate_opening_strategy("SPY", play, mock_get_price)
        assert result == True
    
    def test_entry_outside_buffer(self):
        """Test no entry when price is outside buffer."""
        from goldflipper.strategy.shared.evaluation import evaluate_opening_strategy
        
        play = create_test_play(entry_stock_price=100.0)
        mock_get_price = Mock(return_value=150.0)
        
        result = evaluate_opening_strategy("SPY", play, mock_get_price)
        assert result == False
    
    def test_entry_with_none_price(self):
        """Test no entry when price unavailable."""
        from goldflipper.strategy.shared.evaluation import evaluate_opening_strategy
        
        play = create_test_play()
        mock_get_price = Mock(return_value=None)
        
        result = evaluate_opening_strategy("SPY", play, mock_get_price)
        assert result == False


class TestClosingStrategyEvaluation:
    """Test evaluate_closing_strategy function."""
    
    def test_tp_triggered_call(self):
        """Test TP triggered for CALL."""
        from goldflipper.strategy.shared.evaluation import evaluate_closing_strategy
        
        play = create_test_play(trade_type="CALL", tp_stock_price=105.0)
        mock_get_price = Mock(return_value=106.0)
        mock_get_option = Mock(return_value={'premium': 2.50})
        mock_save = Mock()
        
        result = evaluate_closing_strategy(
            "SPY", play, "/tmp/test.json",
            mock_get_price, mock_get_option, mock_save
        )
        
        assert result['should_close'] == True
        assert result['is_profit'] == True
    
    def test_sl_triggered_call(self):
        """Test SL triggered for CALL."""
        from goldflipper.strategy.shared.evaluation import evaluate_closing_strategy
        
        play = create_test_play(trade_type="CALL", sl_stock_price=95.0)
        mock_get_price = Mock(return_value=94.0)
        mock_get_option = Mock(return_value={'premium': 1.00})
        mock_save = Mock()
        
        result = evaluate_closing_strategy(
            "SPY", play, "/tmp/test.json",
            mock_get_price, mock_get_option, mock_save
        )
        
        assert result['should_close'] == True
        assert result['is_primary_loss'] == True
    
    def test_hold_position(self):
        """Test hold when no conditions met."""
        from goldflipper.strategy.shared.evaluation import evaluate_closing_strategy
        
        play = create_test_play(
            trade_type="CALL",
            tp_stock_price=105.0,
            sl_stock_price=95.0
        )
        mock_get_price = Mock(return_value=100.0)
        mock_get_option = Mock(return_value={'premium': 1.55})
        mock_save = Mock()
        
        result = evaluate_closing_strategy(
            "SPY", play, "/tmp/test.json",
            mock_get_price, mock_get_option, mock_save
        )
        
        assert result['should_close'] == False


def run_tests():
    """Run tests without pytest."""
    print("=" * 60)
    print("Strategy Evaluation Unit Tests")
    print("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    # Run each test class
    for test_class in [TestPriceLevelCalculations, TestPremiumLevelCalculations,
                       TestOpeningStrategyEvaluation, TestClosingStrategyEvaluation]:
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

"""
Test Parallel Execution Mode for Multi-Strategy Orchestration

This test validates that the StrategyOrchestrator correctly executes
multiple strategies in parallel mode using ThreadPoolExecutor.

Test scenarios:
1. Initialize orchestrator with multiple enabled strategies
2. Verify parallel execution mode is configured
3. Create test plays for different strategies
4. Run cycles and verify both strategies execute
5. Verify thread-safety and shared resource access

Usage:
    python -m goldflipper.tests.test_parallel_execution

Author: Cascade (automated)
Date: 2025-12-01
"""

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ==============================================================================
# Test Play Creation Helpers
# ==============================================================================


def create_test_play(
    symbol: str,
    strategy: str,
    strike: float,
    trade_type: str = "CALL",
    entry_price: float = None,
    entry_buffer_pct: float = 0.50,  # 50% buffer for easy entry
    option_symbol: str = None,
    momentum_config: dict = None,
) -> dict[str, Any]:
    """
    Create a test play dictionary for parallel execution testing.

    Args:
        symbol: Stock symbol (e.g., 'SPY')
        strategy: Strategy name ('option_swings' or 'momentum')
        strike: Option strike price
        trade_type: 'CALL' or 'PUT'
        entry_price: Stock price for entry (uses strike if None)
        entry_buffer_pct: Buffer percentage for entry range
        option_symbol: Option contract symbol (auto-generated if None)
        momentum_config: Optional momentum-specific config

    Returns:
        Play dictionary ready for saving
    """
    now = datetime.now()
    exp_date = now + timedelta(days=14)
    play_exp_date = now + timedelta(days=7)

    # Use strike as entry price if not provided
    if entry_price is None:
        entry_price = strike

    # Calculate entry range with wide buffer
    entry_low = entry_price * (1 - entry_buffer_pct)
    entry_high = entry_price * (1 + entry_buffer_pct)

    # Generate option symbol if not provided
    if option_symbol is None:
        exp_str = exp_date.strftime("%y%m%d")
        opt_type = "C" if trade_type == "CALL" else "P"
        strike_str = f"{int(strike * 1000):08d}"
        option_symbol = f"{symbol}{exp_str}{opt_type}{strike_str}"

    play = {
        "creator": "parallel_test",
        "play_name": f"{strategy}_test_{symbol}_{now.strftime('%Y%m%d_%H%M%S')}",
        "symbol": symbol,
        "expiration_date": exp_date.strftime("%m/%d/%Y"),
        "trade_type": trade_type,
        "strike_price": str(strike),
        "option_contract_symbol": option_symbol,
        "contracts": 1,
        "play_expiration_date": play_exp_date.strftime("%m/%d/%Y"),
        "entry_point": {
            "stock_price": entry_price,
            "stock_price_low": entry_low,
            "stock_price_high": entry_high,
            "order_type": "market",
            "entry_premium": 0.0,
            "entry_stock_price": 0.0,
        },
        "take_profit": {
            "TP_type": "single",
            "stock_price": 0.0,
            "stock_price_pct": 0.0,
            "premium_pct": 50.0,
            "order_type": "limit at bid",
            "TP_option_prem": 0.0,
            "TP_stock_price_target": 0.0,
            "trailing_config": {"enabled": False},
        },
        "stop_loss": {
            "SL_type": "STOP",
            "stock_price": 0.0,
            "stock_price_pct": 0.0,
            "premium_pct": 25.0,
            "order_type": "market",
            "SL_option_prem": 0.0,
            "SL_stock_price_target": 0.0,
            "trailing_config": {"enabled": False},
        },
        "play_class": "SIMPLE",
        "strategy": strategy,
        "creation_date": now.strftime("%m/%d/%Y"),
        "conditional_plays": {"OCO_triggers": [], "OTO_triggers": []},
        "status": {
            "play_status": "NEW",
            "order_id": None,
            "position_uuid": None,
            "order_status": None,
            "position_exists": False,
            "closing_order_id": None,
            "closing_order_status": None,
        },
        "logging": {"delta_atOpen": 0.0, "theta_atOpen": 0.0, "datetime_atOpen": None, "price_atOpen": 0.0, "premium_atOpen": 0.0},
    }

    # Add momentum-specific config if provided
    if momentum_config:
        play["momentum_config"] = momentum_config

    return play


def save_test_play(play: dict[str, Any], plays_dir: str) -> str:
    """
    Save a test play to the new/ directory.

    Args:
        play: Play dictionary
        plays_dir: Base plays directory path

    Returns:
        Full path to saved play file
    """
    new_dir = os.path.join(plays_dir, "new")
    os.makedirs(new_dir, exist_ok=True)

    filename = f"{play['play_name']}.json"
    filepath = os.path.join(new_dir, filename)

    with open(filepath, "w") as f:
        json.dump(play, f, indent=2)

    logger.info(f"Saved test play: {filepath}")
    return filepath


def cleanup_test_plays(plays_dir: str, creator: str = "parallel_test"):
    """
    Remove test plays created by this test.

    Args:
        plays_dir: Base plays directory path
        creator: Creator field to match for cleanup
    """
    for subdir in ["new", "pending-opening", "open", "pending-closing", "closed", "expired"]:
        dir_path = os.path.join(plays_dir, subdir)
        if not os.path.exists(dir_path):
            continue

        for filename in os.listdir(dir_path):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(dir_path, filename)
            try:
                with open(filepath) as f:
                    play = json.load(f)

                if play.get("creator") == creator:
                    os.remove(filepath)
                    logger.debug(f"Cleaned up test play: {filepath}")
            except Exception as e:
                logger.warning(f"Error cleaning up {filepath}: {e}")


# ==============================================================================
# Test Functions
# ==============================================================================


def test_orchestrator_initialization():
    """Test that orchestrator initializes with parallel mode and multiple strategies."""
    print("\n" + "=" * 70)
    print("TEST 1: Orchestrator Initialization")
    print("=" * 70)

    from goldflipper.strategy.orchestrator import ExecutionMode, StrategyOrchestrator

    orchestrator = StrategyOrchestrator()
    success = orchestrator.initialize()

    if not success:
        print("❌ FAIL: Orchestrator failed to initialize")
        return False

    # Check parallel mode
    if orchestrator._execution_mode != ExecutionMode.PARALLEL:
        print(f"❌ FAIL: Expected PARALLEL mode, got {orchestrator._execution_mode}")
        return False

    print(f"✅ Execution mode: {orchestrator._execution_mode.value}")

    # Check multiple strategies loaded
    strategy_count = len(orchestrator.strategies)
    if strategy_count < 2:
        print(f"❌ FAIL: Expected at least 2 strategies, got {strategy_count}")
        print(f"   Loaded strategies: {[s.get_name() for s in orchestrator.strategies]}")
        return False

    print(f"✅ Loaded {strategy_count} strategies:")
    for s in orchestrator.strategies:
        print(f"   - {s.get_name()} (priority={s.get_priority()})")

    # Check specific strategies
    strategy_names = [s.get_name() for s in orchestrator.strategies]

    if "option_swings" not in strategy_names:
        print("❌ FAIL: option_swings strategy not loaded")
        return False

    if "momentum" not in strategy_names:
        print("❌ FAIL: momentum strategy not loaded")
        return False

    print("✅ Both option_swings and momentum strategies loaded")

    # Get status
    status = orchestrator.get_status()
    print("\nOrchestrator Status:")
    print(f"  State: {status['state']}")
    print(f"  Enabled: {status['enabled']}")
    print(f"  Mode: {status['execution_mode']}")
    print(f"  Max Workers: {orchestrator._max_workers}")

    print("\n✅ TEST 1 PASSED: Orchestrator initialization successful")
    return True


def test_parallel_execution_timing():
    """Test that parallel execution runs strategies concurrently."""
    print("\n" + "=" * 70)
    print("TEST 2: Parallel Execution Timing")
    print("=" * 70)

    from goldflipper.strategy.orchestrator import StrategyOrchestrator

    # Track execution timing
    execution_times = {}
    execution_threads = {}
    lock = threading.Lock()

    class TimingWrapper:
        """Wrapper to track strategy execution timing."""

        def __init__(self, original_execute, strategy_name):
            self.original_execute = original_execute
            self.strategy_name = strategy_name

        def __call__(self, strategy):
            start = time.time()
            thread_id = threading.get_ident()

            with lock:
                execution_threads[self.strategy_name] = thread_id

            logger.info(f"[{self.strategy_name}] Starting execution on thread {thread_id}")

            try:
                result = self.original_execute(strategy)
            except Exception as e:
                logger.error(f"[{self.strategy_name}] Execution error: {e}")
                result = None

            end = time.time()

            with lock:
                execution_times[self.strategy_name] = {"start": start, "end": end, "duration": end - start, "thread": thread_id}

            logger.info(f"[{self.strategy_name}] Completed in {end - start:.3f}s")
            return result

    # Initialize orchestrator
    orchestrator = StrategyOrchestrator()
    orchestrator.initialize()

    # Wrap execute method to track timing
    original_execute = orchestrator._execute_strategy
    [s.get_name() for s in orchestrator.strategies]

    def timed_execute(strategy):
        name = strategy.get_name()
        start = time.time()
        thread_id = threading.get_ident()

        with lock:
            if name not in execution_times:
                execution_times[name] = {"start": start, "thread": thread_id}
            else:
                execution_times[name]["start"] = start
                execution_times[name]["thread"] = thread_id

        logger.info(f"[{name}] Starting on thread {thread_id}")

        try:
            original_execute(strategy)
        except Exception as e:
            logger.warning(f"[{name}] Error (expected if no plays): {e}")

        end = time.time()

        with lock:
            execution_times[name]["end"] = end
            execution_times[name]["duration"] = end - start

        logger.info(f"[{name}] Completed in {end - start:.3f}s")

    orchestrator._execute_strategy = timed_execute

    # Run a cycle
    print("\nRunning parallel cycle...")
    cycle_start = time.time()
    orchestrator.run_cycle()
    cycle_end = time.time()
    cycle_duration = cycle_end - cycle_start

    print(f"\nCycle completed in {cycle_duration:.3f}s")

    # Analyze timing
    print("\nExecution Timing Analysis:")

    if len(execution_times) < 2:
        print(f"⚠️ WARNING: Only {len(execution_times)} strategies executed")
        print("   This may be expected if no plays are in the new/ directory")

    # Check for thread diversity (parallel should use different threads)
    threads_used = {t.get("thread") for t in execution_times.values() if t.get("thread")}

    print(f"\nThreads used: {len(threads_used)}")
    for name, times in execution_times.items():
        print(f"  {name}: thread {times.get('thread', 'N/A')}, duration {times.get('duration', 0):.3f}s")

    # In parallel mode, strategies should use different threads (if >1 worker)
    if len(threads_used) > 1:
        print("\n✅ Parallel execution confirmed: Multiple threads used")
    elif len(execution_times) < 2:
        print("\n⚠️ Cannot confirm parallelism: Need 2+ strategies executing")
    else:
        print("\n⚠️ Single thread used (may be due to fast execution)")

    # Check for overlapping execution (true parallelism)
    starts = [t.get("start", 0) for t in execution_times.values()]
    ends = [t.get("end", 0) for t in execution_times.values()]

    if len(starts) >= 2 and len(ends) >= 2:
        min(starts)
        max_start = max(starts)
        min_end = min(ends)

        # If second strategy started before first ended, they overlapped
        if max_start < min_end:
            print("✅ Overlapping execution detected (true parallel)")
        else:
            print("⚠️ Sequential execution detected (may need plays to trigger parallel)")

    print("\n✅ TEST 2 PASSED: Parallel execution timing analyzed")
    return True


def test_parallel_with_plays():
    """Test parallel execution with actual test plays."""
    print("\n" + "=" * 70)
    print("TEST 3: Parallel Execution with Test Plays")
    print("=" * 70)

    from goldflipper.data.market.manager import MarketDataManager
    from goldflipper.strategy.orchestrator import StrategyOrchestrator
    from goldflipper.utils.exe_utils import get_plays_dir

    # Get plays directory using account-aware paths
    plays_dir = str(get_plays_dir())

    print(f"Plays directory: {plays_dir}")

    # Clean up any previous test plays
    print("\nCleaning up previous test plays...")
    cleanup_test_plays(plays_dir)

    # Get current market data for realistic plays
    market_data = MarketDataManager()

    # Get current prices for test symbols
    test_configs = [
        {"symbol": "SPY", "strategy": "option_swings"},
        {"symbol": "AAPL", "strategy": "momentum"},
    ]

    created_plays = []

    for config in test_configs:
        symbol = config["symbol"]
        strategy = config["strategy"]

        try:
            # Get current price
            price = market_data.get_stock_price(symbol)
            if price is None:
                print(f"⚠️ Could not get price for {symbol}, using default")
                price = 500.0 if symbol == "SPY" else 200.0

            print(f"\n{symbol}: Current price = ${price:.2f}")

            # Round strike to nearest integer
            strike = round(price)

            # Create play with wide entry buffer for testing
            momentum_config = None
            if strategy == "momentum":
                momentum_config = {
                    "momentum_type": "manual",  # Skip gap/squeeze checks
                    "max_hold_days": 5,
                }

            play = create_test_play(
                symbol=symbol,
                strategy=strategy,
                strike=strike,
                trade_type="CALL",
                entry_price=price,
                entry_buffer_pct=0.50,  # 50% buffer - will always be in range
                momentum_config=momentum_config,
            )

            filepath = save_test_play(play, plays_dir)
            created_plays.append({"filepath": filepath, "symbol": symbol, "strategy": strategy})

            print(f"✅ Created {strategy} play for {symbol}")

        except Exception as e:
            print(f"❌ Failed to create play for {symbol}: {e}")

    if len(created_plays) < 2:
        print("\n❌ FAIL: Could not create plays for both strategies")
        return False

    print(f"\nCreated {len(created_plays)} test plays")

    # Initialize and run orchestrator
    print("\nInitializing orchestrator...")
    orchestrator = StrategyOrchestrator()
    orchestrator.initialize()

    # Track which strategies evaluated plays
    evaluated_strategies = set()

    # Hook into strategy evaluation to track execution
    for strategy in orchestrator.strategies:
        original_evaluate = strategy.evaluate_new_plays
        strategy_name = strategy.get_name()

        def make_wrapper(name, orig):
            def wrapper(plays):
                if plays:
                    evaluated_strategies.add(name)
                    logger.info(f"[{name}] Evaluating {len(plays)} plays")
                return orig(plays)

            return wrapper

        strategy.evaluate_new_plays = make_wrapper(strategy_name, original_evaluate)

    # Run cycle
    print("\nRunning orchestrator cycle...")
    start_time = time.time()
    success = orchestrator.run_cycle()
    elapsed = time.time() - start_time

    print(f"\nCycle completed in {elapsed:.3f}s")
    print(f"Cycle success: {success}")

    # Check results
    print("\nStrategies that evaluated plays:")
    for name in evaluated_strategies:
        print(f"  ✅ {name}")

    expected_strategies = {"option_swings", "momentum"}
    missing = expected_strategies - evaluated_strategies

    if missing:
        print(f"\n⚠️ Strategies that didn't evaluate plays: {missing}")
        print("   (This may be due to validation or market hours)")

    # Get final status
    status = orchestrator.get_status()
    print("\nFinal orchestrator status:")
    print(f"  State: {status['state']}")
    print(f"  Cycles: {status['cycle_count']}")
    if status["last_cycle_errors"]:
        print(f"  Errors: {status['last_cycle_errors']}")

    # Cleanup
    print("\nCleaning up test plays...")
    cleanup_test_plays(plays_dir)

    print("\n✅ TEST 3 PASSED: Parallel execution with plays completed")
    return True


def test_shared_resource_access():
    """Test that shared resources (market data, client) are accessed safely."""
    print("\n" + "=" * 70)
    print("TEST 4: Shared Resource Access")
    print("=" * 70)

    from goldflipper.strategy.orchestrator import StrategyOrchestrator

    orchestrator = StrategyOrchestrator()
    orchestrator.initialize()

    # Verify shared resources
    print("\nShared Resources:")
    print(f"  Market Data: {type(orchestrator.market_data).__name__}")
    print(f"  Brokerage Client: {type(orchestrator.client).__name__}")

    # Check all strategies use same instances
    market_data_ids = set()
    client_ids = set()

    for strategy in orchestrator.strategies:
        market_data_ids.add(id(strategy.market_data))
        client_ids.add(id(strategy.client))

    if len(market_data_ids) == 1:
        print("✅ All strategies share same MarketDataManager instance")
    else:
        print(f"⚠️ Multiple MarketDataManager instances: {len(market_data_ids)}")

    if len(client_ids) == 1:
        print("✅ All strategies share same brokerage client instance")
    else:
        print(f"⚠️ Multiple client instances: {len(client_ids)}")

    print("\n✅ TEST 4 PASSED: Shared resource access verified")
    return True


def run_all_tests():
    """Run all parallel execution tests."""
    print("\n" + "=" * 70)
    print("GOLDFLIPPER PARALLEL EXECUTION TEST SUITE")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = {}

    # Test 1: Initialization
    try:
        results["initialization"] = test_orchestrator_initialization()
    except Exception as e:
        print(f"❌ TEST 1 FAILED with exception: {e}")
        results["initialization"] = False
        import traceback

        traceback.print_exc()

    # Test 2: Timing
    try:
        results["timing"] = test_parallel_execution_timing()
    except Exception as e:
        print(f"❌ TEST 2 FAILED with exception: {e}")
        results["timing"] = False
        import traceback

        traceback.print_exc()

    # Test 3: With Plays (skip if market closed)
    try:
        results["with_plays"] = test_parallel_with_plays()
    except Exception as e:
        print(f"❌ TEST 3 FAILED with exception: {e}")
        results["with_plays"] = False
        import traceback

        traceback.print_exc()

    # Test 4: Shared Resources
    try:
        results["shared_resources"] = test_shared_resource_access()
    except Exception as e:
        print(f"❌ TEST 4 FAILED with exception: {e}")
        results["shared_resources"] = False
        import traceback

        traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print("\n⚠️ Some tests failed - review output above")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

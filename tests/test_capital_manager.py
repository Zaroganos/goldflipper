"""
Tests for CapitalManager

All tests use unittest.mock — no live Alpaca calls, no live filesystem access.
"""

import json
from unittest.mock import Mock, patch

import pytest
from goldflipper.strategy.capital import CapitalManager
from goldflipper.strategy.playbooks.schema import RiskConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bto_play(symbol="SPY", contracts=1, premium=2.0):
    return {
        "symbol": symbol,
        "contracts": contracts,
        "action": "BTO",
        "entry_point": {"target_price": premium},
    }


def _make_sto_play(symbol="SPY", contracts=1, strike=450.0):
    return {
        "symbol": symbol,
        "contracts": contracts,
        "action": "STO",
        "strike_price": strike,
    }


def _make_config(**kwargs):
    """Build a minimal capital_management config dict."""
    defaults = {
        "enabled": True,
        "max_total_open_positions": None,
        "max_capital_deployed_pct": None,
        "per_symbol_max_open_positions": 100,
        "buying_power_reserve_pct": 0.0,
    }
    defaults.update(kwargs)
    return {"capital_management": defaults}


# ===========================================================================
# 1. test_refresh_success
# ===========================================================================


def test_refresh_success():
    """Mock client returns account; verify buying_power / equity / portfolio_value."""
    account = Mock()
    account.options_buying_power = "25000.00"
    account.equity = "50000.00"
    account.portfolio_value = "52000.00"

    client = Mock()
    client.get_account.return_value = account

    mgr = CapitalManager(client, {})
    mgr.refresh()

    assert mgr.buying_power == 25000.0
    assert mgr.equity == 50000.0
    assert mgr.portfolio_value == 52000.0
    assert mgr._account_loaded is True


def test_refresh_success_fallback_to_buying_power():
    """When options_buying_power is absent, fall back to buying_power."""
    account = Mock(spec=["buying_power", "equity", "portfolio_value"])
    account.buying_power = "100000.00"
    account.equity = "100000.00"
    account.portfolio_value = "100000.00"
    # options_buying_power not present on spec → getattr returns None

    client = Mock()
    client.get_account.return_value = account

    mgr = CapitalManager(client, {})
    mgr.refresh()

    assert mgr.buying_power == 100000.0
    assert mgr._account_loaded is True


# ===========================================================================
# 2. test_refresh_failure
# ===========================================================================


def test_refresh_failure():
    """Client raises; verify stale values kept and _account_loaded is False."""
    client = Mock()
    client.get_account.side_effect = RuntimeError("connection refused")

    mgr = CapitalManager(client, {})
    # Seed stale values as if a previous refresh succeeded
    mgr._buying_power = 99999.0
    mgr._equity = 99999.0
    mgr._account_loaded = True

    mgr.refresh()  # Should not raise

    # Stale monetary values remain (we didn't zero them)
    assert mgr._buying_power == 99999.0
    assert mgr._equity == 99999.0
    # But account is marked not loaded
    assert mgr._account_loaded is False


# ===========================================================================
# 3. test_count_active_plays_empty
# ===========================================================================


def test_count_active_plays_empty(tmp_path):
    """Empty play directories → count is 0."""
    (tmp_path / "open").mkdir()
    (tmp_path / "pending-opening").mkdir()

    mgr = CapitalManager(None, {})

    def mock_subdir(subdir, **kwargs):
        return tmp_path / subdir

    with patch("goldflipper.utils.exe_utils.get_play_subdir", side_effect=mock_subdir):
        count = mgr.count_active_plays()

    assert count == 0


# ===========================================================================
# 4. test_count_active_plays_with_files
# ===========================================================================


def test_count_active_plays_with_files(tmp_path):
    """Play JSON files in open/ and pending-opening/ are counted."""
    (tmp_path / "open").mkdir()
    (tmp_path / "pending-opening").mkdir()

    (tmp_path / "open" / "play1.json").write_text(json.dumps({"symbol": "SPY", "contracts": 1}), encoding="utf-8")
    (tmp_path / "pending-opening" / "play2.json").write_text(json.dumps({"symbol": "QQQ", "contracts": 2}), encoding="utf-8")

    mgr = CapitalManager(None, {})

    def mock_subdir(subdir, **kwargs):
        return tmp_path / subdir

    with patch("goldflipper.utils.exe_utils.get_play_subdir", side_effect=mock_subdir):
        count = mgr.count_active_plays()

    assert count == 2


# ===========================================================================
# 5. test_count_active_plays_by_symbol
# ===========================================================================


def test_count_active_plays_by_symbol(tmp_path):
    """count_active_plays filters correctly by symbol."""
    (tmp_path / "open").mkdir()
    (tmp_path / "pending-opening").mkdir()

    for i, sym in enumerate(["SPY", "SPY", "QQQ"]):
        folder = "open" if i < 2 else "pending-opening"
        (tmp_path / folder / f"play{i}.json").write_text(json.dumps({"symbol": sym}), encoding="utf-8")

    mgr = CapitalManager(None, {})

    def mock_subdir(subdir, **kwargs):
        return tmp_path / subdir

    with patch("goldflipper.utils.exe_utils.get_play_subdir", side_effect=mock_subdir):
        spy_count = mgr.count_active_plays("SPY")
        qqq_count = mgr.count_active_plays("QQQ")
        total_count = mgr.count_active_plays()

    assert spy_count == 2
    assert qqq_count == 1
    assert total_count == 3


# ===========================================================================
# 6. test_estimate_trade_cost_bto
# ===========================================================================


def test_estimate_trade_cost_bto():
    """BTO: premium * contracts * 100."""
    mgr = CapitalManager(None, {})
    play = _make_bto_play(contracts=3, premium=2.50)
    cost = mgr.estimate_trade_cost(play)
    assert cost == pytest.approx(3 * 2.50 * 100)


# ===========================================================================
# 7. test_estimate_trade_cost_sto
# ===========================================================================


def test_estimate_trade_cost_sto():
    """STO: strike_price * contracts * 100 (collateral proxy)."""
    mgr = CapitalManager(None, {})
    play = _make_sto_play(contracts=2, strike=400.0)
    cost = mgr.estimate_trade_cost(play)
    assert cost == pytest.approx(2 * 400.0 * 100)


# ===========================================================================
# 8. test_check_trade_passes
# ===========================================================================


def test_check_trade_passes():
    """All limits are comfortably below thresholds → (True, 'ok')."""
    config = _make_config(
        max_total_open_positions=10,
        per_symbol_max_open_positions=5,
        max_capital_deployed_pct=80.0,
        buying_power_reserve_pct=5.0,
    )
    mgr = CapitalManager(None, config)
    mgr._load_active_plays = Mock(return_value=[])
    mgr._account_loaded = True
    mgr._buying_power = 100_000.0
    mgr._equity = 100_000.0

    play = _make_bto_play(premium=1.0)  # cost = $100
    allowed, reason = mgr.check_trade(play)

    assert allowed is True
    assert reason == "ok"


# ===========================================================================
# 9. test_check_trade_blocked_by_global_max
# ===========================================================================


def test_check_trade_blocked_by_global_max():
    """Active play count >= max_total_open_positions → blocked."""
    config = _make_config(max_total_open_positions=3)
    mgr = CapitalManager(None, config)
    # Three plays already open
    mgr._load_active_plays = Mock(return_value=[{}, {}, {}])

    play = _make_bto_play()
    allowed, reason = mgr.check_trade(play)

    assert allowed is False
    assert "max_total_open_positions" in reason
    assert "3" in reason


# ===========================================================================
# 10. test_check_trade_blocked_by_symbol_max
# ===========================================================================


def test_check_trade_blocked_by_symbol_max():
    """Symbol count >= per_symbol_max → blocked."""
    config = _make_config(per_symbol_max_open_positions=1)
    mgr = CapitalManager(None, config)
    # One existing SPY play
    mgr._load_active_plays = Mock(return_value=[{"symbol": "SPY"}])

    play = _make_bto_play(symbol="SPY")
    allowed, reason = mgr.check_trade(play)

    assert allowed is False
    assert "SPY" in reason
    assert "per-symbol limit" in reason


# ===========================================================================
# 11. test_check_trade_blocked_by_risk_config_max_open
# ===========================================================================


def test_check_trade_blocked_by_risk_config_max_open():
    """risk_config.max_open_plays reached → blocked."""
    # Global limits are unlimited; playbook sets a ceiling of 3
    config = _make_config()
    mgr = CapitalManager(None, config)
    mgr._load_active_plays = Mock(return_value=[{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}])

    risk_config = RiskConfig(max_open_plays=3)
    play = _make_bto_play(symbol="SPY")
    allowed, reason = mgr.check_trade(play, risk_config)

    assert allowed is False
    assert "max_open_plays" in reason


# ===========================================================================
# 12. test_check_trade_blocked_by_buying_power
# ===========================================================================


def test_check_trade_blocked_by_buying_power():
    """Estimated cost exceeds available buying power → blocked."""
    config = _make_config(buying_power_reserve_pct=0.0)
    mgr = CapitalManager(None, config)
    mgr._load_active_plays = Mock(return_value=[])
    mgr._account_loaded = True
    mgr._buying_power = 500.0
    mgr._equity = 100_000.0

    # Cost = 10.0 * 1 * 100 = $1 000 > $500 available
    play = _make_bto_play(premium=10.0, contracts=1)
    allowed, reason = mgr.check_trade(play)

    assert allowed is False
    assert "buying power" in reason.lower()


# ===========================================================================
# 13. test_check_trade_disabled
# ===========================================================================


def test_check_trade_disabled():
    """capital_management.enabled = false → always returns (True, 'disabled')."""
    config = {
        "capital_management": {
            "enabled": False,
            "max_total_open_positions": 0,  # Would block if enabled
        }
    }
    mgr = CapitalManager(None, config)
    mgr._load_active_plays = Mock(return_value=[{}, {}, {}, {}, {}])
    mgr._account_loaded = True
    mgr._buying_power = 1.0  # Would block on buying power if enabled

    play = _make_bto_play(premium=100.0)  # huge cost
    allowed, reason = mgr.check_trade(play)

    assert allowed is True
    assert reason == "disabled"


# ===========================================================================
# 14. test_capital_manager_in_orchestrator
# ===========================================================================


def test_capital_manager_in_orchestrator():
    """
    After _initialize_resources(), orchestrator._capital_manager is a
    CapitalManager instance with the correct client and config.
    """
    from goldflipper.strategy.orchestrator import StrategyOrchestrator

    config = {
        "strategy_orchestration": {"enabled": True, "mode": "sequential"},
        "capital_management": {"enabled": True, "max_total_open_positions": 5},
    }
    mock_client = Mock()
    mock_market_data = Mock()

    orchestrator = StrategyOrchestrator(
        config=config,
        market_data=mock_market_data,
        brokerage_client=mock_client,
    )

    # Initially None — not yet initialized
    assert orchestrator._capital_manager is None

    # After _initialize_resources, CapitalManager should exist
    orchestrator._initialize_resources()

    assert orchestrator._capital_manager is not None
    assert isinstance(orchestrator._capital_manager, CapitalManager)
    # Verify it references the same client
    assert orchestrator._capital_manager._client is mock_client

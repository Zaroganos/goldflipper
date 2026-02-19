import os
import sys

# Add the project root directory to Python path (for source mode only)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.append(project_root)

import subprocess

import alpaca

from goldflipper.alpaca_client import get_alpaca_client
from goldflipper.config.config import config, get_account_nickname, get_active_account_name
from goldflipper.utils.exe_utils import get_plays_dir


def get_plays_count():
    """
    Get play counts from each folder for the active account.
    Uses exe-aware path utilities for frozen mode compatibility.
    """
    plays_dir = get_plays_dir()  # Now returns account-aware path: plays/{account}/shared/
    folders = ["new", "temp", "pending-opening", "open", "pending-closing", "closed", "expired"]
    counts = {}

    for folder in folders:
        folder_path = plays_dir / folder
        if folder_path.exists():
            json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
            counts[folder] = len(json_files)
        else:
            counts[folder] = 0

    return counts


def get_active_account_info():
    """
    Get information about the currently active trading account.
    """
    account_name = get_active_account_name()
    nickname = get_account_nickname(account_name)
    plays_dir = str(get_plays_dir())

    return {"name": account_name, "nickname": nickname, "plays_directory": plays_dir}


def get_orchestrator_status():
    """
    Get the strategy orchestrator configuration and status.
    """
    try:
        orch_config = config.get("strategy_orchestration", default={})
        enabled = orch_config.get("enabled", False)
        mode = orch_config.get("mode", "sequential")
        dry_run = orch_config.get("dry_run", False)
        max_workers = orch_config.get("max_parallel_workers", 3)

        return {"enabled": enabled, "mode": mode, "dry_run": dry_run, "max_parallel_workers": max_workers}
    except Exception as e:
        return {"error": str(e)}


def get_enabled_strategies():
    """
    Get list of enabled strategies from config.
    """
    strategies = []
    strategy_configs = [
        ("option_swings", "options_swings"),  # (display_name, config_key)
        ("momentum", "momentum"),
        ("sell_puts", "sell_puts"),
        ("spreads", "spreads"),
        ("option_swings_auto", "option_swings_auto"),
    ]

    for display_name, config_key in strategy_configs:
        try:
            strat_config = config.get(config_key, default={})
            if strat_config.get("enabled", False):
                strategies.append(display_name)
        except Exception:
            pass

    return strategies


def update_alpaca():
    """
    Update alpaca-py package using pip.
    """
    print("\nUpdating alpaca-py package...")
    try:
        # WAIT HOLD ON, SHOULD THIS USE UV OR NO?
        # ALSO UPDATE THIS TO EXPLICITLY MENTION THE CURRENT VERSION AND AVAILABLE / UPGRADING(ED) TO VERSION
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "alpaca-py"])
        print("alpaca-py updated successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error updating alpaca-py: {e}")


def check_system_status():
    """
    Tool to check system status and perform maintenance tasks.
    """
    print("=" * 60)
    print("       System Status and Upkeep")
    print("=" * 60)

    # ==========================================
    # STRATEGY ORCHESTRATOR STATUS
    # ==========================================
    print("\n" + "-" * 40)
    print("  Strategy Orchestrator Status")
    print("-" * 40)

    orch_status = get_orchestrator_status()
    if "error" in orch_status:
        print(f"  Error loading config: {orch_status['error']}")
    else:
        status_str = "[ENABLED]" if orch_status["enabled"] else "[DISABLED]"
        print(f"  Orchestration:      {status_str}")
        print(f"  Execution Mode:     {orch_status['mode'].upper()}")
        if orch_status["mode"] == "parallel":
            print(f"  Max Workers:        {orch_status['max_parallel_workers']}")

        dry_run_str = "[YES - NO LIVE TRADES]" if orch_status["dry_run"] else "No"
        print(f"  Dry-Run Mode:       {dry_run_str}")

    # Enabled strategies
    enabled_strategies = get_enabled_strategies()
    print(f"\n  Enabled Strategies: {len(enabled_strategies)}")
    if enabled_strategies:
        for strat in enabled_strategies:
            print(f"    - {strat}")
    else:
        print("    (none enabled)")

    # ==========================================
    # PLAYS DIRECTORY STATUS
    # ==========================================
    print("\n" + "-" * 40)
    print("  Plays Directory Status")
    print("-" * 40)

    plays_counts = get_plays_count()
    total_active = (
        plays_counts.get("new", 0) + plays_counts.get("pending-opening", 0) + plays_counts.get("open", 0) + plays_counts.get("pending-closing", 0)
    )

    print(f"  NEW:             {plays_counts.get('new', 0):>4} plays")
    print(f"  TEMP:            {plays_counts.get('temp', 0):>4} plays")
    print(f"  PENDING-OPENING: {plays_counts.get('pending-opening', 0):>4} plays")
    print(f"  OPEN:            {plays_counts.get('open', 0):>4} plays")
    print(f"  PENDING-CLOSING: {plays_counts.get('pending-closing', 0):>4} plays")
    print(f"  CLOSED:          {plays_counts.get('closed', 0):>4} plays")
    print(f"  EXPIRED:         {plays_counts.get('expired', 0):>4} plays")
    print("  " + "-" * 30)
    print(f"  TOTAL ACTIVE:    {total_active:>4} plays")

    # ==========================================
    # ALPACA PACKAGE STATUS
    # ==========================================
    print("\n" + "-" * 40)
    print("  Alpaca Python SDK Status")
    print("-" * 40)
    print(f"  Current alpaca-py version: {alpaca.__version__}")

    # Ask user if they want to update
    print("\n  Would you like to update alpaca-py? (y/n): ", end="")
    try:
        response = input().strip().lower()
        if response == "y":
            update_alpaca()
        else:
            print("  Skipping alpaca-py update.")
    except Exception:
        print("  Skipping alpaca-py update.")

    # ==========================================
    # TRADING ACCOUNT STATUS
    # ==========================================
    print("\n" + "-" * 40)
    print("  Trading Account Status")
    print("-" * 40)

    try:
        trade_client = get_alpaca_client()

        # Check trading account status
        acct = trade_client.get_account()
        print(f"  Account Status:         {acct.status}")
        print(f"  Buying Power:           ${float(acct.buying_power):,.2f}")
        print(f"  Options Buying Power:   ${float(acct.options_buying_power):,.2f}")
        print(f"  Options Approved Level: {acct.options_approved_level}")
        print(f"  Options Trading Level:  {acct.options_trading_level}")

        # Check account configuration
        acct_config = trade_client.get_account_configurations()
        print(f"  Max Options Level:      {acct_config.max_options_trading_level}")

    except Exception as e:
        print(f"  Error accessing Alpaca API: {e}")

    # ==========================================
    # SUMMARY
    # ==========================================
    print("\n" + "=" * 60)
    print("  Finished Checking Status")
    print("=" * 60)

    # Show any warnings
    warnings = []
    if orch_status.get("dry_run", False):
        warnings.append("DRY-RUN MODE IS ACTIVE - No live trades will be executed!")
    if not orch_status.get("enabled", False):
        warnings.append("Strategy orchestration is DISABLED - system will not run.")
    if total_active == 0:
        warnings.append("No active plays found.")

    if warnings:
        print("\n  ⚠️  WARNINGS:")
        for w in warnings:
            print(f"    - {w}")

    print("\n  Press Enter to exit...")
    try:
        input()
    except Exception:
        pass


if __name__ == "__main__":
    check_system_status()

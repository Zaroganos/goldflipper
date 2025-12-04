from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Import exe-aware path utilities
from goldflipper.utils.exe_utils import (
    is_frozen,
    get_settings_path,
    get_settings_template_path,
    get_config_dir,
    get_executable_dir,
    debug_paths,
)

LOGGER = logging.getLogger("goldflipper.launcher")


def _print_startup_debug() -> None:
    """Print debug information about paths at startup."""
    if os.environ.get('GOLDFLIPPER_DEBUG') or is_frozen():
        print("=" * 60)
        print("Goldflipper Startup Debug Info")
        print("=" * 60)
        try:
            paths = debug_paths()
            for key, value in paths.items():
                # Highlight critical issues
                if key.endswith('_exists') and value is False:
                    print(f"  {key}: {value}  <-- WARNING: File missing!")
                else:
                    print(f"  {key}: {value}")
            
            # Additional critical checks
            settings_path = get_settings_path()
            if not settings_path.exists():
                template_path = paths.get('settings_template_path', 'unknown')
                template_exists = paths.get('settings_template_exists', False)
                print()
                print("  NOTICE: settings.yaml not found")
                print(f"  Template path: {template_path}")
                print(f"  Template exists: {template_exists}")
                if not template_exists:
                    print("  ERROR: Cannot create settings - template file missing!")
                    print("  This usually means the build didn't include the config data.")
        except Exception as e:
            print(f"  ERROR getting debug paths: {e}")
        print("=" * 60)
        print()


def _settings_path() -> Path:
    """Return the canonical path to the primary settings file.
    
    In frozen (exe) mode: returns path NEXT TO the exe (persistent).
    In source mode: returns path in goldflipper/config/.
    """
    return get_settings_path()


def _run_first_run_setup(force: bool) -> bool:
    """
    Launch the first-run wizard when required.

    Returns True when a previously-missing settings file is created during this
    invocation. This allows the TUI to display the onboarding affordances.
    """
    settings_file = _settings_path()
    existed_before = settings_file.exists()

    if not force and existed_before:
        return False

    try:
        from goldflipper.first_run_setup import FirstRunSetup
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("First-run setup unavailable: %s", exc)
        return False

    LOGGER.info(
        "Launching first-run setup (force=%s, existed_before=%s)",
        force,
        existed_before,
    )
    try:
        FirstRunSetup().run()
    except Exception as exc:  # pragma: no cover - GUI loop exceptions
        LOGGER.error("First-run setup terminated unexpectedly: %s", exc)

    created_now = (not existed_before) and settings_file.exists()
    if created_now:
        LOGGER.info("Settings profile created at %s", settings_file)
    else:
        LOGGER.debug(
            "First-run setup did not create a new settings file (exists=%s)",
            settings_file.exists(),
        )
    return created_now


def _launch_tui() -> None:
    """Start the Textual interface."""
    from goldflipper.goldflipper_tui import GoldflipperTUI

    app = GoldflipperTUI()
    app.run()


def _run_tool(tool_name: str) -> int:
    """
    Run a specific tool directly.
    
    This allows the exe to be launched with --tool <name> to run a specific
    tool in its own process (essential for Tkinter GUI tools).
    
    Supported tools:
    - play_creator_gui: Tkinter GUI for creating plays
    - configuration: Settings editor
    - view_plays: Textual UI for viewing plays
    - system_status: System status checker
    - option_data_fetcher: Option data tool
    - auto_play_creator: Auto play creator
    - chart_viewer: Chart viewer
    - trade_logger: Trade logger UI
    - get_alpaca_info: Alpaca account info
    """
    print(f"[Launcher] Running tool: {tool_name}")
    
    # Map tool names to module paths and entry functions
    TOOL_MAP = {
        'play_creator_gui': ('goldflipper.tools.play_creator_gui', 'main'),
        'configuration': ('goldflipper.tools.configuration', 'main'),
        'view_plays': ('goldflipper.tools.view_plays', 'main'),
        'system_status': ('goldflipper.tools.system_status', 'check_system_status'),
        'option_data_fetcher': ('goldflipper.tools.option_data_fetcher', 'main'),
        'auto_play_creator': ('goldflipper.tools.auto_play_creator', 'main'),
        'play_creation_tool': ('goldflipper.tools.play_creation_tool', 'main'),
        'chart_viewer': ('goldflipper.chart.chart_viewer', 'main'),
        'trade_logger': ('goldflipper.trade_logging.trade_logger_ui', 'main'),
        'get_alpaca_info': ('goldflipper.tools.get_alpaca_info', 'main'),
    }
    
    if tool_name not in TOOL_MAP:
        print(f"[ERROR] Unknown tool: {tool_name}")
        print(f"[ERROR] Available tools: {', '.join(TOOL_MAP.keys())}")
        return 1
    
    module_path, entry_func = TOOL_MAP[tool_name]
    
    try:
        print(f"[Launcher] Importing {module_path}")
        module = importlib.import_module(module_path)
        
        if hasattr(module, entry_func):
            print(f"[Launcher] Calling {entry_func}()")
            getattr(module, entry_func)()
        elif hasattr(module, 'run'):
            print(f"[Launcher] Calling run()")
            module.run()
        elif hasattr(module, 'main'):
            print(f"[Launcher] Calling main()")
            module.main()
        else:
            print(f"[Launcher] No entry function found, module may run on import")
        
        return 0
    except Exception as e:
        import traceback
        print(f"\n{'='*60}")
        print(f"[ERROR] Failed to run tool: {tool_name}")
        print(f"[ERROR] Module: {module_path}")
        print(f"[ERROR] Exception: {e}")
        print(f"{'='*60}")
        traceback.print_exc()
        print(f"{'='*60}")
        input("\nPress Enter to exit...")
        return 1


def main(argv: Optional[list[str]] = None) -> int:
    """
    Entry point for the packaged Goldflipper desktop experience.

    - Runs the onboarding wizard on the very first launch.
    - Falls back to the existing configuration afterwards.
    - Starts the Textual TUI by default.
    
    Special exe-mode arguments:
    - --trading-mode: Run the trading system directly (for spawned processes)
    - --service-install: Install the Windows service
    - --service-remove: Remove the Windows service
    """
    # Print debug info at startup (always in frozen mode, or when GOLDFLIPPER_DEBUG is set)
    _print_startup_debug()
    
    parser = argparse.ArgumentParser(description="Goldflipper Desktop Launcher")
    parser.add_argument(
        "--force-setup",
        action="store_true",
        help="Always run the configuration wizard before launching the TUI.",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Never launch the configuration wizard (even on first run).",
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Run the configuration wizard and exit without launching the TUI.",
    )
    # Exe-mode special arguments
    parser.add_argument(
        "--trading-mode",
        action="store_true",
        help="Run the trading system directly (used when launching from exe TUI).",
    )
    parser.add_argument(
        "--service-install",
        action="store_true",
        help="Install the Windows service (requires admin privileges).",
    )
    parser.add_argument(
        "--service-remove",
        action="store_true",
        help="Remove the Windows service (requires admin privileges).",
    )
    parser.add_argument(
        "--tool",
        type=str,
        help="Launch a specific tool directly (e.g., --tool play_creator_gui).",
    )
    args = parser.parse_args(argv)

    # Handle special exe-mode arguments
    if args.tool:
        return _run_tool(args.tool)
    
    if args.trading_mode:
        LOGGER.info("Trading mode requested; launching trading system directly.")
        from goldflipper.run import run_trading_system
        run_trading_system(console_mode=True)
        return 0
    
    if args.service_install:
        LOGGER.info("Service installation requested.")
        import win32serviceutil
        from goldflipper.run import GoldflipperService
        win32serviceutil.HandleCommandLine(GoldflipperService, argv=['', '--startup', 'auto', 'install'])
        return 0
    
    if args.service_remove:
        LOGGER.info("Service removal requested.")
        import win32serviceutil
        from goldflipper.run import GoldflipperService
        win32serviceutil.HandleCommandLine(GoldflipperService, argv=['', 'remove'])
        return 0

    # Normal TUI launch flow
    settings_created = False
    if not args.skip_setup:
        settings_created = _run_first_run_setup(force=args.force_setup)

    config_module = importlib.import_module("goldflipper.config.config")
    if settings_created:
        # Signal to the TUI that the onboarding workflow just completed so it
        # can highlight the configuration button and show notifications.
        config_module.settings_just_created = True

    if args.setup_only:
        LOGGER.info("Setup-only mode requested; exiting before launching TUI.")
        return 0

    _launch_tui()
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())

